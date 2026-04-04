"""
app/services/voice_template.py

Loads 200-word voice reading templates by language code.

One file = one language. Each JSON has the same flat shape:
  {language, language_name, language_name_local, title, instruction, text, word_count}

The English passage is always a separate file (en.json) and is served
as the optional second card for non-English users.
It is NOT embedded inside native template files.

Folder: app/data/voice_templates/{language_code}.json

Fallback chain: requested language → en.json → hardcoded string
"""

import json
from pathlib import Path
from functools import lru_cache

TEMPLATE_DIR = Path(__file__).parent.parent / "data" / "voice_templates"

_FALLBACK = {
    "language": "en",
    "language_name": "English",
    "language_name_local": "English",
    "title": "Read this out loud",
    "instruction": "Read naturally at your normal pace.",
    "text": (
        "I woke up late this morning and the first thing I did was check my phone. "
        "There were a few messages I was not expecting, so I just left them on read for a while. "
        "Made some coffee and sat by the window — it was one of those slow mornings where you're "
        "not really thinking about anything, just existing. Later on I had to go out and run some errands. "
        "Nothing serious, just the kind of small tasks that pile up during the week. "
        "On the way back I saw someone I vaguely recognised but could not quite place. "
        "That happens more than I would like. By the time I got home I was not hungry yet "
        "so I just put things away and sat down. I had been meaning to call someone back "
        "for a few days now. Still have not done it. Eventually the evening came around "
        "and I made something simple to eat. Watched a bit of something — nothing memorable. "
        "Before sleeping I always end up thinking about what I should have done differently. "
        "Not in a heavy way, just a passing thought. Then it was quiet and I went to sleep."
    ),
    "word_count": 200,
}


@lru_cache(maxsize=32)
def _load(language: str) -> dict | None:
    """Read and LRU-cache a template file. Returns None if missing or corrupt."""
    path = TEMPLATE_DIR / f"{language}.json"
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def get_template(language: str) -> dict:
    """
    Return the reading template for a language code.
    Fallback: en.json → hardcoded English.

    Shape:
    {
        "language": "my",
        "language_name": "Burmese",
        "language_name_local": "မြန်မာဘာသာ",
        "title": "...",
        "instruction": "...",
        "text": "...",
        "word_count": 200
    }
    """
    lang = (language or "en").lower().strip()
    data = _load(lang)
    if data is None and lang != "en":
        data = _load("en")
    return data if data is not None else dict(_FALLBACK)


def get_english_template() -> dict:
    """
    Always returns the English template.
    Used for the optional English card shown to non-English users.
    """
    data = _load("en")
    return data if data is not None else dict(_FALLBACK)


def list_supported_languages() -> list[str]:
    if not TEMPLATE_DIR.exists():
        return []
    return [p.stem for p in TEMPLATE_DIR.glob("*.json")]