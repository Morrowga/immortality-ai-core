"""
app/neo_packages/__init__.py

Registry of all system packages.

To add a new system package:
  1. Create app/neo_packages/{key}.py following the template
  2. Import it here and add to SYSTEM_PACKAGES

That's it. No DB changes needed for system packages.
"""

from app.neo_packages.life_coach import (
    PACKAGE_KEY as _lc_key,
    TITLE as _lc_title,
    DESCRIPTION as _lc_desc,
    DOMAIN_TAGS as _lc_tags,
    BASE_INSTRUCTIONS as _lc_base,
    EXAMPLE_TOPICS as _lc_topics,
    SAFETY_DISCLAIMER as _lc_disclaimer,
    SENSITIVE as _lc_sensitive,
)

from app.neo_packages.politician import (
    PACKAGE_KEY as _po_key,
    TITLE as _po_title,
    DESCRIPTION as _po_desc,
    DOMAIN_TAGS as _po_tags,
    BASE_INSTRUCTIONS as _po_base,
    EXAMPLE_TOPICS as _po_topics,
    SAFETY_DISCLAIMER as _po_disclaimer,
    SENSITIVE as _po_sensitive,
)

# ── Registry ──────────────────────────────────────────────────────────────
# Each entry is the full package definition dict.
# Add new packages here as you create them.

SYSTEM_PACKAGES: dict[str, dict] = {
    "life_coach": {
        "package_key":        _lc_key,
        "title":              _lc_title,
        "description":        _lc_desc,
        "domain_tags":        _lc_tags,
        "base_instructions":  _lc_base,
        "example_topics":     _lc_topics,
        "safety_disclaimer":  _lc_disclaimer,
        "sensitive":          _lc_sensitive,
    },
    "politician": {
        "package_key":        _po_key,
        "title":              _po_title,
        "description":        _po_desc,
        "domain_tags":        _po_tags,
        "base_instructions":  _po_base,
        "example_topics":     _po_topics,
        "safety_disclaimer":  _po_disclaimer,
        "sensitive":          _po_sensitive,
    },
}


def get_system_package(package_key: str) -> dict | None:
    """Return full package definition or None if not found."""
    return SYSTEM_PACKAGES.get(package_key)


def list_system_packages() -> list[dict]:
    """Return all system packages as a list for the package browser."""
    return [
        {
            "package_key": v["package_key"],
            "title":       v["title"],
            "description": v["description"],
            "sensitive":   v["sensitive"],
            "example_topics": v["example_topics"],
        }
        for v in SYSTEM_PACKAGES.values()
    ]


def get_domain_tags(package_key: str) -> list[str]:
    pkg = SYSTEM_PACKAGES.get(package_key)
    return pkg["domain_tags"] if pkg else []


def get_base_instructions(package_key: str) -> str:
    pkg = SYSTEM_PACKAGES.get(package_key)
    return pkg["base_instructions"] if pkg else ""


def get_example_topics(package_key: str) -> list[str]:
    pkg = SYSTEM_PACKAGES.get(package_key)
    return pkg["example_topics"] if pkg else []


def get_safety_disclaimer(package_key: str) -> str | None:
    pkg = SYSTEM_PACKAGES.get(package_key)
    if not pkg:
        return None
    return pkg["safety_disclaimer"] if pkg.get("sensitive") else None