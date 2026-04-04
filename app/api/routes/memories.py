from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, cast, String
from sqlalchemy.dialects.postgresql import ARRAY
from typing import Optional
import uuid
from datetime import datetime, timedelta

from app.db.session import get_db
from app.models.user import User, AgentProfile, Memory
from app.core.security import get_current_user

router = APIRouter()

VALID_SECTIONS       = {"BASIC", "PAST", "PRESENT", "FUTURE"}
VALID_TRAINING_MODES = {"manual", "conversation", "correction"}
REVIEW_THRESHOLD_DAYS = 90


# ── Shared serializers ─────────────────────────────────────────────────────

def _serialize_memory_short(m: Memory) -> dict:
    return {
        "id":                  str(m.id),
        "section":             m.section,
        "what_happened":       m.what_happened,
        "how_i_felt":          m.how_i_felt,
        "why_it_mattered":     m.why_it_mattered,
        "what_i_learned":      m.what_i_learned,
        "instinct_formed":     m.instinct_formed,
        "feeling_weight":      m.feeling_weight,
        "never_forget":        m.never_forget,
        "is_core_memory":      m.is_core_memory,
        "pattern_tags":        m.pattern_tags or [],
        "reinforcement_count": m.reinforcement_count or 0,
        "training_mode":       m.training_mode or "manual",
        "created_at":          m.created_at.isoformat() if m.created_at else None,
        "last_reinforced_at":  m.last_reinforced_at.isoformat() if m.last_reinforced_at else None,
    }


def _serialize_memory_full(m: Memory) -> dict:
    base = _serialize_memory_short(m)
    base.update({
        "cross_sections":            m.cross_sections or [],
        "context":                   m.context,
        "cultural_expression_notes": m.cultural_expression_notes,
        "what_happened_original":    m.what_happened_original,
        "how_i_felt_original":       m.how_i_felt_original,
        "why_it_mattered_original":  m.why_it_mattered_original,
        "what_i_learned_original":   m.what_i_learned_original,
        "instinct_formed_original":  m.instinct_formed_original,
        "transcript_language":       m.transcript_language,
    })
    return base


async def _get_agent(user_id, db: AsyncSession) -> AgentProfile:
    result = await db.execute(
        select(AgentProfile).where(AgentProfile.user_id == user_id)
    )
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


# ── GET /memories/ ─────────────────────────────────────────────────────────

@router.get("/")
async def list_memories(
    section:       Optional[str]  = Query(None, description="BASIC | PAST | PRESENT | FUTURE"),
    never_forget:  Optional[bool] = Query(None),
    min_weight:    Optional[float]= Query(None, description="Minimum feeling weight 0–10"),
    training_mode: Optional[str]  = Query(None, description="manual | conversation | correction"),
    limit:         int            = Query(50, le=200),
    offset:        int            = Query(0, ge=0),
    current_user:  User           = Depends(get_current_user),
    db:            AsyncSession   = Depends(get_db),
):
    agent = await _get_agent(current_user.id, db)

    query = select(Memory).where(
        Memory.agent_id == agent.id,
        Memory.is_active == True,
    )

    if section:
        section_upper = section.upper()
        if section_upper not in VALID_SECTIONS:
            raise HTTPException(status_code=400, detail=f"section must be one of: {', '.join(VALID_SECTIONS)}")
        query = query.where(Memory.section == section_upper)

    if never_forget is not None:
        query = query.where(Memory.never_forget == never_forget)

    if min_weight is not None:
        query = query.where(Memory.feeling_weight >= min_weight)

    if training_mode is not None:
        if training_mode not in VALID_TRAINING_MODES:
            raise HTTPException(status_code=400, detail=f"training_mode must be one of: {', '.join(VALID_TRAINING_MODES)}")
        query = query.where(Memory.training_mode == training_mode)

    count_result = await db.execute(
        select(func.count()).select_from(query.subquery())
    )
    total = count_result.scalar() or 0

    query = query.order_by(
        Memory.never_forget.desc(),
        Memory.feeling_weight.desc(),
        Memory.created_at.desc(),
    ).limit(limit).offset(offset)

    result = await db.execute(query)
    memories = result.scalars().all()

    return {
        "total":    total,
        "limit":    limit,
        "offset":   offset,
        "memories": [_serialize_memory_short(m) for m in memories],
    }


# ── GET /memories/search ──────────────────────────────────────────────────

@router.get("/search")
async def search_memories(
    q:             str            = Query(..., min_length=1),
    section:       Optional[str]  = Query(None),
    training_mode: Optional[str]  = Query(None),
    limit:         int            = Query(20, le=100),
    offset:        int            = Query(0, ge=0),
    current_user:  User           = Depends(get_current_user),
    db:            AsyncSession   = Depends(get_db),
):
    agent = await _get_agent(current_user.id, db)

    search_term = f"%{q.strip()}%"

    text_filter = or_(
        Memory.what_happened.ilike(search_term),
        Memory.how_i_felt.ilike(search_term),
        Memory.instinct_formed.ilike(search_term),
        Memory.what_i_learned.ilike(search_term),
        Memory.why_it_mattered.ilike(search_term),
        Memory.what_happened_original.ilike(search_term),
        Memory.how_i_felt_original.ilike(search_term),
        Memory.instinct_formed_original.ilike(search_term),
        cast(Memory.pattern_tags, String).ilike(search_term),
    )

    query = select(Memory).where(
        Memory.agent_id  == agent.id,
        Memory.is_active == True,
        text_filter,
    )

    if section:
        section_upper = section.upper()
        if section_upper not in VALID_SECTIONS:
            raise HTTPException(status_code=400, detail=f"section must be one of: {', '.join(VALID_SECTIONS)}")
        query = query.where(Memory.section == section_upper)

    if training_mode is not None:
        if training_mode not in VALID_TRAINING_MODES:
            raise HTTPException(status_code=400, detail=f"training_mode must be one of: {', '.join(VALID_TRAINING_MODES)}")
        query = query.where(Memory.training_mode == training_mode)

    count_result = await db.execute(
        select(func.count()).select_from(query.subquery())
    )
    total = count_result.scalar() or 0

    query = query.order_by(
        Memory.never_forget.desc(),
        Memory.feeling_weight.desc(),
        Memory.created_at.desc(),
    ).limit(limit).offset(offset)

    result = await db.execute(query)
    memories = result.scalars().all()

    return {
        "query":    q,
        "total":    total,
        "limit":    limit,
        "offset":   offset,
        "memories": [_serialize_memory_short(m) for m in memories],
    }


# ── GET /memories/stats ───────────────────────────────────────────────────

@router.get("/stats")
async def memory_stats(
    current_user: User         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    agent = await _get_agent(current_user.id, db)

    # Section counts — one query
    section_rows = await db.execute(
        select(Memory.section, func.count(Memory.id).label("cnt"))
        .where(Memory.agent_id == agent.id, Memory.is_active == True)
        .group_by(Memory.section)
    )
    section_counts = {s: 0 for s in VALID_SECTIONS}
    for row in section_rows.all():
        if row.section in section_counts:
            section_counts[row.section] = row.cnt

    # Training mode counts — one query
    mode_rows = await db.execute(
        select(Memory.training_mode, func.count(Memory.id).label("cnt"))
        .where(Memory.agent_id == agent.id, Memory.is_active == True)
        .group_by(Memory.training_mode)
    )
    mode_counts = {"manual": 0, "conversation": 0, "correction": 0}
    for row in mode_rows.all():
        mode = row.training_mode or "manual"
        if mode in mode_counts:
            mode_counts[mode] = row.cnt

    # Never forget + avg weight — one query
    agg_row = await db.execute(
        select(
            func.count(Memory.id).filter(Memory.never_forget == True).label("never_forget_count"),
            func.avg(Memory.feeling_weight).label("avg_weight"),
        ).where(Memory.agent_id == agent.id, Memory.is_active == True)
    )
    agg = agg_row.one()

    # Review count — PRESENT memories older than 90 days
    cutoff = datetime.utcnow() - timedelta(days=REVIEW_THRESHOLD_DAYS)
    review_result = await db.execute(
        select(func.count(Memory.id)).where(
            Memory.agent_id  == agent.id,
            Memory.is_active == True,
            Memory.section   == "PRESENT",
            Memory.created_at < cutoff,
        )
    )
    review_count = review_result.scalar() or 0

    total = sum(section_counts.values())

    return {
        "total":              total,
        "by_section":         section_counts,
        "by_training_mode":   mode_counts,
        "never_forget_count": agg.never_forget_count or 0,
        "avg_weight":         round(float(agg.avg_weight or 0), 2),
        "wisdom_score":       agent.wisdom_score,
        "review_count":       review_count,   # ← new — drives the review banner
    }


# ── GET /memories/review ──────────────────────────────────────────────────

@router.get("/review")
async def get_review_memories(
    current_user: User         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    """
    Returns PRESENT memories older than 90 days.
    These are candidates for review — the owner decides:
      keep (still current), archive (move to PAST), or delete.

    Called when the review banner is clicked on the memories page.
    """
    agent = await _get_agent(current_user.id, db)

    cutoff = datetime.utcnow() - timedelta(days=REVIEW_THRESHOLD_DAYS)

    result = await db.execute(
        select(Memory)
        .where(
            Memory.agent_id  == agent.id,
            Memory.is_active == True,
            Memory.section   == "PRESENT",
            Memory.created_at < cutoff,
        )
        .order_by(Memory.created_at.asc())  # oldest first — most likely outdated
    )
    memories = result.scalars().all()

    return {
        "count":     len(memories),
        "threshold_days": REVIEW_THRESHOLD_DAYS,
        "memories":  [_serialize_memory_short(m) for m in memories],
    }


# ── POST /memories/{memory_id}/archive ───────────────────────────────────

@router.post("/{memory_id}/archive")
async def archive_memory(
    memory_id:    str,
    current_user: User         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    """
    Move a PRESENT memory to PAST.

    The event happened — it's real history now, just no longer current.
    Weight stays the same. Memory stays active.
    Agent will reference it in past tense ("last year you were going through...")
    rather than present tense ("you are currently...").
    """
    try:
        mid = uuid.UUID(memory_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid memory ID")

    result = await db.execute(
        select(Memory).where(
            Memory.id      == mid,
            Memory.user_id == current_user.id,
            Memory.is_active == True,
        )
    )
    memory = result.scalar_one_or_none()
    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")

    if memory.section != "PRESENT":
        raise HTTPException(status_code=400, detail="Only PRESENT memories can be archived to PAST")

    memory.section = "PAST"
    await db.commit()

    return {
        "message":    "Memory moved to Past.",
        "id":         memory_id,
        "section":    "PAST",
    }


# ── GET /memories/{memory_id} ─────────────────────────────────────────────

@router.get("/{memory_id}")
async def get_memory(
    memory_id:    str,
    current_user: User         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    try:
        mid = uuid.UUID(memory_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid memory ID")

    result = await db.execute(
        select(Memory).where(
            Memory.id      == mid,
            Memory.user_id == current_user.id,
            Memory.is_active == True,
        )
    )
    memory = result.scalar_one_or_none()
    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")

    return _serialize_memory_full(memory)


# ── DELETE /memories/{memory_id} ──────────────────────────────────────────

@router.delete("/{memory_id}")
async def delete_memory(
    memory_id:    str,
    current_user: User         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    try:
        mid = uuid.UUID(memory_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid memory ID")

    result = await db.execute(
        select(Memory).where(
            Memory.id      == mid,
            Memory.user_id == current_user.id,
            Memory.is_active == True,
        )
    )
    memory = result.scalar_one_or_none()
    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")

    memory.is_active = False

    agent = await _get_agent(current_user.id, db)
    if agent.total_memories and agent.total_memories > 0:
        agent.total_memories  -= 1
        agent.last_updated_at  = datetime.utcnow()

    await db.commit()

    return {
        "message":       "Memory removed.",
        "id":            memory_id,
        "training_mode": memory.training_mode or "manual",
    }