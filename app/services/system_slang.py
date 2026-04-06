"""
app/services/system_slang.py

System-defined slang comprehension dictionary.

Purpose:
  Help the agent UNDERSTAND slang words visitors use in conversation.
  The agent does NOT use these words itself — purely for comprehension.

Structure:
  app/data/slang/{language_code}.json
  Each file is a list of {"word": "...", "meaning": "..."}

Languages:
  my.json → Burmese slang
  en.json → English / internet slang (always included — code-mixing is common)

Adding new words:
  Just edit the JSON file and redeploy. No DB changes needed.

Fallback:
  If a language file doesn't exist → only English slang is loaded.
  If English file doesn't exist → empty list returned.
"""

import json
from pathlib import Path
from functools import lru_cache

SLANG_DIR = Path(__file__).parent.parent / "data" / "slang"


@lru_cache(maxsize=16)
def _load_slang_file(language: str) -> list[dict]:
    """Load and cache a slang file. Returns empty list if missing or corrupt."""
    path = SLANG_DIR / f"{language}.json"
    if not path.exists():
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
            return []
    except (json.JSONDecodeError, OSError):
        return []


def get_system_slang(language: str) -> list[dict]:
    """
    Load system slang for a language.
    Always includes English slang (code-mixing is universal).
    Native language slang added on top if available.

    Returns list of {"word": "...", "meaning": "..."}
    """
    lang = (language or "en").lower().strip()

    # Always load English slang
    en_slang = _load_slang_file("en")

    # Load native slang if different from English
    if lang != "en":
        native_slang = _load_slang_file(lang)
        # Native first, English appended — native takes priority
        combined = native_slang + en_slang
        return combined

    return en_slang


def build_slang_comprehension_block(language: str, message: str) -> str:
    """
    Only inject slang definitions that appear in the visitor's message.
    Returns empty string if no slang detected.
    """
    slang_list = get_system_slang(language)
    if not slang_list:
        return ""

    message_lower = message.lower()

    # Find which slang words appear in the message
    matched = [
        s for s in slang_list
        if s.get("word", "").lower() in message_lower
    ]

    if not matched:
        return ""

    lines = ["SLANG DETECTED — the visitor used these words, understand them as:"]
    for s in matched:
        lines.append(f'  "{s["word"]}" → {s["meaning"]}')

    return "\n".join(lines)