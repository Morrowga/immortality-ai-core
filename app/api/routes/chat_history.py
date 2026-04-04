"""
app/api/routes/chat_history.py

Phase 1 — Conversation history persistence.

Two endpoints:

  GET  /chat/history
       Returns the last N messages for a session_key.
       Frontend calls this on page load to rehydrate the conversation.
       Works for both owner chat and public chat (public passes access_key).

  GET  /chat/sessions
       Returns a list of recent session_keys for the owner, with metadata.
       Used to show "previous conversations" in the sidebar.

session_key strategy:
  - Generated on the frontend as a UUID or timestamp string.
  - Stored in localStorage on the client side.
  - Passed with every chat request (already supported in ChatRequest).
  - On page load, frontend reads session_key from localStorage and calls
    GET /chat/history?session_key=... to rehydrate.
  - If no session_key in localStorage, frontend generates a new one
    (new conversation starts fresh).

No new DB table needed — AgentResponse already stores:
  session_key, question_text, response_text, speaker_name, created_at.
We just need to read it back.

Frontend implementation note (add to your frontend docs):
  On mount:
    const sessionKey = localStorage.getItem('session_key') ?? crypto.randomUUID()
    localStorage.setItem('session_key', sessionKey)
    const history = await GET /chat/history?session_key={sessionKey}
    // populate chat UI with history

  On new conversation button:
    const newKey = crypto.randomUUID()
    localStorage.setItem('session_key', newKey)
    // clear chat UI
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, distinct, func
from typing import Optional
import uuid

from app.db.session import get_db
from app.models.user import User, AgentProfile, AgentResponse
from app.core.security import get_current_user

router = APIRouter()


# ── GET /chat/history ──────────────────────────────────────────────────────

@router.get("/history")
async def get_chat_history(
    session_key: str = Query(..., description="Session key from localStorage"),
    limit: int = Query(50, le=200, description="Max messages to return"),
    before_id: Optional[str] = Query(None, description="Cursor — return messages before this response_id"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Rehydrate a conversation from a session_key.

    Returns messages in chronological order (oldest first) so the frontend
    can render them top-to-bottom without reversing.

    Supports cursor-based pagination via before_id for long conversations.

    Response shape per message:
      {
        "id": "uuid",
        "role": "user" | "assistant",
        "content": "...",
        "speaker_name": "...",
        "created_at": "ISO string",
        "training_mode": "conversation" | null   -- future use
      }

    Each turn is stored as ONE AgentResponse row containing both
    question_text (user) and response_text (assistant). We expand
    each row into two message objects so the frontend gets a flat
    message array identical to what it would build during a live chat.
    """
    if not session_key or not session_key.strip():
        raise HTTPException(status_code=400, detail="session_key is required")

    # Get the agent for this user
    result = await db.execute(
        select(AgentProfile).where(AgentProfile.user_id == current_user.id)
    )
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Build query
    query = select(AgentResponse).where(
        AgentResponse.agent_id == agent.id,
        AgentResponse.session_key == session_key,
    )

    # Cursor pagination — if before_id provided, only return rows older than it.
    # Compare on id (UUID v4 are random so we keep created_at ordering) —
    # use created_at of the cursor row but also add id as tiebreaker to avoid
    # skipping/duplicating rows when two responses share the same timestamp.
    if before_id:
        try:
            before_uuid = uuid.UUID(before_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid before_id")

        cursor_result = await db.execute(
            select(AgentResponse.created_at, AgentResponse.id).where(
                AgentResponse.id == before_uuid
            )
        )
        cursor_row = cursor_result.one_or_none()
        if cursor_row:
            cursor_ts, cursor_id = cursor_row
            from sqlalchemy import or_, and_
            query = query.where(
                or_(
                    AgentResponse.created_at < cursor_ts,
                    and_(
                        AgentResponse.created_at == cursor_ts,
                        AgentResponse.id < cursor_id,
                    ),
                )
            )

    # Fetch newest-first (we'll reverse for display)
    query = query.order_by(
        desc(AgentResponse.created_at),
        desc(AgentResponse.id),
    ).limit(limit)

    result = await db.execute(query)
    rows = list(reversed(result.scalars().all()))  # chronological order

    # Expand each row into [user_message, assistant_message]
    messages = []
    for row in rows:
        if row.question_text:
            messages.append({
                "id":           f"{str(row.id)}-q",
                "role":         "user",
                "content":      row.question_text,
                "speaker_name": row.speaker_name or "",
                "created_at":   row.created_at.isoformat() if row.created_at else None,
            })
        if row.response_text:
            messages.append({
                "id":           str(row.id),
                "role":         "assistant",
                "content":      row.response_text,
                "speaker_name": row.speaker_name or "",
                "created_at":   row.created_at.isoformat() if row.created_at else None,
                "response_id":  str(row.id),   # needed for feedback / voice speak
            })

    has_more = len(rows) == limit
    oldest_id = str(rows[0].id) if rows else None

    return {
        "session_key": session_key,
        "messages":    messages,
        "count":       len(messages),
        "has_more":    has_more,
        "oldest_id":   oldest_id,   # use as before_id for next page
    }


# ── GET /chat/sessions ─────────────────────────────────────────────────────

@router.get("/sessions")
async def list_chat_sessions(
    limit: int = Query(20, le=50),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List recent unique sessions for the owner.
    Shows session_key, who they were talking to, message count,
    and last message time — enough for a "previous conversations" sidebar.

    Only returns sessions that have at least one message.
    Ordered by most recent activity first.
    """
    result = await db.execute(
        select(AgentProfile).where(AgentProfile.user_id == current_user.id)
    )
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Get distinct session_keys with metadata
    # One query — aggregate per session_key
    from sqlalchemy import case

    session_query = (
        select(
            AgentResponse.session_key,
            func.count(AgentResponse.id).label("message_count"),
            func.max(AgentResponse.created_at).label("last_active"),
            # Take the most common speaker_name in this session
            func.max(AgentResponse.speaker_name).label("speaker_name"),
        )
        .where(
            AgentResponse.agent_id == agent.id,
            AgentResponse.session_key.isnot(None),
            AgentResponse.session_key != "",
        )
        .group_by(AgentResponse.session_key)
        .order_by(desc("last_active"))
        .limit(limit)
    )

    result = await db.execute(session_query)
    sessions = result.all()

    return {
        "sessions": [
            {
                "session_key":    row.session_key,
                "speaker_name":   row.speaker_name or "Unknown",
                "message_count":  row.message_count,
                "last_active":    row.last_active.isoformat() if row.last_active else None,
            }
            for row in sessions
        ]
    }


# ── GET /chat/history/public ───────────────────────────────────────────────

@router.get("/history/public")
async def get_public_chat_history(
    session_key: str = Query(...),
    agent_slug: str = Query(..., description="Agent slug — used to scope the query"),
    limit: int = Query(50, le=200),
    before_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Public version of history rehydration — no auth required.
    Used by the public chat page (/[slug]) to restore conversation
    after a page reload.

    Scoped by agent_slug + session_key so a person can only see
    their own conversation (they must know the session_key, which
    is stored in their own localStorage).

    No authentication — the session_key IS the access control here.
    A random UUID session_key is unguessable enough for this use case.
    """
    if not session_key or not session_key.strip():
        raise HTTPException(status_code=400, detail="session_key is required")
    if not agent_slug or not agent_slug.strip():
        raise HTTPException(status_code=400, detail="agent_slug is required")

    # Resolve agent by slug
    result = await db.execute(
        select(AgentProfile).where(AgentProfile.slug == agent_slug.lower().strip())
    )
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    query = select(AgentResponse).where(
        AgentResponse.agent_id == agent.id,
        AgentResponse.session_key == session_key,
    )

    if before_id:
        try:
            before_uuid = uuid.UUID(before_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid before_id")
        cursor_result = await db.execute(
            select(AgentResponse.created_at, AgentResponse.id).where(
                AgentResponse.id == before_uuid
            )
        )
        cursor_row = cursor_result.one_or_none()
        if cursor_row:
            cursor_ts, cursor_id = cursor_row
            from sqlalchemy import or_, and_
            query = query.where(
                or_(
                    AgentResponse.created_at < cursor_ts,
                    and_(
                        AgentResponse.created_at == cursor_ts,
                        AgentResponse.id < cursor_id,
                    ),
                )
            )

    query = query.order_by(
        desc(AgentResponse.created_at),
        desc(AgentResponse.id),
    ).limit(limit)
    result = await db.execute(query)
    rows = list(reversed(result.scalars().all()))

    messages = []
    for row in rows:
        if row.question_text:
            messages.append({
                "id":           f"{str(row.id)}-q",
                "role":         "user",
                "content":      row.question_text,
                "speaker_name": row.speaker_name or "",
                "created_at":   row.created_at.isoformat() if row.created_at else None,
            })
        if row.response_text:
            messages.append({
                "id":           str(row.id),
                "role":         "assistant",
                "content":      row.response_text,
                "speaker_name": row.speaker_name or "",
                "created_at":   row.created_at.isoformat() if row.created_at else None,
                "response_id":  str(row.id),
            })

    has_more = len(rows) == limit
    oldest_id = str(rows[0].id) if rows else None

    return {
        "session_key": session_key,
        "messages":    messages,
        "count":       len(messages),
        "has_more":    has_more,
        "oldest_id":   oldest_id,
    }