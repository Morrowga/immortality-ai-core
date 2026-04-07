"""
app/neo_packages/__init__.py

Auto-discovery registry — no manual imports needed.

To add a new system package:
  1. Create app/neo_packages/{key}.py following the template
  2. That's it. It registers itself automatically.

Required fields in each package file:
  PACKAGE_KEY, TITLE, DESCRIPTION, DOMAIN_TAGS,
  BASE_INSTRUCTIONS, EXAMPLE_TOPICS, SAFETY_DISCLAIMER, SENSITIVE
"""

import importlib
import pkgutil
from pathlib import Path

# ── Auto-discover all package files in this folder ────────────────────────

SYSTEM_PACKAGES: dict[str, dict] = {}

for _finder, _module_name, _ in pkgutil.iter_modules([str(Path(__file__).parent)]):
    try:
        _module = importlib.import_module(f"app.neo_packages.{_module_name}")
    except Exception:
        continue

    # Only register files that define PACKAGE_KEY
    if not hasattr(_module, "PACKAGE_KEY"):
        continue

    _key = _module.PACKAGE_KEY
    SYSTEM_PACKAGES[_key] = {
        "package_key":        _key,
        "title":              getattr(_module, "TITLE",               _key),
        "description":        getattr(_module, "DESCRIPTION",         ""),
        "domain_tags":        getattr(_module, "DOMAIN_TAGS",         []),
        "base_instructions":  getattr(_module, "BASE_INSTRUCTIONS",   ""),
        "example_topics":     getattr(_module, "EXAMPLE_TOPICS",      []),
        "safety_disclaimer":  getattr(_module, "SAFETY_DISCLAIMER",   None),
        "sensitive":          getattr(_module, "SENSITIVE",           False),
    }


# ── Public API — identical to before, nothing in neo.py needs to change ──

def get_system_package(package_key: str) -> dict | None:
    """Return full package definition or None if not found."""
    return SYSTEM_PACKAGES.get(package_key)


def list_system_packages() -> list[dict]:
    """Return all system packages as a list for the package browser."""
    return [
        {
            "package_key":    v["package_key"],
            "title":          v["title"],
            "description":    v["description"],
            "sensitive":      v["sensitive"],
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