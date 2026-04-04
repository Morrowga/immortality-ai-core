"""
app/api/routes/neo.py

Neo Mode routes — owner authenticated.

Endpoints:
  GET    /neo/packages/system                → list all available system packages
  GET    /neo/packages                       → list installed packages for this agent
  POST   /neo/packages/install               → install a system package into a slot
  POST   /neo/packages/custom                → create and install a custom package (manual)
  POST   /neo/packages/custom/generate       → auto-generate content from title and install
  PATCH  /neo/packages/{package_id}          → update custom instructions on installed package
  DELETE /neo/packages/{package_id}          → uninstall (remove from slot)
  POST   /neo/packages/{package_id}/replace  → replace one package with another
"""

import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.user import User, AgentProfile, NeoPackage
from app.core.security import get_current_user
from app.neo_packages import list_system_packages, get_system_package, get_domain_tags, get_safety_disclaimer
from app.services.neo import (
    validate_custom_instructions,
    validate_custom_package,
    validate_and_generate_package,
    extract_domain_tags,
    MAX_PACKAGES,
    MAX_CUSTOM_INSTRUCTION_CHARS,
    MAX_CUSTOM_PACKAGE_CHARS,
    MIN_CUSTOM_PACKAGE_CHARS,
)

router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────

class InstallSystemPackageRequest(BaseModel):
    package_key: str
    slot_number: int
    custom_instructions: Optional[str] = None


class CreateCustomPackageRequest(BaseModel):
    title: str
    content: str
    slot_number: int
    custom_instructions: Optional[str] = None


class GenerateCustomPackageRequest(BaseModel):
    title: str
    slot_number: int


class UpdatePackageRequest(BaseModel):
    custom_instructions: Optional[str] = None


class ReplacePackageRequest(BaseModel):
    package_key: Optional[str] = None
    new_title: Optional[str] = None
    new_content: Optional[str] = None
    custom_instructions: Optional[str] = None


# ── Helpers ───────────────────────────────────────────────────────────────

async def _get_agent(user_id, db: AsyncSession) -> AgentProfile:
    result = await db.execute(
        select(AgentProfile).where(AgentProfile.user_id == user_id)
    )
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


async def _get_package_by_id(package_id: str, user_id, db: AsyncSession) -> NeoPackage:
    try:
        pid = uuid.UUID(package_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid package_id")

    result = await db.execute(
        select(NeoPackage).where(
            NeoPackage.id == pid,
            NeoPackage.user_id == user_id,
            NeoPackage.is_active == True,
        )
    )
    pkg = result.scalar_one_or_none()
    if not pkg:
        raise HTTPException(status_code=404, detail="Package not found")
    return pkg


def _validate_slot(slot_number: int):
    if slot_number not in range(1, MAX_PACKAGES + 1):
        raise HTTPException(
            status_code=400,
            detail=f"slot_number must be between 1 and {MAX_PACKAGES}.",
        )


def _serialize_package(pkg: NeoPackage) -> dict:
    return {
        "id":                   str(pkg.id),
        "package_type":         pkg.package_type,
        "package_key":          pkg.package_key,
        "title":                pkg.title,
        "description":          pkg.description,
        "slot_number":          pkg.slot_number,
        "custom_instructions":  pkg.custom_instructions,
        "domain_tags":          pkg.domain_tags or [],
        "neo_mode_disclaimer":  pkg.neo_mode_disclaimer,
        "char_count":           pkg.char_count,
        "installed_at":         pkg.installed_at.isoformat() if pkg.installed_at else None,
        "updated_at":           pkg.updated_at.isoformat() if pkg.updated_at else None,
    }


async def _clear_slot(agent_id, slot_number: int, db: AsyncSession):
    """Remove any existing active package in this slot."""
    result = await db.execute(
        select(NeoPackage).where(
            NeoPackage.agent_id == agent_id,
            NeoPackage.slot_number == slot_number,
            NeoPackage.is_active == True,
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        existing.is_active = False
        await db.flush()


# ── GET /neo/packages/system ──────────────────────────────────────────────

@router.get("/packages/system")
async def list_available_system_packages(
    current_user: User = Depends(get_current_user),
):
    """Returns all system packages available to install."""
    return {"packages": list_system_packages()}


# ── GET /neo/packages ─────────────────────────────────────────────────────

@router.get("/packages")
async def list_installed_packages(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Returns all packages currently installed on this agent, mapped by slot."""
    agent = await _get_agent(current_user.id, db)

    result = await db.execute(
        select(NeoPackage).where(
            NeoPackage.agent_id == agent.id,
            NeoPackage.is_active == True,
        ).order_by(NeoPackage.slot_number)
    )
    packages = result.scalars().all()

    slot_map = {i: None for i in range(1, MAX_PACKAGES + 1)}
    for pkg in packages:
        slot_map[pkg.slot_number] = _serialize_package(pkg)

    return {
        "slots":            slot_map,
        "installed_count":  len(packages),
        "max_packages":     MAX_PACKAGES,
        "slots_available":  MAX_PACKAGES - len(packages),
    }


# ── POST /neo/packages/install ────────────────────────────────────────────

@router.post("/packages/install")
async def install_system_package(
    data: InstallSystemPackageRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Install a system package into a slot.
    If the slot is occupied — the existing package is removed first.
    Duplicate package_key in another slot is rejected.
    """
    _validate_slot(data.slot_number)

    agent = await _get_agent(current_user.id, db)

    pkg_def = get_system_package(data.package_key)
    if not pkg_def:
        raise HTTPException(status_code=404, detail=f"System package '{data.package_key}' not found.")

    # No duplicate package_key in other slots
    result = await db.execute(
        select(NeoPackage).where(
            NeoPackage.agent_id == agent.id,
            NeoPackage.package_key == data.package_key,
            NeoPackage.is_active == True,
            NeoPackage.slot_number != data.slot_number,
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail=f"'{pkg_def['title']}' is already installed in another slot.",
        )

    # Validate custom instructions if provided
    if data.custom_instructions and data.custom_instructions.strip():
        validation = await validate_custom_instructions(
            package_key=data.package_key,
            package_title=pkg_def["title"],
            domain_tags=pkg_def["domain_tags"],
            custom_instructions=data.custom_instructions,
        )
        if not validation.get("valid"):
            raise HTTPException(
                status_code=400,
                detail=f"Custom instructions rejected: {validation.get('reason', 'Instructions do not match this package domain.')}",
            )

    await _clear_slot(agent.id, data.slot_number, db)

    package = NeoPackage(
        agent_id            = agent.id,
        user_id             = current_user.id,
        package_type        = "system",
        package_key         = data.package_key,
        title               = pkg_def["title"],
        description         = pkg_def["description"],
        slot_number         = data.slot_number,
        custom_instructions = data.custom_instructions.strip() if data.custom_instructions else None,
        domain_tags         = pkg_def["domain_tags"],
        neo_mode_disclaimer = get_safety_disclaimer(data.package_key),
    )
    db.add(package)
    await db.commit()

    return {
        "message": f"'{pkg_def['title']}' installed in slot {data.slot_number}.",
        "package": _serialize_package(package),
    }


# ── POST /neo/packages/custom ─────────────────────────────────────────────

@router.post("/packages/custom")
async def create_custom_package(
    data: CreateCustomPackageRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a custom package from owner-written content and install it.
    Validates content coherence before saving.
    """
    _validate_slot(data.slot_number)

    if not data.title or not data.title.strip():
        raise HTTPException(status_code=400, detail="Title is required.")

    if not data.content or not data.content.strip():
        raise HTTPException(status_code=400, detail="Content is required.")

    agent = await _get_agent(current_user.id, db)

    validation = await validate_custom_package(
        title=data.title.strip(),
        content=data.content.strip(),
    )
    if not validation.get("valid"):
        raise HTTPException(
            status_code=400,
            detail=f"Package rejected: {validation.get('reason', 'Content could not be validated.')}",
        )

    domain_tags = await extract_domain_tags(data.title.strip(), data.content.strip())

    if data.custom_instructions and data.custom_instructions.strip():
        instr_validation = await validate_custom_instructions(
            package_key="custom",
            package_title=data.title.strip(),
            domain_tags=domain_tags,
            custom_instructions=data.custom_instructions,
        )
        if not instr_validation.get("valid"):
            raise HTTPException(
                status_code=400,
                detail=f"Custom instructions rejected: {instr_validation.get('reason', 'Instructions do not match package domain.')}",
            )

    await _clear_slot(agent.id, data.slot_number, db)

    char_count = len(data.content.strip())
    package = NeoPackage(
        agent_id            = agent.id,
        user_id             = current_user.id,
        package_type        = "custom",
        package_key         = None,
        title               = data.title.strip(),
        description         = validation.get("domain_summary", data.title.strip()),
        slot_number         = data.slot_number,
        custom_instructions = data.content.strip(),
        domain_tags         = domain_tags,
        neo_mode_disclaimer = None,
        char_count          = char_count,
    )
    db.add(package)
    await db.commit()

    return {
        "message":               f"Custom package '{data.title}' installed in slot {data.slot_number}.",
        "package":               _serialize_package(package),
        "char_count":            char_count,
        "domain_tags_extracted": domain_tags,
    }


# ── POST /neo/packages/custom/generate ───────────────────────────────────

@router.post("/packages/custom/generate")
async def generate_and_install_custom_package(
    data: GenerateCustomPackageRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Auto-generate content from title and install in one step.
    Validates title is a meaningful domain before generating.
    Returns 400 with a descriptive reason if title is invalid.
    """
    _validate_slot(data.slot_number)

    if not data.title or not data.title.strip():
        raise HTTPException(status_code=400, detail="Title is required.")

    agent = await _get_agent(current_user.id, db)

    result = await validate_and_generate_package(data.title.strip())

    if not result.get("valid"):
        raise HTTPException(
            status_code=400,
            detail=result.get("reason", "Title is not specific enough. Try a clearer domain name."),
        )

    content = result.get("content", "")
    if not content:
        raise HTTPException(
            status_code=500,
            detail="Content generation failed. Try again.",
        )

    domain_tags = await extract_domain_tags(data.title.strip(), content)

    await _clear_slot(agent.id, data.slot_number, db)

    package = NeoPackage(
        agent_id            = agent.id,
        user_id             = current_user.id,
        package_type        = "custom",
        package_key         = None,
        title               = data.title.strip(),
        description         = result.get("domain_summary", data.title.strip()),
        slot_number         = data.slot_number,
        custom_instructions = content,
        domain_tags         = domain_tags,
        neo_mode_disclaimer = None,
        char_count          = len(content),
    )
    db.add(package)
    await db.commit()

    return {
        "message":               f"'{data.title}' generated and installed in slot {data.slot_number}.",
        "package":               _serialize_package(package),
        "char_count":            len(content),
        "domain_tags_extracted": domain_tags,
    }


# ── PATCH /neo/packages/{package_id} ─────────────────────────────────────

@router.patch("/packages/{package_id}")
async def update_package_instructions(
    package_id: str,
    data: UpdatePackageRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Update custom instructions on a system package.
    For custom packages — updates the full content and re-extracts domain tags.
    """
    pkg = await _get_package_by_id(package_id, current_user.id, db)

    new_instructions = (data.custom_instructions or "").strip()

    if pkg.package_type == "system":
        if new_instructions:
            validation = await validate_custom_instructions(
                package_key=pkg.package_key,
                package_title=pkg.title,
                domain_tags=pkg.domain_tags or [],
                custom_instructions=new_instructions,
            )
            if not validation.get("valid"):
                raise HTTPException(
                    status_code=400,
                    detail=f"Instructions rejected: {validation.get('reason', 'Instructions do not match this package domain.')}",
                )
        pkg.custom_instructions = new_instructions or None

    elif pkg.package_type == "custom":
        if new_instructions:
            validation = await validate_custom_package(pkg.title, new_instructions)
            if not validation.get("valid"):
                raise HTTPException(
                    status_code=400,
                    detail=f"Content rejected: {validation.get('reason', 'Content could not be validated.')}",
                )
            pkg.custom_instructions = new_instructions
            pkg.char_count = len(new_instructions)
            pkg.domain_tags = await extract_domain_tags(pkg.title, new_instructions)

    pkg.updated_at = datetime.utcnow()
    await db.commit()

    return {
        "message": "Package updated.",
        "package": _serialize_package(pkg),
    }


# ── DELETE /neo/packages/{package_id} ────────────────────────────────────

@router.delete("/packages/{package_id}")
async def uninstall_package(
    package_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Remove a package from its slot. Slot becomes available immediately."""
    pkg = await _get_package_by_id(package_id, current_user.id, db)
    slot  = pkg.slot_number
    title = pkg.title

    pkg.is_active = False
    await db.commit()

    return {
        "message":    f"'{title}' removed from slot {slot}.",
        "slot_freed": slot,
    }


# ── POST /neo/packages/{package_id}/replace ───────────────────────────────

@router.post("/packages/{package_id}/replace")
async def replace_package(
    package_id: str,
    data: ReplacePackageRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Replace an installed package with a different one in the same slot.
    Two modes:
      - System: provide package_key
      - Custom: provide new_title + new_content
    """
    existing = await _get_package_by_id(package_id, current_user.id, db)
    slot     = existing.slot_number
    agent_id = existing.agent_id

    existing.is_active = False
    await db.flush()

    if data.package_key:
        pkg_def = get_system_package(data.package_key)
        if not pkg_def:
            raise HTTPException(status_code=404, detail=f"System package '{data.package_key}' not found.")

        result = await db.execute(
            select(NeoPackage).where(
                NeoPackage.agent_id == agent_id,
                NeoPackage.package_key == data.package_key,
                NeoPackage.is_active == True,
            )
        )
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=409,
                detail=f"'{pkg_def['title']}' is already installed in another slot.",
            )

        if data.custom_instructions and data.custom_instructions.strip():
            validation = await validate_custom_instructions(
                package_key=data.package_key,
                package_title=pkg_def["title"],
                domain_tags=pkg_def["domain_tags"],
                custom_instructions=data.custom_instructions,
            )
            if not validation.get("valid"):
                raise HTTPException(
                    status_code=400,
                    detail=f"Instructions rejected: {validation.get('reason')}",
                )

        new_pkg = NeoPackage(
            agent_id            = agent_id,
            user_id             = current_user.id,
            package_type        = "system",
            package_key         = data.package_key,
            title               = pkg_def["title"],
            description         = pkg_def["description"],
            slot_number         = slot,
            custom_instructions = data.custom_instructions.strip() if data.custom_instructions else None,
            domain_tags         = pkg_def["domain_tags"],
            neo_mode_disclaimer = get_safety_disclaimer(data.package_key),
        )

    elif data.new_title and data.new_content:
        validation = await validate_custom_package(data.new_title.strip(), data.new_content.strip())
        if not validation.get("valid"):
            raise HTTPException(
                status_code=400,
                detail=f"Package rejected: {validation.get('reason')}",
            )

        domain_tags = await extract_domain_tags(data.new_title.strip(), data.new_content.strip())

        new_pkg = NeoPackage(
            agent_id            = agent_id,
            user_id             = current_user.id,
            package_type        = "custom",
            package_key         = None,
            title               = data.new_title.strip(),
            description         = validation.get("domain_summary", data.new_title.strip()),
            slot_number         = slot,
            custom_instructions = data.new_content.strip(),
            domain_tags         = domain_tags,
            neo_mode_disclaimer = None,
            char_count          = len(data.new_content.strip()),
        )

    else:
        raise HTTPException(
            status_code=400,
            detail="Provide either package_key (system) or new_title + new_content (custom).",
        )

    db.add(new_pkg)
    await db.commit()

    return {
        "message": f"Slot {slot} replaced with '{new_pkg.title}'.",
        "package": _serialize_package(new_pkg),
    }