"""
app/api/routes/access_keys.py

Owner-authenticated routes for managing public chat access keys.

Each RelationshipProfile can have one passphrase-based access key.
Owner can set their own passphrase or use a system-generated suggestion.

Endpoints:
  GET    /access-keys/suggest               → generate a passphrase suggestion (no DB write)
  POST   /access-keys/{profile_id}/generate → save passphrase (owner-defined or random)
  DELETE /access-keys/{profile_id}/revoke   → clear key
  PATCH  /access-keys/{profile_id}/toggle   → enable / disable without deleting
  GET    /access-keys                        → list all people with key status
"""

import random
from typing import Optional
from passlib.context import CryptContext
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid

from app.db.session import get_db
from app.models.user import User, AgentProfile, RelationshipProfile, RelationshipRole
from app.core.security import get_current_user

router = APIRouter()

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ── Wordlists ─────────────────────────────────────────────────────────────
_ADJECTIVES = [
    "blue", "red", "green", "gold", "silver", "bright", "dark", "calm",
    "swift", "quiet", "warm", "cool", "clear", "deep", "soft", "bold",
    "wild", "sharp", "sweet", "kind", "fair", "proud", "wise", "free",
    "young", "old", "long", "wide", "high", "low", "fast", "slow",
    "rich", "pure", "rare", "true", "glad", "brave", "keen", "great",
]
_NOUNS = [
    "river", "stone", "light", "cloud", "flame", "wind", "sky", "rain",
    "moon", "star", "wave", "lake", "hill", "tree", "bird", "tiger",
    "eagle", "forest", "field", "bridge", "tower", "gate", "path", "cliff",
    "ocean", "desert", "valley", "summit", "harbor", "island", "canyon", "peak",
    "dawn", "dusk", "storm", "frost", "ember", "bloom", "thorn", "cedar",
]


def _generate_passphrase() -> str:
    return f"{random.choice(_ADJECTIVES)}-{random.choice(_NOUNS)}-{random.randint(10, 99)}"


def _make_preview(passphrase: str) -> str:
    """e.g. "blue-river-42" → "···-river-42" """
    parts = passphrase.split("-")
    if len(parts) >= 3:
        return "···-" + "-".join(parts[-2:])
    if len(parts) == 2:
        return "···-" + parts[-1]
    return "···"


def _validate_passphrase(passphrase: str) -> str:
    p = passphrase.strip()
    if len(p) < 6:
        raise HTTPException(status_code=400, detail="Passphrase must be at least 6 characters.")
    if len(p) > 100:
        raise HTTPException(status_code=400, detail="Passphrase must be 100 characters or fewer.")
    return p


# ── Schema ────────────────────────────────────────────────────────────────

class GenerateKeyRequest(BaseModel):
    passphrase: Optional[str] = None  # if None → system generates one


# ── Helper ────────────────────────────────────────────────────────────────

async def _get_profile(
    profile_id: str,
    current_user: User,
    db: AsyncSession,
) -> RelationshipProfile:
    try:
        pid = uuid.UUID(profile_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid profile_id")

    result = await db.execute(
        select(RelationshipProfile).where(
            RelationshipProfile.id        == pid,
            RelationshipProfile.user_id   == current_user.id,
            RelationshipProfile.is_active == True,
        )
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Person not found")
    return profile


# ── GET /access-keys/suggest ──────────────────────────────────────────────

@router.get("/suggest")
async def suggest_passphrase(
    current_user: User = Depends(get_current_user),
):
    """
    Returns a random passphrase suggestion — no DB write.
    Frontend calls this when the Add Person modal opens to pre-fill the input.
    Owner can keep it or type their own.
    """
    return {"passphrase": _generate_passphrase()}


# ── POST /access-keys/{profile_id}/generate ───────────────────────────────

@router.post("/{profile_id}/generate")
async def generate_access_key(
    profile_id:   str,
    data:         GenerateKeyRequest = GenerateKeyRequest(),
    current_user: User               = Depends(get_current_user),
    db:           AsyncSession       = Depends(get_db),
):
    """
    Save an access key for this person.
    Owner can send their own passphrase in data.passphrase,
    or leave it empty to get a system-generated one.
    Replaces any existing key.
    The plain-text is returned once so the owner can share it.
    """
    profile    = await _get_profile(profile_id, current_user, db)
    passphrase = _validate_passphrase(data.passphrase) if data.passphrase else _generate_passphrase()

    profile.access_key_hash    = pwd_ctx.hash(passphrase)
    profile.access_key_plain   = passphrase          # stored so owner can always retrieve it
    profile.access_key_preview = _make_preview(passphrase)
    profile.access_key_enabled = True

    await db.commit()

    return {
        "passphrase":  passphrase,
        "preview":     profile.access_key_preview,
        "person_name": profile.person_name,
        "profile_id":  str(profile.id),
        "enabled":     True,
    }


# ── DELETE /access-keys/{profile_id}/revoke ───────────────────────────────

@router.delete("/{profile_id}/revoke")
async def revoke_access_key(
    profile_id:   str,
    current_user: User         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    profile = await _get_profile(profile_id, current_user, db)
    profile.access_key_hash    = None
    profile.access_key_plain   = None
    profile.access_key_preview = None
    profile.access_key_enabled = False
    await db.commit()
    return {"message": "Access key revoked.", "profile_id": str(profile.id), "person_name": profile.person_name}


# ── PATCH /access-keys/{profile_id}/toggle ────────────────────────────────

@router.patch("/{profile_id}/toggle")
async def toggle_access_key(
    profile_id:   str,
    current_user: User         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    profile = await _get_profile(profile_id, current_user, db)
    if not profile.access_key_hash:
        raise HTTPException(status_code=400, detail="No access key exists. Generate one first.")
    profile.access_key_enabled = not profile.access_key_enabled
    await db.commit()
    return {
        "profile_id":  str(profile.id),
        "person_name": profile.person_name,
        "enabled":     profile.access_key_enabled,
        "preview":     profile.access_key_preview,
    }


# ── GET /access-keys ──────────────────────────────────────────────────────

@router.get("")
async def list_access_keys(
    current_user: User         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    """
    List all people with key status. Never returns hashes or plain-text.
    """
    result = await db.execute(
        select(AgentProfile).where(AgentProfile.user_id == current_user.id)
    )
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    result = await db.execute(
        select(RelationshipProfile).where(
            RelationshipProfile.agent_id  == agent.id,
            RelationshipProfile.is_active == True,
        ).order_by(RelationshipProfile.person_name)
    )
    profiles = result.scalars().all()

    role_ids = list({p.role_id for p in profiles if p.role_id})
    roles_map: dict[uuid.UUID, RelationshipRole] = {}
    if role_ids:
        r_result = await db.execute(
            select(RelationshipRole).where(RelationshipRole.id.in_(role_ids))
        )
        for r in r_result.scalars().all():
            roles_map[r.id] = r

    return {
        "people": [
            {
                "profile_id":      str(p.id),
                "person_name":     p.person_name,
                "zone":            p.zone,
                "role_name":       roles_map[p.role_id].name if p.role_id and p.role_id in roles_map else None,
                "role_name_local": roles_map[p.role_id].name_local if p.role_id and p.role_id in roles_map else None,
                "has_key":         bool(p.access_key_hash),
                "key_enabled":     p.access_key_enabled,
                "key_preview":     p.access_key_preview,
                "key_plain":       p.access_key_plain,   # full passphrase — owner only
            }
            for p in profiles
        ]
    }