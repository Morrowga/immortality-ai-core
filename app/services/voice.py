"""
app/services/voice.py

ElevenLabs voice cloning and TTS service.

Two operations:
  1. clone_voice()  — upload audio → ElevenLabs → get voice_id back
  2. speak()        — text + voice_id → ElevenLabs TTS → audio bytes

Storage:
  Audio files stored locally under VOICE_STORAGE_PATH (set in config).
  voice_id stored in VoiceSample.elevenlabs_voice_id.

ElevenLabs Instant Voice Cloning:
  - 1-2 minutes of clean audio is enough
  - Supports multipart upload (multiple files or single file)
  - Returns voice_id immediately — no async training needed
  - Cost: free tier = 10,000 chars/month TTS
"""

import os
import uuid
import httpx
import asyncio
from pathlib import Path
from app.core.config import settings

# ── Constants ──────────────────────────────────────────────────────────────

ELEVENLABS_BASE = "https://api.elevenlabs.io/v1"

# Model to use for TTS
# eleven_flash_v2_5 = fastest (~75ms), good multilingual support
# eleven_v3         = best quality, most expressive, 70+ languages
TTS_MODEL = "eleven_flash_v2_5"

# Local storage path — set VOICE_STORAGE_PATH in your .env
# Default: ./voice_storage relative to project root
VOICE_STORAGE_PATH = Path(
    getattr(settings, "VOICE_STORAGE_PATH", "voice_storage")
)


def _ensure_storage():
    """Create voice storage directory if it doesn't exist."""
    VOICE_STORAGE_PATH.mkdir(parents=True, exist_ok=True)
    (VOICE_STORAGE_PATH / "samples").mkdir(exist_ok=True)
    (VOICE_STORAGE_PATH / "responses").mkdir(exist_ok=True)


def _elevenlabs_headers() -> dict:
    return {
        "xi-api-key": settings.ELEVENLABS_API_KEY,
        "Accept": "application/json",
    }


# ── Voice cloning ──────────────────────────────────────────────────────────

async def clone_voice(
    audio_path: str | Path,
    user_name: str,
    user_id: str,
    remove_background_noise: bool = False,
) -> str:
    """
    Upload audio to ElevenLabs and create an Instant Voice Clone.
    Returns the voice_id string.

    audio_path: local path to the audio file (wav, mp3, m4a, webm)
    user_name:  used as the voice name in ElevenLabs dashboard
    user_id:    for labeling in ElevenLabs
    remove_background_noise: let ElevenLabs clean the audio
                             only set True if there IS background noise —
                             enabling it on clean audio can hurt quality
    """
    audio_path = Path(audio_path)
    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    voice_name = f"{user_name}_{user_id[:8]}"

    async with httpx.AsyncClient(timeout=60.0) as client:
        with open(audio_path, "rb") as f:
            files = [("files", (audio_path.name, f, _mime_type(audio_path)))]
            data = {
                "name": voice_name,
                "remove_background_noise": str(remove_background_noise).lower(),
                "labels": f'{{"language": "auto", "user_id": "{user_id}"}}',
                "description": f"Cloned voice for user {user_name}",
            }

            response = await client.post(
                f"{ELEVENLABS_BASE}/voices/add",
                headers=_elevenlabs_headers(),
                data=data,
                files=files,
            )

    if response.status_code != 200:
        raise RuntimeError(
            f"ElevenLabs clone failed: {response.status_code} — {response.text}"
        )

    result = response.json()
    voice_id = result.get("voice_id")
    if not voice_id:
        raise RuntimeError(f"ElevenLabs returned no voice_id: {result}")

    return voice_id


async def delete_voice(voice_id: str) -> bool:
    """
    Delete a cloned voice from ElevenLabs.
    Called when user deletes their voice sample.
    Returns True if deleted, False if not found.
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.delete(
            f"{ELEVENLABS_BASE}/voices/{voice_id}",
            headers=_elevenlabs_headers(),
        )
    return response.status_code == 200


# ── Text to Speech ─────────────────────────────────────────────────────────

async def speak(
    text: str,
    voice_id: str,
    stability: float = 0.5,
    similarity_boost: float = 0.75,
    style: float = 0.0,
) -> bytes:
    """
    Convert text to speech using a cloned voice.
    Returns raw audio bytes (mp3).

    stability:        0.0-1.0 — lower = more expressive, higher = more consistent
    similarity_boost: 0.0-1.0 — how closely to match the cloned voice
    style:            0.0-1.0 — speaking style exaggeration (0 = neutral)
    """
    if not text or not text.strip():
        raise ValueError("Text cannot be empty")

    if not voice_id:
        raise ValueError("voice_id is required")

    payload = {
        "text": text,
        "model_id": TTS_MODEL,
        "voice_settings": {
            "stability": stability,
            "similarity_boost": similarity_boost,
            "style": style,
            "use_speaker_boost": True,
        },
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{ELEVENLABS_BASE}/text-to-speech/{voice_id}",
            headers={
                **_elevenlabs_headers(),
                "Accept": "audio/mpeg",
                "Content-Type": "application/json",
            },
            json=payload,
        )

    if response.status_code != 200:
        raise RuntimeError(
            f"ElevenLabs TTS failed: {response.status_code} — {response.text[:200]}"
        )

    return response.content


async def speak_and_save(
    text: str,
    voice_id: str,
    agent_response_id: str,
) -> str:
    """
    Convert text to speech and save the audio file locally.
    Returns the file path relative to VOICE_STORAGE_PATH.

    Called from the /voice/speak endpoint.
    File is saved as: voice_storage/responses/{agent_response_id}.mp3
    """
    _ensure_storage()

    audio_bytes = await speak(text=text, voice_id=voice_id)

    filename = f"{agent_response_id}.mp3"
    file_path = VOICE_STORAGE_PATH / "responses" / filename

    with open(file_path, "wb") as f:
        f.write(audio_bytes)

    return str(file_path)


# ── Audio file saving ──────────────────────────────────────────────────────

def save_audio_file(
    audio_bytes: bytes,
    user_id: str,
    original_filename: str,
) -> tuple[str, float]:
    """
    Save uploaded/recorded audio to local storage.
    Returns (file_path, duration_seconds).

    duration_seconds is estimated from file size — accurate enough
    for storage tracking. Real duration parsing requires ffprobe.
    """
    _ensure_storage()

    ext = Path(original_filename).suffix.lower() or ".webm"
    filename = f"{user_id}_{uuid.uuid4().hex}{ext}"
    file_path = VOICE_STORAGE_PATH / "samples" / filename

    with open(file_path, "wb") as f:
        f.write(audio_bytes)

    # Rough duration estimate from file size
    # webm/mp3 at decent quality ≈ 16KB/s — good enough for validation
    size_kb = len(audio_bytes) / 1024
    estimated_duration = size_kb / 16.0

    return str(file_path), estimated_duration


# ── Helpers ────────────────────────────────────────────────────────────────

def _mime_type(path: Path) -> str:
    ext = path.suffix.lower()
    return {
        ".mp3":  "audio/mpeg",
        ".wav":  "audio/wav",
        ".m4a":  "audio/mp4",
        ".webm": "audio/webm",
        ".ogg":  "audio/ogg",
        ".flac": "audio/flac",
    }.get(ext, "audio/mpeg")