from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from pathlib import Path
import re
import uuid
import os

from app.db.session import get_db
from app.models.user import User, AgentProfile, AgentLifecycle
from app.core.security import get_current_user

router = APIRouter()

# Image storage — same pattern as voice samples.
# Switch AGENT_IMAGE_PATH to an S3 key prefix when deploying.
IMAGE_STORAGE_PATH = Path(
    os.getenv("AGENT_IMAGE_PATH", "agent_images")
)
MAX_IMAGE_SIZE     = 10 * 1024 * 1024   # 10 MB
VALID_IMAGE_TYPES  = {
    "image/jpeg", "image/jpg", "image/png",
    "image/webp", "image/gif",
}
VALID_IMAGE_EXTS   = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


def _ensure_image_dir():
    IMAGE_STORAGE_PATH.mkdir(parents=True, exist_ok=True)


class SlugUpdateRequest(BaseModel):
    slug: str


class AgentUpdateRequest(BaseModel):
    agent_name: str


# ── GET /agents/me ─────────────────────────────────────────────────────────

@router.get("/me")
async def get_my_agent(
    current_user: User         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AgentProfile).where(AgentProfile.user_id == current_user.id)
    )
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    return {
        "agent_id":              str(agent.id),
        "agent_name":            agent.agent_name,
        "slug":                  agent.slug,
        "total_memories":        agent.total_memories,
        "wisdom_score":          round(agent.wisdom_score or 0.0, 2),
        "survey_completed":      agent.survey_completed,
        "dominant_pattern_tags": agent.dominant_pattern_tags,
        "language":              current_user.language,
        "image_url":             f"/agents/me/image" if agent.image_path else None,
    }


# ── PATCH /agents/me ───────────────────────────────────────────────────────

@router.patch("/me")
async def update_agent(
    data:         AgentUpdateRequest,
    current_user: User         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    """
    Update agent name.
    Slug is separate — use PATCH /agents/me/slug.
    """
    name = data.agent_name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="agent_name cannot be empty.")
    if len(name) > 255:
        raise HTTPException(status_code=400, detail="agent_name must be 255 characters or fewer.")

    result = await db.execute(
        select(AgentProfile).where(AgentProfile.user_id == current_user.id)
    )
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    agent.agent_name = name
    await db.commit()

    return {
        "agent_id":   str(agent.id),
        "agent_name": agent.agent_name,
    }


# ── POST /agents/me/image ──────────────────────────────────────────────────

@router.post("/me/image")
async def upload_agent_image(
    file:         UploadFile   = File(...),
    current_user: User         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    """
    Upload an agent profile image.
    Stored locally under AGENT_IMAGE_PATH.
    Returns image_url for the frontend to display immediately.

    When deploying to production, swap IMAGE_STORAGE_PATH → S3:
      - Change _save_image() to upload to S3 and store the S3 key in image_path
      - Change GET /agents/me/image to generate a presigned URL or serve via CDN
    """
    # Validate type
    content_type = (file.content_type or "").lower()
    ext          = Path(file.filename or "image.jpg").suffix.lower()

    if content_type not in VALID_IMAGE_TYPES and ext not in VALID_IMAGE_EXTS:
        raise HTTPException(
            status_code=400,
            detail="Unsupported image format. Use jpg, png, webp, or gif.",
        )

    # Read and size-check
    image_bytes = await file.read()
    if len(image_bytes) > MAX_IMAGE_SIZE:
        raise HTTPException(status_code=400, detail="Image too large. Maximum 10MB.")
    if len(image_bytes) < 100:
        raise HTTPException(status_code=400, detail="Image file appears empty.")

    result = await db.execute(
        select(AgentProfile).where(AgentProfile.user_id == current_user.id)
    )
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Delete old image if exists
    if agent.image_path and os.path.exists(agent.image_path):
        try:
            os.remove(agent.image_path)
        except Exception:
            pass

    # Save new image
    _ensure_image_dir()
    filename   = f"{current_user.id}{ext}"
    file_path  = IMAGE_STORAGE_PATH / filename

    with open(file_path, "wb") as f:
        f.write(image_bytes)

    agent.image_path = str(file_path)
    await db.commit()

    return {
        "message":   "Image uploaded successfully.",
        "image_url": f"/agents/me/image",
    }


# ── DELETE /agents/me/image ────────────────────────────────────────────────

@router.delete("/me/image")
async def delete_agent_image(
    current_user: User         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AgentProfile).where(AgentProfile.user_id == current_user.id)
    )
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    if not agent.image_path:
        raise HTTPException(status_code=404, detail="No image to delete.")

    if os.path.exists(agent.image_path):
        try:
            os.remove(agent.image_path)
        except Exception:
            pass

    agent.image_path = None
    await db.commit()

    return {"message": "Image removed."}


# ── GET /agents/me/image ───────────────────────────────────────────────────

@router.get("/me/image")
async def get_agent_image(
    current_user: User         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    """
    Serve the agent image file directly.
    Frontend calls this URL as <img src="/agents/me/image" />.
    """
    from fastapi.responses import FileResponse

    result = await db.execute(
        select(AgentProfile).where(AgentProfile.user_id == current_user.id)
    )
    agent = result.scalar_one_or_none()
    if not agent or not agent.image_path:
        raise HTTPException(status_code=404, detail="No image found.")

    if not os.path.exists(agent.image_path):
        # Path in DB but file missing — clear it
        agent.image_path = None
        await db.commit()
        raise HTTPException(status_code=404, detail="No image found.")

    ext_to_mime = {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".png": "image/png",  ".webp": "image/webp",
        ".gif": "image/gif",
    }
    ext      = Path(agent.image_path).suffix.lower()
    media    = ext_to_mime.get(ext, "image/jpeg")

    return FileResponse(path=agent.image_path, media_type=media)


# ── GET /agents/lifecycle ──────────────────────────────────────────────────

@router.get("/lifecycle")
async def get_lifecycle(
    current_user: User         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AgentProfile).where(AgentProfile.user_id == current_user.id)
    )
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    result = await db.execute(
        select(AgentLifecycle).where(AgentLifecycle.agent_id == agent.id)
    )
    lifecycle = result.scalar_one_or_none()

    return {
        "interaction_count":      lifecycle.interaction_count      if lifecycle else 0,
        "training_session_count": lifecycle.training_session_count if lifecycle else 0,
        "last_active_at":         lifecycle.last_active_at.isoformat()
                                  if lifecycle and lifecycle.last_active_at else None,
    }


# ── PATCH /agents/me/slug ──────────────────────────────────────────────────

@router.patch("/me/slug")
async def update_slug(
    data:         SlugUpdateRequest,
    current_user: User         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    raw = data.slug.strip().lower()

    if not re.match(r"^[a-z0-9][a-z0-9-]{1,48}[a-z0-9]$", raw):
        raise HTTPException(
            status_code=400,
            detail="Slug must be 3–50 characters, letters/numbers/hyphens only, no leading/trailing hyphens.",
        )

    result = await db.execute(
        select(AgentProfile).where(AgentProfile.slug == raw)
    )
    existing = result.scalar_one_or_none()
    if existing and existing.user_id != current_user.id:
        raise HTTPException(status_code=409, detail="This slug is already taken. Try another.")

    result = await db.execute(
        select(AgentProfile).where(AgentProfile.user_id == current_user.id)
    )
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    agent.slug = raw
    await db.commit()

    return {
        "slug":       agent.slug,
        "public_url": f"/{agent.slug}",
    }