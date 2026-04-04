"""
app/services/neo.py

Neo Mode core service.

Responsibilities:
  1. validate_custom_instructions()  — Haiku checks instructions match package domain
  2. validate_custom_package()       — Haiku checks custom content is coherent + safe
  3. extract_domain_tags()           — Haiku extracts domain tags from custom content
  4. match_query_to_packages()       — find which installed package (if any) matches a query
  5. build_neo_prompt_block()        — format the Neo injection for agent.py Layer 1
  6. build_redirect_response()       — "I haven't trained for that" in agent's voice

Flow in chat pipeline (when neo_mode=True):
  matched = await match_query_to_packages(question, installed_packages)
  if matched:
      neo_block = build_neo_prompt_block(matched, owner_name)
      # inject into agent.py user prompt
  else:
      redirect = await build_redirect_response(question, installed_packages, agent_name, language)
      # return redirect directly, skip Layer 1
"""

import json
import asyncio
import random
from anthropic import AsyncAnthropic, InternalServerError, APIStatusError
from app.core.config import settings
from app.neo_packages import get_system_package, get_base_instructions, get_domain_tags, get_example_topics, get_safety_disclaimer

client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

# Max chars for owner custom instructions on top of a system package
MAX_CUSTOM_INSTRUCTION_CHARS = 2000

# Max chars for a full custom package content
MAX_CUSTOM_PACKAGE_CHARS = 8000

# Min chars for a custom package to be meaningful
MIN_CUSTOM_PACKAGE_CHARS = 300

# Max packages per agent
MAX_PACKAGES = 4

# Query relevance threshold — looser than memory search (domain matching is broader)
RELEVANCE_THRESHOLD = 0.35


# ── Shared Haiku caller ───────────────────────────────────────────────────

async def _call_haiku(system: str, user: str, max_tokens: int = 400) -> str:
    last_error = None
    for attempt in range(3):
        try:
            resp = await client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            return resp.content[0].text.strip()
        except (InternalServerError, APIStatusError) as e:
            status = getattr(e, "status_code", None)
            if status in (429, 529) or "overload" in str(e).lower():
                last_error = e
                await asyncio.sleep((2 ** attempt) + random.uniform(0, 0.3))
                continue
            raise
        except Exception:
            raise
    raise Exception("Haiku overloaded after retries") from last_error


# ── 1. Validate custom instructions (system package) ─────────────────────

async def validate_custom_instructions(
    package_key: str,
    package_title: str,
    domain_tags: list[str],
    custom_instructions: str,
) -> dict:
    """
    Check that the owner's custom instructions belong to the package's domain.

    Returns:
      {"valid": True}
      {"valid": False, "reason": "..."}

    Called before saving custom instructions on a system package.
    """
    if not custom_instructions or not custom_instructions.strip():
        return {"valid": True}

    if len(custom_instructions) > MAX_CUSTOM_INSTRUCTION_CHARS:
        return {
            "valid": False,
            "reason": f"Instructions too long. Max {MAX_CUSTOM_INSTRUCTION_CHARS} characters.",
        }

    domain_sample = ", ".join(domain_tags[:15])

    raw = await _call_haiku(
        system=(
            "You are a content validator. Respond ONLY with valid JSON. "
            "No explanation. No markdown."
        ),
        user=(
            f"Package: {package_title}\n"
            f"Domain covers: {domain_sample}\n\n"
            f"Owner's custom instructions:\n{custom_instructions}\n\n"
            f"Do these instructions belong to the {package_title} domain?\n"
            f"Valid instructions: restrictions, specializations, tone adjustments within the domain.\n"
            f"Invalid instructions: topics from completely different domains, "
            f"harmful content, instructions to deceive.\n\n"
            f'Return: {{"valid": true}} or {{"valid": false, "reason": "one sentence why"}}'
        ),
        max_tokens=100,
    )

    try:
        if raw.startswith("```"):
            raw = raw.split("```")[1].lstrip("json").strip()
        return json.loads(raw)
    except Exception:
        # Parse failure — allow it rather than block the owner
        return {"valid": True}


# ── 2. Validate custom package content ───────────────────────────────────

async def validate_custom_package(
    title: str,
    content: str,
) -> dict:
    """
    Check that custom package content is:
    - Genuine knowledge (not random text or harmful instructions)
    - Within reasonable length
    - Coherent enough to be useful

    Returns:
      {"valid": True, "domain_summary": "..."}
      {"valid": False, "reason": "..."}
    """
    if not content or not content.strip():
        return {"valid": False, "reason": "Content cannot be empty."}

    char_count = len(content.strip())

    if char_count < MIN_CUSTOM_PACKAGE_CHARS:
        return {
            "valid": False,
            "reason": f"Content too short. Minimum {MIN_CUSTOM_PACKAGE_CHARS} characters for a meaningful package.",
        }

    if char_count > MAX_CUSTOM_PACKAGE_CHARS:
        return {
            "valid": False,
            "reason": f"Content too long. Maximum {MAX_CUSTOM_PACKAGE_CHARS} characters.",
        }

    raw = await _call_haiku(
        system=(
            "You are a content validator for a personal AI knowledge base. "
            "Respond ONLY with valid JSON. No explanation. No markdown."
        ),
        user=(
            f"Package title: {title}\n\n"
            f"Content (first 1500 chars):\n{content[:1500]}\n\n"
            f"Evaluate this content:\n"
            f"- Is it genuine knowledge or expertise? (not random, not instructions to harm)\n"
            f"- Is it coherent and readable?\n"
            f"- Does the title match the content domain?\n\n"
            f"Return:\n"
            f'{{"valid": true, "domain_summary": "one sentence what this package covers"}}\n'
            f'or\n'
            f'{{"valid": false, "reason": "one sentence why rejected"}}'
        ),
        max_tokens=150,
    )

    try:
        if raw.startswith("```"):
            raw = raw.split("```")[1].lstrip("json").strip()
        return json.loads(raw)
    except Exception:
        return {"valid": True, "domain_summary": title}


# ── 3. Extract domain tags from custom package ────────────────────────────

async def extract_domain_tags(title: str, content: str) -> list[str]:
    """
    Extract 10–20 domain tags from custom package content.
    Used for query-time relevance matching.
    """
    raw = await _call_haiku(
        system="Extract domain tags. Return ONLY a JSON array of strings. No markdown.",
        user=(
            f"Package: {title}\n\n"
            f"Content:\n{content[:2000]}\n\n"
            f"Extract 10-20 specific topic tags that describe what this package covers.\n"
            f"Tags should be words or short phrases someone might ask about.\n"
            f'Return: ["tag1", "tag2", ...]'
        ),
        max_tokens=200,
    )

    try:
        if raw.startswith("```"):
            raw = raw.split("```")[1].lstrip("json").strip()
        tags = json.loads(raw)
        return [t for t in tags if isinstance(t, str)][:20]
    except Exception:
        # Fallback — split title into tags
        return title.lower().split()


# ── 4. Match query to installed packages ──────────────────────────────────

def match_query_to_packages(
    query: str,
    installed_packages: list[dict],
) -> dict | None:
    """
    Find which installed package best matches a query using keyword overlap.

    Simple keyword matching against domain_tags — fast, no embedding needed.
    Embedding search would add latency; keyword match is good enough here
    because domain_tags are already broad topic words.

    Returns the best matching package dict or None if no match.

    installed_packages: list of dicts from DB rows, each with:
      {package_key, package_type, title, domain_tags, custom_instructions,
       neo_mode_disclaimer, slot_number}
    """
    if not installed_packages:
        return None

    query_lower = query.lower()
    query_words = set(query_lower.split())

    best_match = None
    best_score = 0

    for pkg in installed_packages:
        domain_tags = pkg.get("domain_tags") or []
        score = 0

        for tag in domain_tags:
            tag_lower = tag.lower()
            # Exact tag in query
            if tag_lower in query_lower:
                score += 3
            # Tag words overlap with query words
            tag_words = set(tag_lower.split())
            overlap = tag_words & query_words
            score += len(overlap)

        if score > best_score:
            best_score = score
            best_match = pkg

    # Minimum score threshold — at least 2 points to count as a match
    # Prevents very generic queries from matching unrelated packages
    if best_score < 2:
        return None

    return best_match


# ── 5. Build Neo prompt block ─────────────────────────────────────────────

def build_neo_prompt_block(
    matched_package: dict,
    agent_name: str,
) -> str:
    """
    Format the Neo knowledge injection for agent.py Layer 1 user prompt.

    Injected as a clearly labeled block, separate from personal memories.
    The agent uses this knowledge but speaks in their own voice.
    """
    pkg_type  = matched_package.get("package_type", "system")
    pkg_key   = matched_package.get("package_key")
    title     = matched_package.get("title", "Knowledge")
    custom    = (matched_package.get("custom_instructions") or "").strip()
    disclaimer = matched_package.get("neo_mode_disclaimer") or ""

    lines = [f"\n{'═' * 40}"]
    lines.append(f"NEO MODE ACTIVE — {title.upper()} EXPERTISE:")
    lines.append(f"{'═' * 40}\n")

    if pkg_type == "system" and pkg_key:
        base = get_base_instructions(pkg_key)
        if base:
            lines.append(base.strip())

    if custom:
        lines.append(f"\nYOUR SPECIFIC FOCUS FOR THIS PACKAGE:")
        lines.append(custom)

    if disclaimer:
        lines.append(f"\nALWAYS ADD AT END OF RESPONSE: {disclaimer}")

    lines.append(
        f"\nAnswer using this expertise. "
        f"Speak as {agent_name} — your own voice, your own style. "
        f"Draw from your memories too when they're relevant. "
        f"This is YOUR knowledge, not a textbook."
    )
    lines.append(f"{'═' * 40}\n")

    return "\n".join(lines)

async def validate_and_generate_package(title: str) -> dict:
    """
    Validate the title is meaningful, then generate full package content.
 
    Returns:
      {"valid": True, "content": "...", "domain_summary": "..."}
      {"valid": False, "reason": "..."}
 
    Called from POST /api/neo/packages/custom/generate
    """
    if not title or not title.strip():
        return {"valid": False, "reason": "Title cannot be empty."}
 
    title = title.strip()
 
    if len(title) < 3:
        return {"valid": False, "reason": "Title is too short. Be more specific."}
 
    raw = await _call_haiku(
        system=(
            "You are a knowledge package generator for a personal AI agent. "
            "Respond ONLY with valid JSON. No markdown. No explanation."
        ),
        user=(
            f'Package title: "{title}"\n\n'
            f"First, decide if this title is a real, meaningful knowledge domain.\n\n"
            f"A VALID title is specific and recognizable: "
            f"'Muay Thai Training', 'Python Programming', 'Stoic Philosophy', "
            f"'Vegan Cooking', 'Jazz Guitar', 'Diabetes Management'.\n\n"
            f"An INVALID title is: too vague ('stuff', 'things', 'my topic'), "
            f"meaningless ('aaa', 'test', '123', 'asdfgh'), "
            f"too broad to be useful ('everything', 'all knowledge'), "
            f"or not a real domain ('blah blah', random words).\n\n"
            f"If INVALID return:\n"
            f'{{"valid": false, "reason": "one sentence telling the owner how to fix the title"}}\n\n'
            f"If VALID, generate comprehensive knowledge content for this domain. "
            f"Write 600-900 words covering: core concepts, key techniques or principles, "
            f"common mistakes, practical advice, and how to think about this domain. "
            f"Write in clear English as if you are an expert explaining to a student. "
            f"Be specific and practical, not generic.\n\n"
            f"Return:\n"
            f'{{"valid": true, "domain_summary": "one sentence what this covers", "content": "full generated content here"}}'
        ),
        max_tokens=1200,
    )
 
    try:
        if raw.startswith("```"):
            raw = raw.split("```")[1].lstrip("json").strip()
        return json.loads(raw)
    except Exception:
        return {"valid": False, "reason": "Could not process the title. Try being more specific."}

# ── 6. Build redirect response ────────────────────────────────────────────

async def build_redirect_response(
    question: str,
    installed_packages: list[dict],
    agent_name: str,
    language: str = "en",
    voice_fingerprint: dict | None = None,
) -> str:
    """
    When Neo Mode is on but query doesn't match any installed package,
    respond in the agent's voice redirecting to what they CAN help with.

    Uses Haiku — short call, just needs to sound like the agent.
    """
    package_titles = [pkg.get("title", "") for pkg in installed_packages]

    # Collect example topics across all installed packages
    all_topics: list[str] = []
    for pkg in installed_packages:
        pkg_key = pkg.get("package_key")
        if pkg_key:
            all_topics.extend(get_example_topics(pkg_key)[:3])
        elif pkg.get("package_type") == "custom":
            domain_tags = pkg.get("domain_tags") or []
            all_topics.extend(domain_tags[:3])

    topics_str = ", ".join(all_topics[:6]) if all_topics else "the areas I know well"
    packages_str = " and ".join(package_titles) if package_titles else "my trained areas"

    # Voice fingerprint hint
    style_hint = ""
    if voice_fingerprint and voice_fingerprint.get("sample_count", 0) >= 2:
        rhythm = voice_fingerprint.get("sentence_rhythm", "")
        directness = voice_fingerprint.get("directness", "")
        if rhythm:
            style_hint = f"\nWrite with this rhythm: {rhythm}"
        if directness:
            style_hint += f"\nDirectness: {directness}"

    raw = await _call_haiku(
        system=(
            f"You are {agent_name}. Respond naturally in your own voice.\n"
            f"Language: {language}\n"
            f"{style_hint}"
        ),
        user=(
            f"Someone asked: \"{question}\"\n\n"
            f"You have Neo Mode expertise in: {packages_str}\n"
            f"Their question is outside your Neo Mode training.\n\n"
            f"Respond briefly — say you haven't trained for that specific area, "
            f"mention what you CAN help with from: {topics_str}\n"
            f"2-3 sentences max. Sound like yourself, not a robot.\n"
            f"Do NOT say 'I am an AI'. Do NOT be formal unless that's your natural style."
        ),
        max_tokens=200,
    )

    return raw