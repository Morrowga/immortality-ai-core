from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
import uuid
from datetime import datetime

from app.db.session import get_db
from app.models.user import (
    User, AgentProfile, RelationshipType,
    RelationshipRole, RelationshipProfile,
)
from app.core.security import get_current_user

router = APIRouter()


# ── Pydantic schemas ───────────────────────────────────────────────────────

class TypeCreate(BaseModel):
    name: str
    name_local: Optional[str] = None

class TypeUpdate(BaseModel):
    name: Optional[str] = None
    name_local: Optional[str] = None
    sort_order: Optional[int] = None

class RoleCreate(BaseModel):
    type_id: str
    name: str
    name_local: Optional[str] = None
    address_forms: Optional[list[dict]] = []
    self_address_forms: Optional[list[dict]] = []
    forbidden_particles: Optional[list[str]] = []
    required_particles: Optional[list[str]] = []
    allowed_endings: Optional[list[str]] = []
    tone_description: Optional[str] = None
    openness_level: Optional[float] = 5.0
    formality_level: Optional[float] = 5.0
    affection_level: Optional[float] = 5.0
    restricted_topics: Optional[list[str]] = []

class RoleUpdate(BaseModel):
    name: Optional[str] = None
    name_local: Optional[str] = None
    address_forms: Optional[list[dict]] = None
    self_address_forms: Optional[list[dict]] = None
    forbidden_particles: Optional[list[str]] = None
    required_particles: Optional[list[str]] = None
    allowed_endings: Optional[list[str]] = None
    tone_description: Optional[str] = None
    openness_level: Optional[float] = None
    formality_level: Optional[float] = None
    affection_level: Optional[float] = None
    restricted_topics: Optional[list[str]] = None

class PersonCreate(BaseModel):
    role_id: str
    person_name: str
    person_aliases: Optional[list[str]] = []
    person_role: Optional[str] = None
    relationship_language: Optional[str] = None
    how_i_talk_to_them: Optional[str] = None
    chat_samples: Optional[list[str]] = []
    address_forms: Optional[list[dict]] = []
    self_address_forms: Optional[list[dict]] = []
    # NEW — optional person-level fields
    gender: Optional[str] = None                    # "male" | "female" | "other"
    age: Optional[int] = None                       # actual age
    tone_description: Optional[str] = None          # overrides role tone if set
    forbidden_particles: Optional[list[str]] = []   # overrides role forbidden if non-empty
    required_particles: Optional[list[str]] = []    # overrides role required if non-empty
    allowed_endings: Optional[list[str]] = []       # overrides role endings if non-empty

class PersonUpdate(BaseModel):
    person_name: Optional[str] = None
    person_aliases: Optional[list[str]] = None
    person_role: Optional[str] = None
    relationship_language: Optional[str] = None
    how_i_talk_to_them: Optional[str] = None
    chat_samples: Optional[list[str]] = None
    address_forms: Optional[list[dict]] = None
    self_address_forms: Optional[list[dict]] = None
    voice_summary: Optional[str] = None
    # NEW — all optional, exclude_none=True means missing = no change
    gender: Optional[str] = None
    age: Optional[int] = None
    tone_description: Optional[str] = None
    forbidden_particles: Optional[list[str]] = None
    required_particles: Optional[list[str]] = None
    allowed_endings: Optional[list[str]] = None

class IdentifyRequest(BaseModel):
    speaker_name: Optional[str] = ""
    role_id: str
    agent_id: str


# ── Helpers ────────────────────────────────────────────────────────────────

def _role_to_dict(r: RelationshipRole) -> dict:
    return {
        "id": str(r.id),
        "type_id": str(r.type_id),
        "name": r.name,
        "name_local": r.name_local,
        "is_system_default": r.is_system_default,
        "sort_order": r.sort_order,
        "address_forms": r.address_forms or [],
        "self_address_forms": r.self_address_forms or [],
        "forbidden_particles": r.forbidden_particles or [],
        "required_particles": r.required_particles or [],
        "allowed_endings": r.allowed_endings or [],
        "tone_description": r.tone_description,
        "openness_level": r.openness_level,
        "formality_level": r.formality_level,
        "affection_level": r.affection_level,
        "restricted_topics": r.restricted_topics or [],
    }

def _person_to_dict(p: RelationshipProfile) -> dict:
    return {
        "id": str(p.id),
        "role_id": str(p.role_id) if p.role_id else None,
        "zone": p.zone,
        "person_name": p.person_name,
        "person_aliases": p.person_aliases or [],
        "person_role": p.person_role,
        "relationship_language": p.relationship_language,
        "how_i_talk_to_them": p.how_i_talk_to_them,
        "chat_samples": p.chat_samples or [],
        "address_forms": p.address_forms or [],
        "self_address_forms": p.self_address_forms or [],
        "voice_summary": p.voice_summary,
        "openness_level": p.openness_level,
        "warmth_level": p.warmth_level,
        "humor_level": p.humor_level,
        "formality_level": p.formality_level,
        "affection_level": p.affection_level,
        "restricted_topics": p.restricted_topics or [],
        # NEW fields
        "gender": p.gender,
        "age": p.age,
        "tone_description": p.tone_description,
        "forbidden_particles": p.forbidden_particles or [],
        "required_particles": p.required_particles or [],
        "allowed_endings": p.allowed_endings or [],
        # Access key status (read-only here)
        "has_key": bool(p.access_key_hash),
        "key_enabled": p.access_key_enabled,
        "key_preview": p.access_key_preview,
        "key_plain": p.access_key_plain,
    }

TYPE_ZONE_MAP = {
    "Partner": 1,
    "Family": 2,
    "Friend": 3,
    "Work": 4,
    "Stranger": 5,
}

def _first_form(forms: list[dict]) -> str:
    if forms and isinstance(forms[0], dict):
        return forms[0].get("form", "")
    return ""


# ── GET /api/relationships — full tree ────────────────────────────────────

@router.get("")
async def get_relationship_tree(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AgentProfile).where(AgentProfile.user_id == current_user.id)
    )
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    result = await db.execute(
        select(RelationshipType)
        .where(
            RelationshipType.agent_id == agent.id,
            RelationshipType.is_active == True,
        )
        .order_by(RelationshipType.sort_order)
    )
    types = result.scalars().all()

    tree = []
    for t in types:
        result = await db.execute(
            select(RelationshipRole)
            .where(
                RelationshipRole.type_id == t.id,
                RelationshipRole.is_active == True,
            )
            .order_by(RelationshipRole.sort_order)
        )
        roles = result.scalars().all()

        roles_data = []
        for r in roles:
            result = await db.execute(
                select(RelationshipProfile)
                .where(
                    RelationshipProfile.role_id == r.id,
                    RelationshipProfile.is_active == True,
                )
                .order_by(RelationshipProfile.person_name)
            )
            people = result.scalars().all()

            roles_data.append({
                **_role_to_dict(r),
                "people": [_person_to_dict(p) for p in people],
            })

        tree.append({
            "id": str(t.id),
            "name": t.name,
            "name_local": t.name_local,
            "is_system_default": t.is_system_default,
            "sort_order": t.sort_order,
            "access_mode": t.access_mode,
            "roles": roles_data,
        })

    return {"types": tree}


# ── TYPES ──────────────────────────────────────────────────────────────────

@router.post("/types")
async def create_type(
    data: TypeCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AgentProfile).where(AgentProfile.user_id == current_user.id)
    )
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    t = RelationshipType(
        agent_id=agent.id,
        user_id=current_user.id,
        name=data.name,
        name_local=data.name_local,
        is_system_default=False,
    )
    db.add(t)
    await db.commit()
    return {"id": str(t.id), "name": t.name, "name_local": t.name_local}


@router.patch("/types/{type_id}")
async def update_type(
    type_id: str,
    data: TypeUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(RelationshipType).where(
            RelationshipType.id == uuid.UUID(type_id),
            RelationshipType.user_id == current_user.id,
        )
    )
    t = result.scalar_one_or_none()
    if not t:
        raise HTTPException(status_code=404, detail="Type not found")

    # System defaults: allow renaming name_local only, not name
    if data.name and not t.is_system_default:
        t.name = data.name
    if data.name_local is not None:
        t.name_local = data.name_local
    if data.sort_order is not None:
        t.sort_order = data.sort_order

    await db.commit()
    return {"id": str(t.id), "name": t.name, "name_local": t.name_local}


@router.delete("/types/{type_id}")
async def delete_type(
    type_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(RelationshipType).where(
            RelationshipType.id == uuid.UUID(type_id),
            RelationshipType.user_id == current_user.id,
        )
    )
    t = result.scalar_one_or_none()
    if not t:
        raise HTTPException(status_code=404, detail="Type not found")
    if t.is_system_default:
        raise HTTPException(status_code=400, detail="Cannot delete system default types")

    t.is_active = False
    await db.commit()
    return {"message": "deleted"}


# ── ROLES ──────────────────────────────────────────────────────────────────

@router.post("/roles")
async def create_role(
    data: RoleCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AgentProfile).where(AgentProfile.user_id == current_user.id)
    )
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    result = await db.execute(
        select(RelationshipType).where(
            RelationshipType.id == uuid.UUID(data.type_id),
            RelationshipType.agent_id == agent.id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Type not found")

    r = RelationshipRole(
        type_id=uuid.UUID(data.type_id),
        agent_id=agent.id,
        user_id=current_user.id,
        name=data.name,
        name_local=data.name_local,
        is_system_default=False,
        address_forms=data.address_forms or [],
        self_address_forms=data.self_address_forms or [],
        forbidden_particles=data.forbidden_particles or [],
        required_particles=data.required_particles or [],
        allowed_endings=data.allowed_endings or [],
        tone_description=data.tone_description,
        openness_level=data.openness_level,
        formality_level=data.formality_level,
        affection_level=data.affection_level,
        restricted_topics=data.restricted_topics or [],
    )
    db.add(r)
    await db.commit()
    return _role_to_dict(r)


@router.patch("/roles/{role_id}")
async def update_role(
    role_id: str,
    data: RoleUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(RelationshipRole).where(
            RelationshipRole.id == uuid.UUID(role_id),
            RelationshipRole.user_id == current_user.id,
        )
    )
    r = result.scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="Role not found")

    for field, value in data.model_dump(exclude_none=True).items():
        # System defaults: allow renaming name_local only
        if field == "name" and r.is_system_default:
            continue
        setattr(r, field, value)

    r.updated_at = datetime.utcnow()
    await db.commit()
    return _role_to_dict(r)


@router.delete("/roles/{role_id}")
async def delete_role(
    role_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(RelationshipRole).where(
            RelationshipRole.id == uuid.UUID(role_id),
            RelationshipRole.user_id == current_user.id,
        )
    )
    r = result.scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="Role not found")
    if r.is_system_default:
        raise HTTPException(status_code=400, detail="Cannot delete system default roles")

    r.is_active = False
    await db.commit()
    return {"message": "deleted"}


# ── PEOPLE ─────────────────────────────────────────────────────────────────

@router.post("/people")
async def create_person(
    data: PersonCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AgentProfile).where(AgentProfile.user_id == current_user.id)
    )
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    result = await db.execute(
        select(RelationshipRole).where(
            RelationshipRole.id == uuid.UUID(data.role_id),
            RelationshipRole.agent_id == agent.id,
        )
    )
    role = result.scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    result = await db.execute(
        select(RelationshipType).where(RelationshipType.id == role.type_id)
    )
    type_obj = result.scalar_one_or_none()
    # sort_order is language-agnostic (1=Partner,2=Family,3=Friend,4=Work,5=Stranger)
    # and is the same across all language seeds — safe to use directly as zone.
    # Fallback to English name lookup for any custom types the owner created.
    if type_obj and type_obj.sort_order in (1, 2, 3, 4, 5):
        zone = type_obj.sort_order
    else:
        zone = TYPE_ZONE_MAP.get(type_obj.name if type_obj else "Stranger", 5)

    p = RelationshipProfile(
        agent_id=agent.id,
        user_id=current_user.id,
        role_id=uuid.UUID(data.role_id),
        zone=zone,
        person_name=data.person_name,
        person_aliases=data.person_aliases or [],
        person_role=data.person_role,
        relationship_language=data.relationship_language or current_user.language,
        how_i_talk_to_them=data.how_i_talk_to_them,
        chat_samples=data.chat_samples or [],
        address_forms=data.address_forms or [],
        self_address_forms=data.self_address_forms or [],
        # NEW fields
        gender=data.gender,
        age=data.age,
        tone_description=data.tone_description,
        forbidden_particles=data.forbidden_particles or [],
        required_particles=data.required_particles or [],
        allowed_endings=data.allowed_endings or [],
    )
    db.add(p)
    await db.commit()

    # Extract voice profile if owner provided enough context.
    # Runs after commit so a voice extraction failure never blocks person creation.
    if data.how_i_talk_to_them or data.chat_samples:
        try:
            from app.services.survey import extract_relationship_voice
            voice = await extract_relationship_voice(
                person_name=data.person_name,
                person_role=data.person_role or (role.name if role else ""),
                zone=zone,
                how_i_talk_to_them=data.how_i_talk_to_them or "",
                chat_samples=data.chat_samples or [],
                language=data.relationship_language or current_user.language,
            )
            if voice and voice.get("voice_summary"):
                p.voice_summary     = voice.get("voice_summary")
                p.openness_level    = voice.get("openness_level",  p.openness_level)
                p.warmth_level      = voice.get("warmth_level",    p.warmth_level)
                p.humor_level       = voice.get("humor_level",     p.humor_level)
                p.formality_level   = voice.get("formality_level", p.formality_level)
                p.affection_level   = voice.get("affection_level", p.affection_level)
                await db.commit()
        except Exception:
            pass  # voice extraction failure never blocks the response

    return _person_to_dict(p)


@router.patch("/people/{person_id}")
async def update_person(
    person_id: str,
    data: PersonUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(RelationshipProfile).where(
            RelationshipProfile.id == uuid.UUID(person_id),
            RelationshipProfile.user_id == current_user.id,
        )
    )
    p = result.scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Person not found")

    for field, value in data.model_dump(exclude_none=True).items():
        setattr(p, field, value)

    p.updated_at = datetime.utcnow()
    await db.commit()

    # Re-extract voice profile if owner updated voice-relevant fields.
    updated_fields = set(data.model_dump(exclude_none=True).keys())
    if updated_fields & {"how_i_talk_to_them", "chat_samples"}:
        try:
            from app.services.survey import extract_relationship_voice
            # Fetch role for role name fallback
            role_result = await db.execute(
                select(RelationshipRole).where(RelationshipRole.id == p.role_id)
            ) if p.role_id else None
            role = role_result.scalar_one_or_none() if role_result else None

            voice = await extract_relationship_voice(
                person_name=p.person_name,
                person_role=p.person_role or (role.name if role else ""),
                zone=p.zone,
                how_i_talk_to_them=p.how_i_talk_to_them or "",
                chat_samples=p.chat_samples or [],
                language=p.relationship_language or "en",
            )
            if voice and voice.get("voice_summary"):
                p.voice_summary     = voice.get("voice_summary")
                p.openness_level    = voice.get("openness_level",  p.openness_level)
                p.warmth_level      = voice.get("warmth_level",    p.warmth_level)
                p.humor_level       = voice.get("humor_level",     p.humor_level)
                p.formality_level   = voice.get("formality_level", p.formality_level)
                p.affection_level   = voice.get("affection_level", p.affection_level)
                await db.commit()
        except Exception:
            pass  # voice extraction failure never blocks the response

    return _person_to_dict(p)


@router.delete("/people/{person_id}")
async def delete_person(
    person_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(RelationshipProfile).where(
            RelationshipProfile.id == uuid.UUID(person_id),
            RelationshipProfile.user_id == current_user.id,
        )
    )
    p = result.scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Person not found")

    p.is_active = False
    await db.commit()
    return {"message": "deleted"}


# ── IDENTIFY ───────────────────────────────────────────────────────────────

@router.post("/identify")
async def identify_speaker(
    data: IdentifyRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    agent_id = uuid.UUID(data.agent_id)

    result = await db.execute(
        select(RelationshipRole).where(
            RelationshipRole.id == uuid.UUID(data.role_id),
            RelationshipRole.agent_id == agent_id,
            RelationshipRole.is_active == True,
        )
    )
    role = result.scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    role_addr   = role.address_forms or []
    role_self   = role.self_address_forms or []

    base = {
        "found_person":           False,
        "person":                 None,
        "role":                   _role_to_dict(role),
        "address_forms":          role_addr,
        "self_address_forms":     role_self,
        "effective_address_form": _first_form(role_addr),
        "effective_self_address": _first_form(role_self),
        "forbidden_particles":    role.forbidden_particles or [],
        "required_particles":     role.required_particles or [],
        "allowed_endings":        role.allowed_endings or [],
        "tone_description":       role.tone_description or "",
        "voice_summary":          None,
        "display_name":           (data.speaker_name or "").strip() or role.name,
    }

    speaker_name = (data.speaker_name or "").strip()
    if not speaker_name:
        return base

    result = await db.execute(
        select(RelationshipProfile).where(
            RelationshipProfile.role_id == role.id,
            RelationshipProfile.agent_id == agent_id,
            RelationshipProfile.is_active == True,
        )
    )
    people = result.scalars().all()

    speaker_lower = speaker_name.lower()
    matched = None

    for p in people:
        if p.person_name.lower().strip() == speaker_lower:
            matched = p
            break

    if not matched:
        for p in people:
            if speaker_lower in [a.lower().strip() for a in (p.person_aliases or [])]:
                matched = p
                break

    if matched:
        # Person overrides role — fall back to role if person has no override
        addr  = matched.address_forms  or role_addr
        self_ = matched.self_address_forms or role_self
        # Pronoun overrides: person wins if non-empty, else role
        forbidden = (matched.forbidden_particles or []) or (role.forbidden_particles or [])
        required  = (matched.required_particles  or []) or (role.required_particles  or [])
        endings   = (matched.allowed_endings      or []) or (role.allowed_endings      or [])
        tone      = matched.tone_description or role.tone_description or ""

        return {
            "found_person":           True,
            "person":                 _person_to_dict(matched),
            "role":                   _role_to_dict(role),
            "address_forms":          addr,
            "self_address_forms":     self_,
            "effective_address_form": _first_form(addr),
            "effective_self_address": _first_form(self_),
            "forbidden_particles":    forbidden,
            "required_particles":     required,
            "allowed_endings":        endings,
            "tone_description":       tone,
            "voice_summary":          matched.voice_summary,
            "display_name":           matched.person_name,
        }

    return {**base, "display_name": speaker_name}


# ── TYPES FOR CHAT ─────────────────────────────────────────────────────────

@router.get("/types-for-chat")
async def get_types_for_chat(
    agent_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(RelationshipType)
        .where(
            RelationshipType.agent_id == uuid.UUID(agent_id),
            RelationshipType.is_active == True,
        )
        .order_by(RelationshipType.sort_order)
    )
    types = result.scalars().all()

    output = []
    for t in types:
        result = await db.execute(
            select(RelationshipRole)
            .where(
                RelationshipRole.type_id == t.id,
                RelationshipRole.is_active == True,
            )
            .order_by(RelationshipRole.sort_order)
        )
        roles = result.scalars().all()

        output.append({
            "type_id":         str(t.id),
            "type_name":       t.name,
            "type_name_local": t.name_local,
            "access_mode":     t.access_mode,
            "roles": [
                {"id": str(r.id), "name": r.name, "name_local": r.name_local}
                for r in roles
            ],
            "default_role_id": str(roles[0].id) if roles else None,
        })

    return {"types": output}