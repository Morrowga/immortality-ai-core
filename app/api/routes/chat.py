import asyncio
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
import uuid

from app.db.session import get_db
from app.models.user import (
    User, AgentProfile, AgentResponse, AgentLifecycle,
    RelationshipProfile, RelationshipRole, RelationshipType,
    PersonalitySurvey,
)
from app.core.security import get_current_user
from app.services.agent import generate_agent_response
from app.services.retrieval import fetch_all_retrieval_data
from app.services.survey import naturalize_response
from datetime import datetime, date
from anthropic import AsyncAnthropic
from app.core.config import settings

router = APIRouter()

# Shared client — one connection pool, reused across all Layer 3 calls
_haiku_client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

# Languages that require pronoun/honorific correction
HONORIFIC_LANGUAGES = {"my", "th", "ko", "ja", "id"}


def _first_form(forms: list[dict]) -> str:
    for f in forms or []:
        form = f.get("form", "")
        if form and form not in ("skip", "__custom__", "name"):
            return form
    return ""


# ── Age gap computation ────────────────────────────────────────────────────

def _compute_age_gap(speaker_age: int, owner_birthdate: str | None) -> int | None:
    if not owner_birthdate:
        return None
    try:
        from dateutil import parser as dateparser
        owner_dob = dateparser.parse(owner_birthdate).date()
    except Exception:
        try:
            year = int(str(owner_birthdate).strip()[:4])
            owner_dob = date(year, 1, 1)
        except Exception:
            return None

    today = date.today()
    owner_age = today.year - owner_dob.year - (
        (today.month, today.day) < (owner_dob.month, owner_dob.day)
    )
    return speaker_age - owner_age


# ── Address form picker ────────────────────────────────────────────────────

def _pick_address_form_deterministic(
    address_forms: list[dict],
    speaker_gender: str | None,
    speaker_actual_age: int | None,
    age_gap: int | None,
    speaker_name: str = "",
) -> str:
    if not address_forms:
        return speaker_name or ""

    valid = [
        f for f in address_forms
        if f.get("form") and f["form"] not in ("skip", "__custom__")
    ]
    if not valid:
        return speaker_name or ""

    if len(valid) == 1:
        f = valid[0]["form"]
        return speaker_name if f == "name" else f

    gender_lower = (speaker_gender or "").lower()
    age = speaker_actual_age
    gap = age_gap

    import re

    def score(entry: dict) -> int:
        ctx = (entry.get("context", "") or "").lower().strip()
        form = entry.get("form", "")

        if ctx == "always":
            return 1

        s = 0

        ctx_has_male   = any(k in ctx for k in ["male", " man", " boy", " m ", "( m)"])
        ctx_has_female = any(k in ctx for k in ["female", "fermale", " woman", " girl", " f ", "( f)"])

        if gender_lower == "male":
            if ctx_has_female and not ctx_has_male:
                return -1
            if ctx_has_male:
                s += 10
        elif gender_lower == "female":
            if ctx_has_male and not ctx_has_female:
                return -1
            if ctx_has_female:
                s += 10

        use_age = age

        range_match = re.search(r'(\d+)\s*[-–]\s*(\d+)', ctx)
        if range_match and use_age is not None:
            lo, hi = int(range_match.group(1)), int(range_match.group(2))
            if lo <= use_age <= hi:
                s += 20
            else:
                s -= 5

        over_match = re.search(r'(\d+)\s*(?:or|and)?\s*over', ctx)
        if not over_match:
            over_match = re.search(r'over\s*(\d+)', ctx)
        if over_match and use_age is not None:
            threshold = int(over_match.group(1))
            if use_age >= threshold:
                s += 20
            else:
                s -= 5

        under_match = re.search(r'(?:under|below|up to)\s*(\d+)', ctx)
        if under_match and use_age is not None:
            threshold = int(under_match.group(1))
            if use_age < threshold:
                s += 20
            else:
                s -= 5

        if use_age is None and gap is not None:
            if "younger" in ctx and gap < 0:
                s += 15
            elif "older" in ctx and gap > 0:
                gap_range = re.search(r'(\d+)\s*[-–]\s*(\d+)', ctx)
                if gap_range:
                    lo, hi = int(gap_range.group(1)), int(gap_range.group(2))
                    if lo <= abs(gap) <= hi:
                        s += 15
                else:
                    s += 8

        return s

    scored = [(score(f), f) for f in valid]
    print(f"[PICK SCORES] age={age} gap={gap} gender={gender_lower}: "
          + str([(f['form'], sc) for sc, f in scored]))

    candidates = [(sc, f) for sc, f in scored if sc >= 0]
    if not candidates:
        candidates = scored

    best_score, best_form = max(candidates, key=lambda x: x[0])
    form = best_form["form"]
    return speaker_name if form == "name" else form


async def _pick_address_form(
    address_forms: list[dict],
    speaker_gender: str | None,
    age_gap: int | None,
    speaker_name: str = "",
    speaker_actual_age: int | None = None,
    owner_age: int | None = None,
    owner_name: str = "",
    person_role: str = "",
) -> str:
    return _pick_address_form_deterministic(
        address_forms      = address_forms,
        speaker_gender     = speaker_gender,
        speaker_actual_age = speaker_actual_age,
        age_gap            = age_gap,
        speaker_name       = speaker_name,
    )


# ── Request schema ─────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    language: str = "en"
    speaker_name: str = ""
    role_id: Optional[str] = None
    person_id: Optional[str] = None
    session_key: Optional[str] = None
    speaker_gender: Optional[str] = None
    speaker_age: Optional[int] = None


# ── Speaker context resolver ───────────────────────────────────────────────

async def _resolve_speaker_context(
    speaker_name: str,
    role_id: Optional[str],
    person_id: Optional[str],
    agent_id: uuid.UUID,
    db: AsyncSession,
) -> dict:
    person = None
    role = None

    if person_id:
        result = await db.execute(
            select(RelationshipProfile).where(
                RelationshipProfile.id == uuid.UUID(person_id),
                RelationshipProfile.agent_id == agent_id,
                RelationshipProfile.is_active == True,
            )
        )
        person = result.scalar_one_or_none()

    if person and person.role_id:
        result = await db.execute(
            select(RelationshipRole).where(RelationshipRole.id == person.role_id)
        )
        role = result.scalar_one_or_none()
    elif role_id:
        result = await db.execute(
            select(RelationshipRole).where(
                RelationshipRole.id == uuid.UUID(role_id),
                RelationshipRole.agent_id == agent_id,
            )
        )
        role = result.scalar_one_or_none()

    address_forms = (
        (person.address_forms if person and person.address_forms else None)
        or (role.address_forms if role else None)
        or []
    )
    self_address_forms = (
        (person.self_address_forms if person and person.self_address_forms else None)
        or (role.self_address_forms if role else None)
        or []
    )
    forbidden = (
        (person.forbidden_particles if person and person.forbidden_particles else None)
        or (role.forbidden_particles if role else None)
        or []
    )
    required = (
        (person.required_particles if person and person.required_particles else None)
        or (role.required_particles if role else None)
        or []
    )
    allowed_endings = (
        (person.allowed_endings if person and person.allowed_endings else None)
        or (role.allowed_endings if role else None)
        or []
    )
    tone = (
        (person.tone_description if person and person.tone_description else None)
        or (role.tone_description if role else None)
        or "Polite and measured."
    )

    voice_summary = person.voice_summary if person else None
    zone = person.zone if person else (5 if not role else _role_zone(role))
    formality = (
        (person.formality_level if person else None)
        or (role.formality_level if role else 7.0)
    )
    openness = (
        (person.openness_level if person else None)
        or (role.openness_level if role else 2.0)
    )
    warmth    = (person.warmth_level    if person else None) or (getattr(role, "warmth_level",    None) if role else None) or 5.0
    humor     = (person.humor_level     if person else None) or (getattr(role, "humor_level",     None) if role else None) or 5.0
    affection = (person.affection_level if person else None) or (getattr(role, "affection_level", None) if role else None) or 5.0

    relationship_context = f"{speaker_name} is talking to you."
    if role:
        relationship_context = f"This is your {role.name}. {tone}"
    if person and person.person_role:
        relationship_context = f"{person.person_role}. {tone}"

    person_gender = person.gender if person else None
    person_age    = person.age    if person else None

    return {
        "zone":                zone,
        "address_forms":       address_forms,
        "self_address_forms":  self_address_forms,
        "forbidden_particles": forbidden,
        "required_particles":  required,
        "allowed_endings":     allowed_endings,
        "tone_description":    tone,
        "voice_summary":       voice_summary,
        "relationship_context": relationship_context,
        "formality_level":     formality,
        "openness_level":      openness,
        "warmth_level":        warmth,
        "humor_level":         humor,
        "affection_level":     affection,
        "role_name":           role.name if role else "Stranger",
        "person_role_text":    (person.person_role or "") if person else "",
        "person_gender":       person_gender,
        "person_age":          person_age,
    }


def _role_zone(role: RelationshipRole) -> int:
    if role.affection_level >= 9:
        return 1
    if role.formality_level <= 3 and role.openness_level >= 8:
        return 3
    if role.formality_level >= 7:
        return 4
    return 4


# ── Chat endpoint ──────────────────────────────────────────────────────────

@router.post("/")
async def chat(
    data:         ChatRequest,
    current_user: User         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    if not data.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    if not data.speaker_name.strip():
        raise HTTPException(
            status_code=400,
            detail="speaker_name is required. Call /api/relationships/identify first."
        )

    result = await db.execute(
        select(AgentProfile).where(AgentProfile.user_id == current_user.id)
    )
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    if not agent.survey_completed:
        raise HTTPException(
            status_code=403,
            detail="Complete your personality survey first before chatting."
        )

    response_language = data.language or current_user.language

    ctx = await _resolve_speaker_context(
        speaker_name=data.speaker_name,
        role_id=data.role_id,
        person_id=data.person_id,
        agent_id=agent.id,
        db=db,
    )

    is_owner = not data.role_id and not data.person_id

    effective_gender = data.speaker_gender or ctx.get("person_gender")
    effective_age    = data.speaker_age    or ctx.get("person_age")

    retrieval = await fetch_all_retrieval_data(
        question=data.message,
        agent_id=str(agent.id),
        user_id=str(current_user.id),
        db=db,
        language=response_language,
        zone=ctx["zone"],
        session_key=data.session_key or "",
        fetch_survey=True,
        survey_user_id=str(current_user.id),
    )

    memories             = retrieval["memories"]
    patterns             = retrieval["patterns"]
    style                = retrieval["style"]
    slang                = retrieval["slang"]
    personality          = retrieval["personality"]
    language_samples     = retrieval["language_samples"]
    conversation_history = retrieval["conversation_history"]
    survey               = retrieval["survey"]
    known_people         = retrieval["known_people"]
    ambiguity            = retrieval["ambiguity"]

    owner_age:       int | None = survey.age       if survey else None
    owner_birthdate: str | None = survey.birthdate if survey else None

    age_gap: int | None = None
    if effective_age is not None:
        age_gap = _compute_age_gap(effective_age, owner_birthdate)
        if age_gap is None:
            age_gap = effective_age

    resolved_address = await _pick_address_form(
        address_forms      = ctx["address_forms"],
        speaker_gender     = effective_gender,
        age_gap            = age_gap,
        speaker_name       = data.speaker_name,
        speaker_actual_age = effective_age,
        owner_age          = owner_age,
        owner_name         = current_user.name,
        person_role        = ctx["person_role_text"] or ctx["relationship_context"],
    )

    print(f"[RESOLVED] {resolved_address}")

    relationship_profile = {
        "zone":               ctx["zone"],
        "person_name":        data.speaker_name,
        "person_role":        ctx["relationship_context"],
        "relationship_language": response_language,
        "address_forms":      ctx["address_forms"],
        "self_address_forms": ctx["self_address_forms"],
        "resolved_address":   resolved_address,
        "voice_summary":      ctx["voice_summary"],
        "openness_level":     ctx["openness_level"],
        "warmth_level":       ctx.get("warmth_level", 5.0),
        "humor_level":        ctx.get("humor_level", 5.0),
        "formality_level":    ctx["formality_level"],
        "affection_level":    ctx.get("affection_level", 5.0),
        "allowed_topics":     [],
        "restricted_topics":  [],
        "forbidden_particles": ctx["forbidden_particles"],
    }

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
        speaker_name         = data.speaker_name,
        is_owner             = is_owner,
        relationship_context = ctx["relationship_context"],
        relationship_profile = relationship_profile,
        conversation_history = conversation_history,
        language_samples     = language_samples,
        known_people         = known_people, 
        ambiguity            = ambiguity,
    )

    print(f"[L1 DRAFT] {draft}")

    # ── Layer 2: Naturalize ───────────────────────────────────────────────
    naturalized = await naturalize_response(
        draft_response             = draft,
        language                   = response_language,
        real_samples               = language_samples,
        zone                       = ctx["zone"],
        relationship_voice_summary = ctx["voice_summary"] or "",
    )

    print(f"[L2 NATURALIZED] {naturalized}")

    # ── Layer 3: Pronoun correction ───────────────────────────────────────
    response_text = await _correct_pronouns(
        response            = naturalized,
        language            = response_language,
        address_forms       = ctx["address_forms"],
        self_address_forms  = ctx["self_address_forms"],
        forbidden_particles = ctx["forbidden_particles"],
        required_particles  = ctx["required_particles"],
        speaker_name        = data.speaker_name,
        speaker_gender      = effective_gender,
        speaker_age         = age_gap,
        resolved_address    = resolved_address,
    )

    print(f"[L3 CORRECTED] {response_text}")

    # ── Save ──────────────────────────────────────────────────────────────
    # Owner chat is for testing only — no conversation memory extraction.
    agent_response = AgentResponse(
        user_id       = current_user.id,
        agent_id      = agent.id,
        response_text = response_text,
        question_text = data.message,
        speaker_name  = data.speaker_name,
        session_key   = data.session_key,
        response_type = "chat",
    )
    db.add(agent_response)

    result = await db.execute(
        select(AgentLifecycle).where(AgentLifecycle.agent_id == agent.id)
    )
    lifecycle = result.scalar_one_or_none()
    if lifecycle:
        lifecycle.interaction_count = (lifecycle.interaction_count or 0) + 1
        lifecycle.last_active_at    = datetime.utcnow()

    await db.commit()

    return {
        "response":      response_text,
        "memories_used": len(memories),
        "patterns_used": len(patterns),
        "response_id":   str(agent_response.id),
        "role_used":     ctx["role_name"],
        "zone":          ctx["zone"],
    }


# ── Layer 3: Pronoun correction ────────────────────────────────────────────

async def _correct_pronouns(
    response: str,
    language: str,
    address_forms: list[dict],
    self_address_forms: list[dict],
    forbidden_particles: list[str],
    required_particles: list[str],
    speaker_name: str,
    speaker_gender: str | None = None,
    speaker_age: int | None = None,
    resolved_address: str | None = None,
) -> str:
    if language not in HONORIFIC_LANGUAGES:
        return response

    if not forbidden_particles and not address_forms and not self_address_forms and not resolved_address:
        return response

    speaker_context_parts = []
    if speaker_gender and speaker_gender != "prefer_not":
        speaker_context_parts.append(f"gender: {speaker_gender}")
    if speaker_age is not None:
        if speaker_age > 0:
            speaker_context_parts.append(f"speaker is {speaker_age} year(s) OLDER than the agent owner")
        elif speaker_age < 0:
            speaker_context_parts.append(f"speaker is {abs(speaker_age)} year(s) YOUNGER than the agent owner")
        else:
            speaker_context_parts.append("speaker is the same age as the agent owner")

    _ = address_forms

    if self_address_forms:
        self_lines = "\n".join(
            f"  - Use \"{f['form']}\" when: {f['context']}"
            for f in self_address_forms
        )
        self_block = f"How to refer to yourself:\n{self_lines}"
    else:
        self_block = "Refer to yourself naturally."

    forbidden_str = ", ".join(forbidden_particles) if forbidden_particles else "none"

    from app.language_packs import get_pronoun_rules
    pronoun_rules = get_pronoun_rules(language)
    pack_block = f"\nAdditional language rules:\n{pronoun_rules}\n" if pronoun_rules else ""

    prompt = f"""Fix the honorific/pronoun in this message. Preserve everything else exactly.

CORRECT address form: "{resolved_address or _first_form(address_forms) or 'skip'}"
Replace ANY other honorific directed at the speaker with this form.

FORBIDDEN words (never use toward this person): {forbidden_str}

{self_block}
{pack_block}
Output ONLY the final corrected message.
NO explanations. NO notes. NO "Wait". NO reasoning. NO self-correction narration.
If you catch yourself writing anything other than the message — stop and delete it.

Message:
{response}"""

    try:
        result = await _haiku_client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=800,
            messages=[{"role": "user", "content": prompt}],
        )
        corrected = result.content[0].text.strip()
        print(f"[L3 RAW] {repr(corrected)}")
        return corrected if corrected else response
    except Exception:
        return response