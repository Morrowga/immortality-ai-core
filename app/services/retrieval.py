"""
retrieval.py — optimized for parallel execution

Key change: embedding generation (OpenAI network calls) and ORM queries
now run concurrently. The raw asyncpg connection is acquired once and
reused for both vector searches sequentially — SQLAlchemy async sessions
are not safe to use concurrently for raw connection access.

Call pattern in chat.py / public.py:
    from app.services.retrieval import fetch_all_retrieval_data
    data = await fetch_all_retrieval_data(...)
    memories         = data["memories"]
    patterns         = data["patterns"]
    style            = data["style"]
    slang            = data["slang"]
    personality      = data["personality"]
    language_samples = data["language_samples"]
    conversation_history = data["conversation_history"]
    survey           = data["survey"]   # PersonalitySurvey | None (chat.py only)
"""

import asyncio
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, or_
from app.models.user import (
    PatternAbstraction, StyleProfile, RelationshipProfile,
    LanguageSample, AgentResponse, SlangDictionary,
    PersonalitySurvey,
)
from app.services.embeddings import generate_embedding_for_query


# ─────────────────────────────────────────────────────────────────────────────
# Public convenience wrapper — call this from chat.py / public.py
# ─────────────────────────────────────────────────────────────────────────────

async def fetch_all_retrieval_data(
    *, question, agent_id, user_id, db, language="en",
    zone=5, session_key="", fetch_survey=True, survey_user_id=None,
) -> dict:

    embedding_task = asyncio.create_task(
        generate_embedding_for_query(question, language=language)
    )

    orm_tasks = asyncio.gather(
        _get_style_profile(user_id, db),
        _get_slang_for_language(user_id, language, db, zone),
        _get_personality_summary(user_id, db),
        _get_language_samples(agent_id, language, db, zone),
        _get_conversation_history(agent_id, session_key, db),
        _get_survey(survey_user_id or user_id, db) if fetch_survey else _noop(),
        _get_known_people(agent_id, db),  
    )

    embedding, orm_results = await asyncio.gather(embedding_task, orm_tasks)

    style, slang, personality, language_samples, conversation_history, survey, known_people = orm_results

    embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"
    raw_conn = await db.connection()
    asyncpg_conn = await raw_conn.get_raw_connection()
    native_conn = asyncpg_conn.driver_connection

    memories = await _vector_search_memories(native_conn, embedding_str, agent_id)
    patterns = await _vector_search_patterns(native_conn, embedding_str, agent_id)

    return {
        "memories":             memories,
        "patterns":             patterns,
        "style":                style,
        "slang":                slang,
        "personality":          personality,
        "language_samples":     language_samples,
        "conversation_history": conversation_history,
        "survey":               survey,
        "known_people":         known_people, 
    }


# ─────────────────────────────────────────────────────────────────────────────
# Vector search helpers (raw asyncpg — NOT safe to run concurrently on same
# session, called sequentially after raw connection is acquired once)
# ─────────────────────────────────────────────────────────────────────────────

async def _vector_search_memories(
    native_conn,
    embedding_str: str,
    agent_id: str,
    limit: int = 10,
    min_hybrid_score: float = 0.30,
) -> list[dict]:
    rows = await native_conn.fetch("""
        SELECT
            id::text,
            created_at,
            what_happened,
            what_happened_original,
            how_i_felt,
            how_i_felt_original,
            why_it_mattered,
            why_it_mattered_original,
            what_i_learned,
            what_i_learned_original,
            instinct_formed,
            instinct_formed_original,
            cultural_expression_notes,
            feeling_weight,
            never_forget,
            is_core_memory,
            pattern_tags,
            section,
            transcript_language,
            reinforcement_count,
            1 - (embedding <=> $1::vector) AS similarity,
            (
                (1 - (embedding <=> $1::vector)) * 0.5
                + (feeling_weight / 10.0) * 0.3
                + (CASE WHEN never_forget
                        AND (1 - (embedding <=> $1::vector)) > 0.25
                        THEN 0.12 ELSE 0.0 END)
                + (CASE WHEN is_core_memory
                        AND (1 - (embedding <=> $1::vector)) > 0.20
                        THEN 0.05 ELSE 0.0 END)
                + (CASE WHEN reinforcement_count > 1
                        THEN LEAST(reinforcement_count * 0.01, 0.05) ELSE 0.0 END)
            ) AS hybrid_score
        FROM memories
        WHERE
            agent_id = $2::uuid
            AND is_active = true
            AND embedding IS NOT NULL
        ORDER BY hybrid_score DESC
        LIMIT $3
    """, embedding_str, agent_id, limit * 2)

    results = [dict(row) for row in rows]
    filtered = [r for r in results if r["hybrid_score"] >= min_hybrid_score]
    if len(filtered) < 3 and results:
        filtered = results[:3]
    return filtered[:limit]


async def _vector_search_patterns(
    native_conn,
    embedding_str: str,
    agent_id: str,
    limit: int = 3,
) -> list[dict]:
    rows = await native_conn.fetch("""
        SELECT
            pattern_summary,
            pattern_summary_original,
            pattern_type,
            abstraction_weight,
            CASE
                WHEN embedding IS NOT NULL
                THEN (1 - (embedding <=> $1::vector)) * 0.6
                     + (abstraction_weight / 10.0) * 0.4
                ELSE abstraction_weight / 10.0
            END AS relevance_score
        FROM pattern_abstractions
        WHERE agent_id = $2::uuid
        ORDER BY relevance_score DESC
        LIMIT $3
    """, embedding_str, agent_id, limit)

    return [
        {
            "pattern_summary":          r["pattern_summary"],
            "pattern_summary_original": r["pattern_summary_original"],
            "pattern_type":             r["pattern_type"],
            "abstraction_weight":       r["abstraction_weight"],
        }
        for r in rows
    ]


# ─────────────────────────────────────────────────────────────────────────────
# ORM helpers — safe to gather (no raw connection access)
# ─────────────────────────────────────────────────────────────────────────────

async def _get_style_profile(user_id: str, db: AsyncSession) -> dict:
    result = await db.execute(
        select(StyleProfile).where(StyleProfile.user_id == uuid.UUID(user_id))
    )
    style = result.scalar_one_or_none()
    if not style:
        return {}
    return {
        "avg_speaking_pace":            style.avg_speaking_pace,
        "avg_sentence_length":          style.avg_sentence_length,
        "humor_level":                  style.humor_level,
        "directness_level":             style.directness_level,
        "warmth_level":                 style.warmth_level,
        "language_primary":             style.language_primary,
        "cultural_expression_patterns": style.cultural_expression_patterns,
        "voice_fingerprint":            style.voice_fingerprint or None,
    }


async def _get_slang_for_language(
    user_id: str,
    language: str,
    db: AsyncSession,
    zone: int = None,
) -> list[dict]:
    languages_to_fetch = list({language, "en"})
    query = select(SlangDictionary).where(
        SlangDictionary.user_id == uuid.UUID(user_id),
        SlangDictionary.language.in_(languages_to_fetch),
        SlangDictionary.is_active == True,
    )
    if zone is not None:
        query = query.where(
            or_(
                SlangDictionary.relationship_zone == zone,
                SlangDictionary.relationship_zone == None,
            )
        )
    result = await db.execute(query)
    return [
        {
            "word_or_phrase":    s.word_or_phrase,
            "meanings":          s.meanings,
            "example_sentences": s.example_sentences,
            "grammar_note":      s.grammar_note,
            "usage_context":     s.usage_context,
        }
        for s in result.scalars().all()
    ]


async def _get_personality_summary(user_id: str, db: AsyncSession) -> str:
    result = await db.execute(
        select(PersonalitySurvey).where(
            PersonalitySurvey.user_id == uuid.UUID(user_id),
            PersonalitySurvey.is_completed == True,
        )
    )
    survey = result.scalar_one_or_none()
    if not survey:
        return ""
    return survey.identity_summary or ""


async def _get_language_samples(
    agent_id: str,
    language: str,
    db: AsyncSession,
    zone: int = None,
    limit: int = 8,
) -> list[str]:
    languages_to_fetch = list({language, "en"})

    if zone is not None:
        result = await db.execute(
            select(LanguageSample)
            .where(
                LanguageSample.agent_id == uuid.UUID(agent_id),
                LanguageSample.language.in_(languages_to_fetch),
                LanguageSample.relationship_zone == zone,
            )
            .order_by(desc(LanguageSample.created_at))
            .limit(limit)
        )
        samples = result.scalars().all()
        if len(samples) >= 3:
            return [s.sample_text for s in samples]

    result = await db.execute(
        select(LanguageSample)
        .where(
            LanguageSample.agent_id == uuid.UUID(agent_id),
            LanguageSample.language.in_(languages_to_fetch),
        )
        .order_by(desc(LanguageSample.created_at))
        .limit(limit)
    )
    return [s.sample_text for s in result.scalars().all()]


async def _get_conversation_history(
    agent_id: str,
    session_key: str,
    db: AsyncSession,
    limit: int = 6,
) -> list[dict]:
    if not session_key:
        return []
    result = await db.execute(
        select(AgentResponse)
        .where(
            AgentResponse.agent_id == uuid.UUID(agent_id),
            AgentResponse.session_key == session_key,
        )
        .order_by(desc(AgentResponse.created_at))
        .limit(limit)
    )
    turns = list(reversed(result.scalars().all()))
    history = []
    for turn in turns:
        if turn.question_text:
            history.append({"role": "user",      "content": turn.question_text})
        if turn.response_text:
            history.append({"role": "assistant", "content": turn.response_text})
    return history

async def _get_survey(user_id: str, db: AsyncSession):
    """Returns the PersonalitySurvey object (not just summary) for birthdate access."""
    result = await db.execute(
        select(PersonalitySurvey).where(
            PersonalitySurvey.user_id == uuid.UUID(user_id),
            PersonalitySurvey.is_completed == True,
        )
    )
    return result.scalar_one_or_none()

async def _get_installed_neo_packages(
    agent_id: str,
    db,
) -> list[dict]:
    """
    Fetch all active Neo packages for this agent.
    Called as part of fetch_all_retrieval_data() when neo_mode=True.
    Returns list of dicts ready for match_query_to_packages().
    """
    from app.models.user import NeoPackage
    from sqlalchemy import select
    import uuid
 
    result = await db.execute(
        select(NeoPackage).where(
            NeoPackage.agent_id == uuid.UUID(agent_id),
            NeoPackage.is_active == True,
        ).order_by(NeoPackage.slot_number)
    )
    packages = result.scalars().all()
 
    return [
        {
            "id":                   str(pkg.id),
            "package_type":         pkg.package_type,
            "package_key":          pkg.package_key,
            "title":                pkg.title,
            "slot_number":          pkg.slot_number,
            "custom_instructions":  pkg.custom_instructions,
            "domain_tags":          pkg.domain_tags or [],
            "neo_mode_disclaimer":  pkg.neo_mode_disclaimer,
        }
        for pkg in packages
    ]


async def _noop():
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Legacy individual functions — kept for backward compatibility with any other
# callers (training.py, etc.) that import them directly
# ─────────────────────────────────────────────────────────────────────────────

async def find_relevant_memories(
    question: str,
    agent_id: str,
    db: AsyncSession,
    limit: int = 10,
    min_hybrid_score: float = 0.30,
    language: str = "en",
) -> list[dict]:
    question_embedding = await generate_embedding_for_query(question, language=language)
    embedding_str = "[" + ",".join(str(x) for x in question_embedding) + "]"
    raw_conn = await db.connection()
    asyncpg_conn = await raw_conn.get_raw_connection()
    native_conn = asyncpg_conn.driver_connection
    return await _vector_search_memories(native_conn, embedding_str, agent_id, limit, min_hybrid_score)


async def find_relevant_patterns(
    question: str,
    agent_id: str,
    db: AsyncSession,
    limit: int = 3,
    language: str = "en",
) -> list[dict]:
    question_embedding = await generate_embedding_for_query(question, language=language)
    embedding_str = "[" + ",".join(str(x) for x in question_embedding) + "]"
    raw_conn = await db.connection()
    asyncpg_conn = await raw_conn.get_raw_connection()
    native_conn = asyncpg_conn.driver_connection
    return await _vector_search_patterns(native_conn, embedding_str, agent_id, limit)


async def get_style_profile(user_id: str, db: AsyncSession) -> dict:
    return await _get_style_profile(user_id, db)


async def get_slang_for_language(
    user_id: str, language: str, db: AsyncSession, zone: int = None
) -> list[dict]:
    return await _get_slang_for_language(user_id, language, db, zone)


async def get_personality_summary(user_id: str, db: AsyncSession) -> str:
    return await _get_personality_summary(user_id, db)


async def get_language_samples(
    agent_id: str, language: str, db: AsyncSession,
    zone: int = None, limit: int = 8,
) -> list[str]:
    return await _get_language_samples(agent_id, language, db, zone, limit)


async def get_conversation_history(
    agent_id: str, session_key: str, db: AsyncSession, limit: int = 6,
) -> list[dict]:
    return await _get_conversation_history(agent_id, session_key, db, limit)

async def _get_known_people(agent_id: str, db: AsyncSession) -> list[dict]:
    result = await db.execute(
        select(RelationshipProfile)
        .where(
            RelationshipProfile.agent_id == uuid.UUID(agent_id),
            RelationshipProfile.is_active == True,
        )
        .order_by(RelationshipProfile.zone, RelationshipProfile.person_name)
    )
    people = result.scalars().all()

    return [
        {
            "person_name":    p.person_name,
            "person_aliases": p.person_aliases or [],
            "person_role":    p.person_role or "",
            "zone":           p.zone,
            "address_forms":  p.address_forms or [],   # ← add this
        }
        for p in people
    ]