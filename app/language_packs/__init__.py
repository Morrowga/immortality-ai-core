"""
app/language_packs/__init__.py

Language pack loader.

Each language pack is a single Python file named by language code (my.py, th.py, ja.py).
Packs are loaded once at startup and cached in memory — no runtime file I/O.

Usage:
    from app.language_packs import get_language_pack

    pack = get_language_pack("my")   # returns Burmese pack
    pack = get_language_pack("xx")   # returns None for unsupported languages

Contributing a new language:
    1. Copy en.py as a template
    2. Rename to your language code (ISO 639-1)
    3. Fill in all fields — native speaker knowledge required
    4. Submit a PR with native speaker review

Supported languages (add to this list when a pack is merged):
    my — Burmese (မြန်မာဘာသာ)
    en — English
    # th — Thai (add th.py to enable)
    # ja — Japanese (add ja.py to enable)
    # ko — Korean (add ko.py to enable)
    # zh — Chinese Simplified (add zh.py to enable)
    # ar — Arabic (add ar.py to enable)
    # id — Indonesian (add id.py to enable)
"""

import importlib
from types import ModuleType

# Cache — loaded once per process
_pack_cache: dict[str, ModuleType | None] = {}


def get_language_pack(language_code: str) -> ModuleType | None:
    """
    Load and return the language pack module for the given language code.
    Returns None if no pack exists for that language — callers must handle None.

    Cached after first load — safe to call on every request.
    """
    if not language_code:
        return None

    code = language_code.lower().strip()

    if code in _pack_cache:
        return _pack_cache[code]

    try:
        pack = importlib.import_module(f"app.language_packs.{code}")
        _pack_cache[code] = pack
        return pack
    except ModuleNotFoundError:
        # No pack for this language — that's fine, not an error
        _pack_cache[code] = None
        return None
    except Exception as e:
        # Pack exists but has a syntax/import error — log and skip
        print(f"[LANGUAGE PACK] Failed to load pack for '{code}': {e}")
        _pack_cache[code] = None
        return None


def get_generation_rules(language_code: str) -> str:
    """Return GENERATION_RULES string for language, or empty string."""
    pack = get_language_pack(language_code)
    return getattr(pack, "GENERATION_RULES", "") if pack else ""


def get_naturalize_rules(language_code: str) -> str:
    """Return NATURALIZE_RULES string for language, or empty string."""
    pack = get_language_pack(language_code)
    return getattr(pack, "NATURALIZE_RULES", "") if pack else ""


def get_pronoun_rules(language_code: str) -> str:
    """Return PRONOUN_RULES string for language, or empty string."""
    pack = get_language_pack(language_code)
    return getattr(pack, "PRONOUN_RULES", "") if pack else ""


def get_common_mistakes(language_code: str, limit: int = 3) -> list[tuple[str, str]]:
    """Return COMMON_MISTAKES list (wrong, right) pairs, capped at limit."""
    pack = get_language_pack(language_code)
    mistakes = getattr(pack, "COMMON_MISTAKES", []) if pack else []
    return mistakes[:limit]


def get_language_name(language_code: str) -> str:
    """Return the full LANGUAGE_NAME string, or just the code if no pack."""
    pack = get_language_pack(language_code)
    return getattr(pack, "LANGUAGE_NAME", language_code) if pack else language_code