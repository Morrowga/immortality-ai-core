"""
app/api/routes/public.py

Changes from previous version:
  - Added BackgroundTasks to public_chat endpoint signature
  - After db.commit(), count session turns and fire conversation
    memory extraction every 6 turns as a background task
  - Everything else unchanged
"""

import re
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from jose import jwt, JWTError
from passlib.context import CryptContext
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.core.config import settings
from app.db.session import get_db, AsyncSessionLocal
from app.models.user import (
    AgentProfile, AgentLifecycle, AgentResponse,
    RelationshipProfile, RelationshipRole,
    PersonalitySurvey,
)
from app.services.agent import generate_agent_response
from app.services.retrieval import fetch_all_retrieval_data
from app.services.survey import naturalize_response
from app.services.conversation_memory import maybe_extract_conversation_memory

router  = APIRouter()
pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

_ALGORITHM          = "HS256"
_TOKEN_EXPIRY_HOURS = 24


# ── Pydantic schemas ───────────────────────────────────────────────────────

class VerifyRequest(BaseModel):
    passphrase: str

class PublicChatRequest(BaseModel):
    message:        str
    session_token:  str
    speaker_name:   Optional[str] = ""
    speaker_gender: Optional[str] = None
    speaker_age:    Optional[int] = None
    session_key:    Optional[str] = None

class SlugUpdateRequest(BaseModel):
    slug: str


# ── JWT helpers ────────────────────────────────────────────────────────────

def _create_session_token(payload: dict) -> str:
    data = dict(payload)
    data["exp"] = datetime.now(timezone.utc) + timedelta(hours=_TOKEN_EXPIRY_HOURS)
    return jwt.encode(data, settings.SECRET_KEY, algorithm=_ALGORITHM)


def _decode_session_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[_ALGORITHM])
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid or expired session token: {e}")


# ── Slug helpers ───────────────────────────────────────────────────────────

def _slugify(text: str) -> str:
    slug = text.lower().strip()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"\s+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug or "agent"


async def _get_agent_by_slug(slug: str, db: AsyncSession) -> AgentProfile:
    result = await db.execute(
        select(AgentProfile).where(AgentProfile.slug == slug)
    )
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found. Check the link.")
    return agent


# ── GET /public/{slug} ────────────────────────────────────────────────────

@router.get("/{slug}")
async def get_public_agent_info(slug: str, db: AsyncSession = Depends(get_db)):
    agent = await _get_agent_by_slug(slug, db)

    result = await db.execute(
        select(PersonalitySurvey).where(
            PersonalitySurvey.agent_id    == agent.id,
            PersonalitySurvey.is_completed == True,
        )
    )
    survey = result.scalar_one_or_none()

    from app.models.user import User
    result = await db.execute(select(User).where(User.id == agent.user_id))
    owner = result.scalar_one_or_none()
    owner_first_name = (owner.name or "").split()[0] if owner else ""

    return {
        "agent_name":       agent.agent_name,
        "owner_first_name": owner_first_name,
        "slug":             agent.slug,
        "is_ready":         bool(survey),
        "total_memories":   agent.total_memories or 0,
    }


# ── POST /public/{slug}/verify ────────────────────────────────────────────

@router.post("/{slug}/verify")
async def verify_passphrase(slug: str, data: VerifyRequest, db: AsyncSession = Depends(get_db)):
    agent = await _get_agent_by_slug(slug, db)

    passphrase = (data.passphrase or "").strip()
    if not passphrase:
        raise HTTPException(status_code=400, detail="Passphrase is required.")

    result = await db.execute(
        select(RelationshipProfile).where(
            RelationshipProfile.agent_id           == agent.id,
            RelationshipProfile.is_active          == True,
            RelationshipProfile.access_key_enabled == True,
            RelationshipProfile.access_key_hash    != None,
        )
    )
    profiles = result.scalars().all()

    if not profiles:
        raise HTTPException(status_code=403, detail="No access keys configured for this agent.")

    matched: RelationshipProfile | None = None
    for profile in profiles:
        if profile.access_key_hash and pwd_ctx.verify(passphrase, profile.access_key_hash):
            matched = profile
            break

    if not matched:
        raise HTTPException(status_code=403, detail="Invalid passphrase. Contact the owner for your access key.")

    role: RelationshipRole | None = None
    if matched.role_id:
        r_result = await db.execute(
            select(RelationshipRole).where(RelationshipRole.id == matched.role_id)
        )
        role = r_result.scalar_one_or_none()

    token_payload = {
        "agent_id":        str(agent.id),
        "profile_id":      str(matched.id),
        "zone":            matched.zone,
        "role_id":         str(matched.role_id) if matched.role_id else None,
        "role_name":       role.name if role else "Guest",
        "role_name_local": role.name_local if role else None,
        "person_name":     matched.person_name,
        "language":        matched.relationship_language or "en",
    }
    token = _create_session_token(token_payload)

    return {
        "session_token":    token,
        "person_name":      matched.person_name,
        "role_name":        role.name if role else "Guest",
        "role_name_local":  role.name_local if role else None,
        "zone":             matched.zone,
        "expires_in_hours": _TOKEN_EXPIRY_HOURS,
        "person_gender":    matched.gender,
        "person_age":       matched.age,
    }


# ── POST /public/{slug}/chat ──────────────────────────────────────────────

@router.post("/{slug}/chat")
async def public_chat(
    slug:             str,
    data:             PublicChatRequest,
    background_tasks: BackgroundTasks,           # ← fires memory extraction after response
    db:               AsyncSession = Depends(get_db),
):
    if not data.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    claims     = _decode_session_token(data.session_token)
    agent_id   = claims["agent_id"]
    profile_id = claims["profile_id"]
    zone       = claims.get("zone", 5)
    role_id    = claims.get("role_id")
    person_name_from_token = claims.get("person_name", "")

    agent = await _get_agent_by_slug(slug, db)
    if str(agent.id) != agent_id:
        raise HTTPException(status_code=403, detail="Session token does not match this agent.")

    # ── Load profile + role ───────────────────────────────────────────────
    result = await db.execute(
        select(RelationshipProfile).where(
            RelationshipProfile.id                 == uuid.UUID(profile_id),
            RelationshipProfile.agent_id           == agent.id,
            RelationshipProfile.is_active          == True,
            RelationshipProfile.access_key_enabled == True,
        )
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=403, detail="Your access has been revoked. Contact the owner.")

    role: RelationshipRole | None = None
    if role_id:
        r_result = await db.execute(
            select(RelationshipRole).where(RelationshipRole.id == uuid.UUID(role_id))
        )
        role = r_result.scalar_one_or_none()

    speaker_name = (data.speaker_name or "").strip() or person_name_from_token

    # ── Pronoun rules — person overrides role if person field is non-empty ─
    addr_forms = profile.address_forms or (role.address_forms if role else []) or []
    self_forms = profile.self_address_forms or (role.self_address_forms if role else []) or []

    forbidden = (
        (profile.forbidden_particles if profile.forbidden_particles else None)
        or (role.forbidden_particles if role else None)
        or []
    )
    required = (
        (profile.required_particles if profile.required_particles else None)
        or (role.required_particles if role else None)
        or []
    )
    allowed_endings = (
        (profile.allowed_endings if profile.allowed_endings else None)
        or (role.allowed_endings if role else None)
        or []
    )
    tone = (
        (profile.tone_description if profile.tone_description else None)
        or (role.tone_description if role else None)
        or "Polite and measured."
    )

    # ── Gender/age: request → profile fallback ────────────────────────────
    effective_gender = data.speaker_gender or profile.gender
    effective_age    = data.speaker_age    or profile.age

    # ── Owner info + language ─────────────────────────────────────────────
    from app.models.user import User
    owner_result = await db.execute(select(User).where(User.id == agent.user_id))
    owner = owner_result.scalar_one_or_none()
    owner_language    = (owner.language or "en") if owner else "en"
    response_language = profile.relationship_language or owner_language

    # ── Survey for owner birthdate (age gap) ──────────────────────────────
    survey_result = await db.execute(
        select(PersonalitySurvey).where(
            PersonalitySurvey.agent_id     == agent.id,
            PersonalitySurvey.is_completed == True,
        )
    )
    survey = survey_result.scalar_one_or_none()
    owner_birthdate: str | None = survey.birthdate if survey else None

    # ── Age gap + address form ────────────────────────────────────────────
    age_gap: int | None = None
    if effective_age is not None:
        from app.api.routes.chat import _compute_age_gap
        age_gap = _compute_age_gap(effective_age, owner_birthdate)
        if age_gap is None:
            age_gap = effective_age

    from app.api.routes.chat import _pick_address_form_deterministic
    resolved_address = _pick_address_form_deterministic(
        address_forms      = addr_forms,
        speaker_gender     = effective_gender,
        speaker_actual_age = effective_age,
        age_gap            = age_gap,
        speaker_name       = speaker_name,
    )

    # ── Parallel retrieval ────────────────────────────────────────────────
    retrieval = await fetch_all_retrieval_data(
        question=data.message,
        agent_id=str(agent.id),
        user_id=str(agent.user_id),
        db=db,
        language=response_language,
        zone=zone,
        session_key=data.session_key or "",
        fetch_survey=False,
    )

    memories             = retrieval["memories"]
    patterns             = retrieval["patterns"]
    style                = retrieval["style"]
    slang                = retrieval["slang"]
    personality          = retrieval["personality"]
    language_samples     = retrieval["language_samples"]
    conversation_history = retrieval["conversation_history"]
    known_people         = retrieval["known_people"]

    # ── Build relationship profile dict ───────────────────────────────────
    relationship_profile = {
        "zone":               zone,
        "person_name":        speaker_name,
        "person_role":        profile.person_role or (role.name if role else "Guest"),
        "relationship_language": response_language,
        "address_forms":      addr_forms,
        "self_address_forms": self_forms,
        "resolved_address":   resolved_address,
        "voice_summary":      profile.voice_summary,
        "openness_level":     profile.openness_level,
        "warmth_level":       profile.warmth_level,
        "humor_level":        profile.humor_level,
        "formality_level":    profile.formality_level,
        "affection_level":    profile.affection_level,
        "allowed_topics":     [],
        "restricted_topics":  profile.restricted_topics or [],
        "forbidden_particles": forbidden,
    }

    from app.api.routes.chat import _correct_pronouns

    # ── Layer 1: Sonnet ───────────────────────────────────────────────────
    draft = await generate_agent_response(
        question             = data.message,
        memories             = memories,
        patterns             = patterns,
        style                = style,
        agent_name           = agent.agent_name,
        language             = response_language,
        slang                = slang,
        personality          = personality,
        speaker_name         = speaker_name,
        is_owner             = False,
        relationship_context = profile.person_role or (role.name if role else ""),
        relationship_profile = relationship_profile,
        conversation_history = conversation_history,
        language_samples     = language_samples,
        known_people         = known_people, 
    )

    # ── Layer 2: Naturalize ───────────────────────────────────────────────
    naturalized = await naturalize_response(
        draft_response             = draft,
        language                   = response_language,
        real_samples               = language_samples,
        zone                       = zone,
        relationship_voice_summary = profile.voice_summary or "",
    )

    # ── Layer 3: Pronoun correction ───────────────────────────────────────
    response_text = await _correct_pronouns(
        response            = naturalized,
        language            = response_language,
        address_forms       = addr_forms,
        self_address_forms  = self_forms,
        forbidden_particles = forbidden,
        required_particles  = required,
        speaker_name        = speaker_name,
        speaker_gender      = effective_gender,
        speaker_age         = age_gap,
        resolved_address    = resolved_address,
    )

    # ── Save ──────────────────────────────────────────────────────────────
    agent_response = AgentResponse(
        user_id       = agent.user_id,
        agent_id      = agent.id,
        response_text = response_text,
        question_text = data.message,
        speaker_name  = speaker_name,
        session_key   = data.session_key,
        response_type = "public_chat",
    )
    db.add(agent_response)

    lc_result = await db.execute(
        select(AgentLifecycle).where(AgentLifecycle.agent_id == agent.id)
    )
    lifecycle = lc_result.scalar_one_or_none()
    if lifecycle:
        lifecycle.interaction_count = (lifecycle.interaction_count or 0) + 1
        lifecycle.last_active_at    = datetime.utcnow()

    await db.commit()

    # ── Conversation memory extraction ────────────────────────────────────
    # Fires every 6 turns as a background task — zero latency impact.
    # Only public chat extracts memories (owner chat is for testing only).
    if data.session_key:
        turn_count_result = await db.execute(
            select(func.count(AgentResponse.id)).where(
                AgentResponse.agent_id    == agent.id,
                AgentResponse.session_key == data.session_key,
            )
        )
        turn_count = turn_count_result.scalar() or 0

        background_tasks.add_task(
            maybe_extract_conversation_memory,
            session_key = data.session_key,
            agent_id    = str(agent.id),
            user_id     = str(agent.user_id),
            turn_count  = turn_count,
            db_factory  = AsyncSessionLocal,
        )

    return {
        "response":      response_text,
        "memories_used": len(memories),
        "patterns_used": len(patterns),
        "response_id":   str(agent_response.id),
        "zone":          zone,
        "speaker_name":  speaker_name,
    }


# ── GET /public/{slug}/voice ──────────────────────────────────────────────

@router.get("/{slug}/voice")
async def public_voice_status(slug: str, db: AsyncSession = Depends(get_db)):
    from app.core.config import settings as app_settings
    voice_enabled = str(getattr(app_settings, "VOICE_ENABLED", "false")).lower() == "true"

    if not voice_enabled:
        return {"enabled": False, "native": {"trained": False}}

    agent = await _get_agent_by_slug(slug, db)

    from app.models.user import VoiceSample
    result = await db.execute(
        select(VoiceSample).where(
            VoiceSample.user_id       == agent.user_id,
            VoiceSample.language_slot == "native",
        )
    )
    sample = result.scalar_one_or_none()

    return {
        "enabled": True,
        "native": {
            "trained":  bool(sample and sample.elevenlabs_voice_id),
            "voice_id": sample.elevenlabs_voice_id if sample else None,
        },
    }


# ── PATCH /public/slug ────────────────────────────────────────────────────

from app.core.security import get_current_user
from app.models.user import User

@router.patch("/slug")
async def update_agent_slug(
    data:         SlugUpdateRequest,
    current_user: User         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    raw_slug = data.slug.strip().lower()

    if not re.match(r"^[a-z0-9][a-z0-9-]{1,48}[a-z0-9]$", raw_slug):
        raise HTTPException(
            status_code=400,
            detail="Slug must be 3-50 characters, letters/numbers/hyphens only, no leading/trailing hyphens."
        )

    result = await db.execute(
        select(AgentProfile).where(AgentProfile.slug == raw_slug)
    )
    existing = result.scalar_one_or_none()
    if existing and existing.user_id != current_user.id:
        raise HTTPException(status_code=409, detail="This slug is already taken. Try a different one.")

    result = await db.execute(
        select(AgentProfile).where(AgentProfile.user_id == current_user.id)
    )
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    agent.slug = raw_slug
    await db.commit()

    return {
        "slug":       agent.slug,
        "public_url": f"/{agent.slug}",
        "message":    "Slug updated. Share this link with your people.",
    }

@router.get("/{slug}/image")
async def get_public_agent_image(slug: str, db: AsyncSession = Depends(get_db)):
    """
    Serve the agent's profile image publicly — no auth required.
    Returns 404 if the agent has no image (frontend falls back to letter avatar).
    """
    from fastapi.responses import FileResponse
    from pathlib import Path
    import os

    agent = await _get_agent_by_slug(slug, db)

    if not agent.image_path or not os.path.exists(agent.image_path):
        raise HTTPException(status_code=404, detail="No image found.")

    ext_to_mime = {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".png": "image/png",  ".webp": "image/webp",
        ".gif": "image/gif",
    }
    ext   = Path(agent.image_path).suffix.lower()
    media = ext_to_mime.get(ext, "image/jpeg")

    return FileResponse(path=agent.image_path, media_type=media)