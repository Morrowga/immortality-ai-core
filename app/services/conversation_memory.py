"""
app/services/conversation_memory.py

Smart conversation memory extraction.

Two triggers:
  1. Every 6 turns in an active session (called from chat.py / public.py)
  2. Session-end fallback for sessions that never hit 6 turns
     (called from the same place via _should_extract_remainder)

Flow per trigger:
  - Fetch last N turns from AgentResponse for this session_key
  - Send to Haiku — "did anything meaningful happen here?"
  - If yes → run through duplicate check → save as Memory
    with training_mode="conversation", weight 3-5
  - If no  → discard silently

No new DB table needed. Everything reads/writes to existing tables:
  AgentResponse (read turns), Memory (write), StyleProfile (read agent_id→user_id)

Duplicate check:
  Uses existing check_duplicate_memory() with cosine similarity threshold 0.85.
  If duplicate found → reinforce existing memory instead of creating new one.
  Same logic as manual training — consistent behavior.
"""

import json
import asyncio
import random
from anthropic import AsyncAnthropic, InternalServerError, APIStatusError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.core.config import settings
from app.models.user import AgentResponse, Memory, TrainingSession, AgentProfile
from app.services.embeddings import generate_embedding
from app.services.extraction import check_duplicate_memory, reinforce_memory

client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

# How many turns trigger extraction
EXTRACTION_THRESHOLD = 6

# Minimum turns for session-end fallback extraction
MIN_TURNS_FOR_FALLBACK = 2

EXTRACTION_PROMPT = """You are analyzing a real conversation between a person and their AI agent.
Your job: find anything meaningful that was said about the SPEAKER (the human, not the agent).

Look for:
- Personal facts (job, family, relationships, health, location)
- Emotions or struggles they expressed
- Life events they mentioned (past or current)
- Beliefs, values, or opinions they shared
- Anything that reveals who this person is

DO NOT extract:
- Pure small talk ("hi", "how are you", "thanks", "bye")
- Questions the speaker asked the agent
- Agent responses
- Generic pleasantries with no personal content

If nothing meaningful was shared by the speaker → return null.
If something meaningful exists → extract it.

Be conservative with weight:
  5.0-6.0 = significant personal detail (job loss, relationship issue, health)
  3.0-4.0 = moderate personal detail (preference, opinion, minor life event)
  2.0-2.9 = passing mention worth noting but low significance

Return ONLY valid JSON or null. No explanation. No markdown.

If extracting:
{
  "what_happened": "Clean English summary of what the speaker shared",
  "how_i_felt": "How the speaker seemed to feel (infer from tone if not explicit)",
  "instinct_formed": "What this reveals about the speaker as a person",
  "feeling_weight": 4.0,
  "section": "PAST or PRESENT or BASIC",
  "pattern_tags": ["tag1", "tag2"],
  "never_forget": false
}

If nothing meaningful: null"""


async def _call_haiku(turns_text: str) -> dict | None:
    """
    Send conversation turns to Haiku for extraction.
    Returns parsed dict or None if nothing meaningful found.
    """
    last_error = None
    for attempt in range(3):
        try:
            response = await client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=600,
                system=EXTRACTION_PROMPT,
                messages=[{"role": "user", "content": turns_text}],
            )
            raw = response.content[0].text.strip()

            # Haiku returned null — nothing meaningful
            if raw.lower() == "null" or not raw:
                return None

            # Strip markdown fences if present
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            raw = raw.strip()

            return json.loads(raw)

        except (InternalServerError, APIStatusError) as e:
            status = getattr(e, "status_code", None)
            if status in (429, 529) or "overload" in str(e).lower():
                last_error = e
                await asyncio.sleep((2 ** attempt) + random.uniform(0, 0.3))
                continue
            return None  # non-retryable — skip silently
        except (json.JSONDecodeError, Exception):
            return None  # parse failure — skip silently

    return None  # all retries exhausted


def _format_turns(turns: list[AgentResponse]) -> str:
    """
    Format AgentResponse rows into a readable conversation block for Haiku.
    Oldest first so context is chronological.
    """
    lines = ["CONVERSATION TURNS (oldest first):\n"]
    for turn in turns:
        if turn.question_text:
            speaker = turn.speaker_name or "Speaker"
            lines.append(f"{speaker}: {turn.question_text}")
        if turn.response_text:
            lines.append(f"Agent: {turn.response_text[:300]}")  # truncate long responses
        lines.append("")
    return "\n".join(lines)


async def _get_recent_turns(
    session_key: str,
    agent_id: str,
    db: AsyncSession,
    limit: int = EXTRACTION_THRESHOLD,
) -> list[AgentResponse]:
    """
    Fetch the most recent N turns for a session, returned chronologically.
    """
    from sqlalchemy import desc
    result = await db.execute(
        select(AgentResponse)
        .where(
            AgentResponse.agent_id   == agent_id,
            AgentResponse.session_key == session_key,
        )
        .order_by(desc(AgentResponse.created_at))
        .limit(limit)
    )
    turns = result.scalars().all()
    return list(reversed(turns))  # chronological order


async def _get_turn_count(
    session_key: str,
    agent_id: str,
    db: AsyncSession,
) -> int:
    result = await db.execute(
        select(func.count(AgentResponse.id)).where(
            AgentResponse.agent_id    == agent_id,
            AgentResponse.session_key == session_key,
        )
    )
    return result.scalar() or 0


async def _save_conversation_memory(
    extracted: dict,
    agent_id: str,
    user_id: str,
    session_key: str,
    db: AsyncSession,
) -> dict | None:
    """
    Save extracted conversation memory.
    Runs duplicate check first — reinforces existing if duplicate found.
    Returns saved memory info or None.
    """
    from sqlalchemy import text as sa_text
    from datetime import datetime
    import uuid as uuid_mod

    embed_text = (
        f"{extracted.get('what_happened', '')} "
        f"{extracted.get('how_i_felt', '')} "
        f"{extracted.get('instinct_formed', '')}"
    ).strip()

    if not embed_text:
        return None

    try:
        embedding = await generate_embedding(embed_text)
    except Exception:
        return None

    # ── Duplicate check ───────────────────────────────────────────────────
    duplicate = await check_duplicate_memory(
        embedding=embedding,
        agent_id=agent_id,
        db=db,
        threshold=0.85,
    )

    if duplicate:
        # Reinforce existing memory instead of creating a duplicate
        reinforced = await reinforce_memory(
            memory_id=duplicate["memory_id"],
            db=db,
        )
        return {
            "action":   "reinforced",
            "memory_id": duplicate["memory_id"],
            "weight":    reinforced.get("feeling_weight"),
        }

    # ── Save new conversation memory ──────────────────────────────────────
    feeling_weight = float(extracted.get("feeling_weight", 4.0))
    feeling_weight = max(1.0, min(6.0, feeling_weight))  # cap at 6 — conversation memories don't outweigh manual

    # Create a minimal training session to link the memory
    session = TrainingSession(
        user_id            = user_id,
        agent_id           = agent_id,
        mode               = "conversation",
        section_covered    = extracted.get("section", "PRESENT"),
        memories_captured  = 1,
        avg_weight_of_session = feeling_weight,
    )
    db.add(session)
    await db.flush()

    memory = Memory(
        user_id              = user_id,
        agent_id             = agent_id,
        session_id           = session.id,
        section              = extracted.get("section", "PRESENT"),
        transcript_text      = extracted.get("what_happened", ""),
        transcript_language  = "en",
        what_happened        = extracted.get("what_happened"),
        how_i_felt           = extracted.get("how_i_felt"),
        instinct_formed      = extracted.get("instinct_formed"),
        feeling_weight       = feeling_weight,
        never_forget         = feeling_weight >= 8.5,
        pattern_tags         = extracted.get("pattern_tags", []),
        training_mode        = "conversation",
        is_core_memory       = False,
    )
    db.add(memory)
    await db.flush()

    # Insert embedding via raw SQL (same pattern as training.py)
    embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"
    await db.execute(
        sa_text("UPDATE memories SET embedding = :embedding WHERE id = :id"),
        {"embedding": embedding_str, "id": str(memory.id)},
    )

    # Update agent memory count
    result = await db.execute(
        select(AgentProfile).where(AgentProfile.id == agent_id)
    )
    agent = result.scalar_one_or_none()
    if agent:
        agent.total_memories  = (agent.total_memories or 0) + 1
        from datetime import datetime
        agent.last_updated_at = datetime.utcnow()

    await db.commit()

    return {
        "action":    "created",
        "memory_id": str(memory.id),
        "weight":    feeling_weight,
        "section":   memory.section,
        "tags":      memory.pattern_tags,
    }


# ── Public API — called from chat.py and public.py ────────────────────────

def should_extract(turn_count: int) -> bool:
    """
    Returns True if extraction should fire at this turn count.
    Fires at turn 6, 12, 18, 24... (every EXTRACTION_THRESHOLD turns)
    """
    return turn_count > 0 and turn_count % EXTRACTION_THRESHOLD == 0


def should_extract_remainder(turn_count: int) -> bool:
    """
    Returns True if this session has unprocessed turns that never hit
    the main threshold. Used as a session-end fallback.

    Fires when: turn_count > 0 AND turn_count < EXTRACTION_THRESHOLD
    AND turn_count >= MIN_TURNS_FOR_FALLBACK.

    Caller is responsible for only calling this at session end
    (e.g. when session_key changes or explicit end signal).
    Currently not used in the main chat flow — reserved for
    a future scheduled job or explicit session close.
    """
    return (
        MIN_TURNS_FOR_FALLBACK <= turn_count < EXTRACTION_THRESHOLD
    )


async def maybe_extract_conversation_memory(
    session_key: str,
    agent_id: str,
    user_id: str,
    turn_count: int,
    db_factory,
) -> None:
    """
    Main entry point called from public.py after saving each response.

    Receives db_factory (AsyncSessionLocal) — NOT an open session.
    Opens its own session so it's safe to run after the request session closes.

    Call pattern in public.py:
        from app.db.session import AsyncSessionLocal
        from app.services.conversation_memory import maybe_extract_conversation_memory

        background_tasks.add_task(
            maybe_extract_conversation_memory,
            session_key = data.session_key,
            agent_id    = str(agent.id),
            user_id     = str(agent.user_id),
            turn_count  = turn_count,
            db_factory  = AsyncSessionLocal,
        )
    """
    if not should_extract(turn_count):
        return

    if not session_key:
        return

    try:
        async with db_factory() as db:
            turns = await _get_recent_turns(
                session_key=session_key,
                agent_id=agent_id,
                db=db,
                limit=EXTRACTION_THRESHOLD,
            )

            if not turns:
                return

            turns_text = _format_turns(turns)
            extracted  = await _call_haiku(turns_text)

            if not extracted:
                return

            await _save_conversation_memory(
                extracted=extracted,
                agent_id=agent_id,
                user_id=user_id,
                session_key=session_key,
                db=db,
            )

    except Exception:
        # Never crash over a background extraction
        pass