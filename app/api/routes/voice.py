"""
app/api/routes/voice.py

Voice cloning, TTS, and reading template endpoints.

VOICE_ENABLED flag (set in .env):
  VOICE_ENABLED=false  — disables all cloning/TTS endpoints (default until paid plan)
  VOICE_ENABLED=true   — enables full ElevenLabs pipeline

Template endpoint is always available — it's just text, no ElevenLabs involved.
Status endpoint always returns { enabled: false } when VOICE_ENABLED=false
so the frontend can hide the 🔊 icon in chat without any extra logic.
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from pathlib import Path
import uuid
import os

from app.db.session import get_db
from app.models.user import User, AgentProfile, VoiceSample, AgentResponse
from app.core.security import get_current_user
from app.services.voice_template import get_template, get_english_template
from app.core.config import settings

router = APIRouter()

MAX_AUDIO_SIZE    = 50 * 1024 * 1024
MIN_DURATION_SECS = 30.0
VALID_SLOTS       = {"native", "en"}

# ── Feature flag ───────────────────────────────────────────────────────────
# Set VOICE_ENABLED=true in .env when ElevenLabs paid plan is active.
# Everything else works normally — only the cloning/TTS endpoints are gated.
VOICE_ENABLED: bool = str(getattr(settings, "VOICE_ENABLED", "false")).lower() == "true"


def _require_voice():
    """FastAPI dependency — raises 503 if voice is not yet enabled."""
    if not VOICE_ENABLED:
        raise HTTPException(
            status_code=503,
            detail={
                "code":    "voice_not_enabled",
                "message": "Voice cloning is not enabled yet. Set VOICE_ENABLED=true in .env when your ElevenLabs paid plan is active.",
            }
        )


# ── Schemas ────────────────────────────────────────────────────────────────

class SpeakRequest(BaseModel):
    response_id:      str
    stability:        float = 0.5
    similarity_boost: float = 0.75


# ── Helpers ────────────────────────────────────────────────────────────────

async def _get_slot(user_id, slot: str, db: AsyncSession) -> VoiceSample | None:
    result = await db.execute(
        select(VoiceSample).where(
            VoiceSample.user_id       == user_id,
            VoiceSample.language_slot == slot,
        )
    )
    return result.scalar_one_or_none()


def _slot_summary(sample: VoiceSample | None) -> dict:
    if not sample or not sample.elevenlabs_voice_id:
        return {"trained": False, "voice_id": None, "duration_seconds": None, "created_at": None}
    return {
        "trained":          True,
        "voice_id":         sample.elevenlabs_voice_id,
        "duration_seconds": sample.duration_seconds,
        "created_at":       sample.created_at.isoformat() if sample.created_at else None,
    }


# ── GET /voice/template  (always available) ────────────────────────────────

@router.get("/template")
async def get_reading_template(
    current_user: User = Depends(get_current_user),
):
    """
    Reading scripts for both voice cards.
    Always available regardless of VOICE_ENABLED.
    """
    lang            = (current_user.language or "en").lower().strip()
    native_template = get_template(lang)
    english_template = None
    if lang != "en":
        english_template = {**get_english_template(), "optional": True}

    return {"native": native_template, "english": english_template}


# ── GET /voice/status  (always available) ─────────────────────────────────

@router.get("/status")
async def voice_status(
    current_user: User         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    """
    Returns voice status for both slots plus the enabled flag.
    Frontend uses enabled:false to hide the 🔊 icon in chat
    and show a "coming soon" state on the voice settings page.
    """
    lang = (current_user.language or "en").lower().strip()

    if not VOICE_ENABLED:
        return {
            "enabled":            False,
            "native":             {"trained": False, "voice_id": None, "duration_seconds": None, "created_at": None},
            "english":            {"trained": False, "voice_id": None, "duration_seconds": None, "created_at": None},
            "english_applicable": lang != "en",
        }

    native_sample  = await _get_slot(current_user.id, "native", db)
    english_sample = await _get_slot(current_user.id, "en",     db)

    return {
        "enabled":            True,
        "native":             _slot_summary(native_sample),
        "english":            _slot_summary(english_sample),
        "english_applicable": lang != "en",
    }


# ── POST /voice/record  (requires VOICE_ENABLED) ───────────────────────────

@router.post("/record")
async def record_voice_sample(
    file:                    UploadFile   = File(...),
    language_slot:           str          = Form(...),
    remove_background_noise: bool         = Form(False),
    current_user:            User         = Depends(get_current_user),
    db:                      AsyncSession = Depends(get_db),
    _:                       None         = Depends(_require_voice),
):
    return await _process_upload(
        file=file, language_slot=language_slot,
        remove_background_noise=remove_background_noise,
        current_user=current_user, db=db, source="record",
    )


# ── POST /voice/upload  (requires VOICE_ENABLED) ───────────────────────────

@router.post("/upload")
async def upload_voice_sample(
    file:                    UploadFile   = File(...),
    language_slot:           str          = Form(...),
    remove_background_noise: bool         = Form(False),
    current_user:            User         = Depends(get_current_user),
    db:                      AsyncSession = Depends(get_db),
    _:                       None         = Depends(_require_voice),
):
    return await _process_upload(
        file=file, language_slot=language_slot,
        remove_background_noise=remove_background_noise,
        current_user=current_user, db=db, source="upload",
    )


async def _process_upload(
    file:                    UploadFile,
    language_slot:           str,
    remove_background_noise: bool,
    current_user:            User,
    db:                      AsyncSession,
    source:                  str,
) -> dict:
    # Imported here so the module loads cleanly even without ElevenLabs creds
    from app.services.voice import clone_voice, delete_voice, save_audio_file

    if language_slot not in VALID_SLOTS:
        raise HTTPException(status_code=400, detail="language_slot must be 'native' or 'en'")

    user_lang = (current_user.language or "en").lower().strip()
    if language_slot == "en" and user_lang == "en":
        raise HTTPException(
            status_code=400,
            detail="English slot is not applicable when your native language is already English."
        )

    allowed_types = {
        "audio/mpeg", "audio/mp3", "audio/wav", "audio/x-wav",
        "audio/mp4", "audio/m4a", "audio/webm", "audio/ogg",
        "audio/flac", "audio/x-flac",
    }
    filename = file.filename or "recording.webm"
    ext      = Path(filename).suffix.lower()
    if (file.content_type or "") not in allowed_types and ext not in {".mp3", ".wav", ".m4a", ".webm", ".ogg", ".flac"}:
        raise HTTPException(status_code=400, detail="Unsupported audio format. Use mp3, wav, m4a, webm, ogg, or flac.")

    audio_bytes = await file.read()
    if len(audio_bytes) > MAX_AUDIO_SIZE:
        raise HTTPException(status_code=400, detail="Audio file too large. Maximum 50MB.")
    if len(audio_bytes) < 10_000:
        raise HTTPException(status_code=400, detail="Audio file too small. Record at least 30 seconds.")

    file_path, estimated_duration = save_audio_file(
        audio_bytes=audio_bytes,
        user_id=str(current_user.id),
        original_filename=filename,
    )

    if estimated_duration < MIN_DURATION_SECS:
        try: os.remove(file_path)
        except Exception: pass
        raise HTTPException(
            status_code=400,
            detail=f"Recording too short ({estimated_duration:.0f}s). Minimum 30 seconds needed."
        )

    try:
        voice_id = await clone_voice(
            audio_path=file_path,
            user_name=f"{current_user.name}_{language_slot}",
            user_id=str(current_user.id),
            remove_background_noise=remove_background_noise,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except RuntimeError as e:
        try: os.remove(file_path)
        except Exception: pass
        raise HTTPException(status_code=502, detail=str(e))

    old = await _get_slot(current_user.id, language_slot, db)
    if old:
        if old.elevenlabs_voice_id:
            try: await delete_voice(old.elevenlabs_voice_id)
            except Exception: pass
        if old.audio_file_ref and os.path.exists(old.audio_file_ref):
            try: os.remove(old.audio_file_ref)
            except Exception: pass
        await db.delete(old)

    sample = VoiceSample(
        user_id             = current_user.id,
        session_id          = None,
        language_slot       = language_slot,
        audio_file_ref      = file_path,
        duration_seconds    = estimated_duration,
        language_detected   = "en" if language_slot == "en" else current_user.language,
        elevenlabs_voice_id = voice_id,
    )
    db.add(sample)
    await db.commit()

    return {
        "message":          "Voice cloned successfully.",
        "slot":             language_slot,
        "voice_id":         voice_id,
        "duration_seconds": round(estimated_duration, 1),
        "source":           source,
    }


# ── DELETE /voice/{slot}  (requires VOICE_ENABLED) ────────────────────────

@router.delete("/{slot}")
async def delete_voice_slot(
    slot:         str,
    current_user: User         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
    _:            None         = Depends(_require_voice),
):
    from app.services.voice import delete_voice

    if slot not in VALID_SLOTS:
        raise HTTPException(status_code=400, detail="Slot must be 'native' or 'en'")

    sample = await _get_slot(current_user.id, slot, db)
    if not sample:
        raise HTTPException(status_code=404, detail=f"No voice sample found for slot '{slot}'")

    if sample.elevenlabs_voice_id:
        try: await delete_voice(sample.elevenlabs_voice_id)
        except Exception: pass

    if sample.audio_file_ref and os.path.exists(sample.audio_file_ref):
        try: os.remove(sample.audio_file_ref)
        except Exception: pass

    await db.delete(sample)
    await db.commit()

    return {"message": f"Voice slot '{slot}' deleted.", "slot": slot}


# ── POST /voice/speak  (requires VOICE_ENABLED) ────────────────────────────

@router.post("/speak")
async def speak_response(
    data:         SpeakRequest,
    current_user: User         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
    _:            None         = Depends(_require_voice),
):
    from app.services.voice import speak_and_save, VOICE_STORAGE_PATH

    try:
        response_uuid = uuid.UUID(data.response_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid response_id")

    result = await db.execute(
        select(AgentResponse).where(
            AgentResponse.id      == response_uuid,
            AgentResponse.user_id == current_user.id,
        )
    )
    agent_response = result.scalar_one_or_none()
    if not agent_response:
        raise HTTPException(status_code=404, detail="Response not found")

    user_lang     = (current_user.language or "en").lower().strip()
    response_lang = (getattr(agent_response, "response_language", None) or user_lang).lower().strip()
    prefer_slot   = "en" if response_lang == "en" and user_lang != "en" else "native"

    sample = await _get_slot(current_user.id, prefer_slot, db)
    if not sample or not sample.elevenlabs_voice_id:
        fallback = "native" if prefer_slot == "en" else "en"
        sample   = await _get_slot(current_user.id, fallback, db)

    if not sample or not sample.elevenlabs_voice_id:
        raise HTTPException(status_code=404, detail="No cloned voice found. Record your voice first.")

    cached_path = VOICE_STORAGE_PATH / "responses" / f"{data.response_id}.mp3"
    if cached_path.exists():
        return {"audio_url": f"/voice/play/{data.response_id}", "cached": True}

    text = agent_response.response_text
    if not text or not text.strip():
        raise HTTPException(status_code=400, detail="Response text is empty")

    try:
        await speak_and_save(
            text=text,
            voice_id=sample.elevenlabs_voice_id,
            agent_response_id=data.response_id,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))

    return {"audio_url": f"/voice/play/{data.response_id}", "cached": False}


# ── GET /voice/play/{response_id}  (requires VOICE_ENABLED) ───────────────

@router.get("/play/{response_id}")
async def play_response(
    response_id:  str,
    current_user: User = Depends(get_current_user),
    _:            None = Depends(_require_voice),
):
    from app.services.voice import VOICE_STORAGE_PATH

    try:
        uuid.UUID(response_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid response_id")

    file_path = VOICE_STORAGE_PATH / "responses" / f"{response_id}.mp3"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Audio not found. Call POST /voice/speak first.")

    return FileResponse(
        path=str(file_path),
        media_type="audio/mpeg",
        filename=f"response_{response_id}.mp3",
    )