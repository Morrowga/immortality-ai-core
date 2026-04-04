from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
from pydantic import BaseModel
from typing import Optional
import uuid
import asyncio
from datetime import datetime

from app.db.session import get_db
from app.models.user import User, AgentProfile, Memory, TrainingSession, StyleProfile, AgentLifecycle
from app.core.security import get_current_user
from app.services.embeddings import generate_embedding
from app.services.patterns import should_run_abstraction, run_pattern_abstraction
from app.services.extraction import (
    extract_memory, check_duplicate_memory, reinforce_memory,
    extract_voice_fingerprint, merge_voice_fingerprints,
)

router = APIRouter()

WISDOM_CAP = 100.0


class TrainRequest(BaseModel):
    text: str
    mode: str = "free"


class ConfirmMemoryRequest(BaseModel):
    extracted: dict
    feeling_weight: float
    session_id: str


@router.post("/submit")
async def submit_training(
    data: TrainRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not data.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    result = await db.execute(
        select(AgentProfile).where(AgentProfile.user_id == current_user.id)
    )
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    if not agent.survey_completed:
        raise HTTPException(
            status_code=403,
            detail="Complete your personality survey first before training."
        )

    result = await db.execute(
        select(StyleProfile).where(StyleProfile.user_id == current_user.id)
    )
    style = result.scalar_one_or_none()
    style_context = ""
    if style:
        style_context = f"Speaking pace: {style.avg_speaking_pace}, Directness: {style.directness_level}/10, Warmth: {style.warmth_level}/10"

    session = TrainingSession(
        user_id=current_user.id,
        agent_id=agent.id,
        mode=data.mode,
    )
    db.add(session)
    await db.flush()

    try:
        extracted, fingerprint = await asyncio.gather(
            extract_memory(
                text=data.text,
                language=current_user.language,
                style_context=style_context,
            ),
            extract_voice_fingerprint(
                text=data.text,
                language=current_user.language,
            ),
            return_exceptions=False,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

    if fingerprint and style:
        existing_fp = style.voice_fingerprint or {}
        style.voice_fingerprint = merge_voice_fingerprints(existing_fp, fingerprint)
        style.last_trained_at = datetime.utcnow()
        print(f"[FINGERPRINT] merged. sample_count={style.voice_fingerprint.get('sample_count', 1)}")

    await db.commit()

    return {
        "session_id": str(session.id),
        "extracted": extracted,
        "original_text": data.text,
    }


@router.post("/confirm")
async def confirm_memory(
    data: ConfirmMemoryRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AgentProfile).where(AgentProfile.user_id == current_user.id)
    )
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    embed_text = (
        f"{data.extracted.get('what_happened', '')} "
        f"{data.extracted.get('how_i_felt', '')} "
        f"{data.extracted.get('instinct_formed', '')}"
    )
    embedding = await generate_embedding(embed_text)
    embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"

    duplicate = await check_duplicate_memory(
        embedding=embedding,
        agent_id=str(agent.id),
        db=db,
    )

    if duplicate:
        reinforced = await reinforce_memory(
            memory_id=duplicate["memory_id"],
            db=db,
        )

        # Reinforce gives a small wisdom bump — it's a repeat, not new knowledge
        agent.wisdom_score    = min(WISDOM_CAP, (agent.wisdom_score or 0.0) + 0.2)
        agent.last_updated_at = datetime.utcnow()
        await db.commit()

        return {
            "duplicate":          True,
            "message":            "You have shared something similar before. Memory reinforced.",
            "existing_memory":    duplicate["what_happened"],
            "new_weight":         reinforced["feeling_weight"],
            "reinforcement_count": reinforced["reinforcement_count"],
            "wisdom_score":       round(agent.wisdom_score, 2),
        }

    memory = Memory(
        user_id=current_user.id,
        agent_id=agent.id,
        session_id=uuid.UUID(data.session_id),
        section=data.extracted.get("section", "PAST"),
        cross_sections=data.extracted.get("cross_sections", []),
        is_core_memory=data.extracted.get("is_core_memory", False),
        transcript_text=data.extracted.get("what_happened", ""),
        transcript_original=data.extracted.get("what_happened_original", ""),
        transcript_language=current_user.language,
        what_happened=data.extracted.get("what_happened"),
        what_happened_original=data.extracted.get("what_happened_original"),
        context=data.extracted.get("context"),
        how_i_felt=data.extracted.get("how_i_felt"),
        how_i_felt_original=data.extracted.get("how_i_felt_original"),
        why_it_mattered=data.extracted.get("why_it_mattered"),
        why_it_mattered_original=data.extracted.get("why_it_mattered_original"),
        what_i_learned=data.extracted.get("what_i_learned"),
        what_i_learned_original=data.extracted.get("what_i_learned_original"),
        instinct_formed=data.extracted.get("instinct_formed"),
        instinct_formed_original=data.extracted.get("instinct_formed_original"),
        cultural_expression_notes=data.extracted.get("cultural_expression_notes"),
        feeling_weight=data.feeling_weight,
        never_forget=data.feeling_weight >= 8.5,
        pattern_tags=data.extracted.get("pattern_tags", []),
        training_mode="manual",
    )
    db.add(memory)
    await db.flush()

    await db.execute(
        text("UPDATE memories SET embedding = :embedding WHERE id = :id"),
        {"embedding": embedding_str, "id": str(memory.id)}
    )

    # New memory: wisdom += feeling_weight * 0.1
    # Weight-5 → +0.5, weight-9 → +0.9. At 50 memories avg weight-7 → ~35 pts.
    increment             = round(data.feeling_weight * 0.1, 3)
    agent.wisdom_score    = min(WISDOM_CAP, (agent.wisdom_score or 0.0) + increment)
    agent.total_memories  = (agent.total_memories or 0) + 1
    agent.last_updated_at = datetime.utcnow()

    result = await db.execute(
        select(TrainingSession).where(TrainingSession.id == uuid.UUID(data.session_id))
    )
    session = result.scalar_one_or_none()
    if session:
        session.memories_captured     = 1
        session.avg_weight_of_session = data.feeling_weight

    result = await db.execute(
        select(AgentLifecycle).where(AgentLifecycle.agent_id == agent.id)
    )
    lifecycle = result.scalar_one_or_none()
    if lifecycle:
        lifecycle.training_session_count = (lifecycle.training_session_count or 0) + 1
        lifecycle.last_active_at         = datetime.utcnow()

    await db.commit()

    # Pattern abstraction runs every 10 sessions and blends in avg pattern weight —
    # compounds naturally on top of the per-memory increments above.
    try:
        if await should_run_abstraction(str(agent.id), db):
            await run_pattern_abstraction(str(agent.id), db)
    except Exception:
        pass

    return {
        "memory_id":      str(memory.id),
        "feeling_weight": data.feeling_weight,
        "never_forget":   memory.never_forget,
        "acknowledgment": "Saved successfully.",
        "pattern_tags":   memory.pattern_tags,
        "section":        memory.section,
        "wisdom_score":   round(agent.wisdom_score, 2),
    }


@router.get("/progress")
async def training_progress(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AgentProfile).where(AgentProfile.user_id == current_user.id)
    )
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    sections = ["BASIC", "PAST", "PRESENT", "FUTURE"]
    section_counts = {}
    for section in sections:
        result = await db.execute(
            select(func.count(Memory.id)).where(
                Memory.agent_id == agent.id,
                Memory.section == section,
                Memory.is_active == True,
            )
        )
        section_counts[section] = result.scalar() or 0

    total = sum(section_counts.values())

    return {
        "sections":           section_counts,
        "total_memories":     total,
        "wisdom_score":       round(agent.wisdom_score or 0.0, 2),
        "estimated_accuracy": min(40 + (total * 2), 95),
    }