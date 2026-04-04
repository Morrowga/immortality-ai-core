"""
app/services/survey.py

Stripped down from the old survey service.

Old version: extracted personality profiles, built complex summaries, ran
relationship voice extraction. All removed.

New version:
  - build_identity_summary()   → formats identity facts for the agent prompt
  - extract_relationship_voice() → kept, used by relationship setup
  - naturalize_response()        → kept, used by chat pipeline — now injects language pack rules
  - extract_language_samples_from_text() → kept, used by training
  - assign_person_to_zone()      → kept, used by relationship setup

Everything related to personality survey extraction is gone.
The agent's "personality" now comes entirely from training memories.
"""

import json
import random
import asyncio
from anthropic import AsyncAnthropic, InternalServerError, APIStatusError
from app.core.config import settings
from app.language_packs import get_naturalize_rules

client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

LANGUAGE_SCRIPT_NAMES = {
    "my": "Burmese (Myanmar script — မြန်မာဘာသာ). NOT Chinese. NOT Japanese. Myanmar Unicode only.",
    "th": "Thai (Thai script — ภาษาไทย). NOT Chinese.",
    "zh": "Chinese (Simplified — 中文)",
    "ja": "Japanese (hiragana/katakana/kanji)",
    "ko": "Korean (Hangul — 한국어)",
    "ar": "Arabic (Arabic script — العربية)",
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "id": "Indonesian",
}

ZONE_DESCRIPTIONS = {
    1: "intimate — partner/lover/soulmate. Zero guards. Full emotional truth. Most themselves.",
    2: "core family — mother/father/sibling/grandparent/who raised them. Deep love, complex dynamic, cultural respect rules apply.",
    3: "chosen close — best friend/mentor/trusted old friend. Honest, personal, trusted.",
    4: "social circle — friend/colleague/classmate/distant family. Warm but lighter, not deeply personal.",
    5: "formal/stranger — coworker/boss/stranger/unknown. Polite, guarded, professional.",
}


# ── Shared Claude call with retry ─────────────────────────────────────────

async def _call_claude(
    messages: list[dict],
    system: str = None,
    model: str = "claude-haiku-4-5-20251001",
    max_tokens: int = 1000,
) -> str:
    """
    Shared retry-wrapped Claude call.
    Defaults to Haiku — callers that need Sonnet pass model explicitly.
    """
    last_error = None
    for attempt in range(5):
        try:
            kwargs = dict(model=model, max_tokens=max_tokens, messages=messages)
            if system:
                kwargs["system"] = system
            response = await client.messages.create(**kwargs)
            return response.content[0].text.strip()
        except (InternalServerError, APIStatusError) as e:
            status = getattr(e, "status_code", None)
            err = str(e).lower()
            if status in (429, 529) or "overload" in err:
                last_error = e
                wait = 5 * (attempt + 1) if status == 429 else 2 ** attempt
                await asyncio.sleep(wait + random.uniform(0, 0.5))
                continue
            raise
    from fastapi import HTTPException
    raise HTTPException(
        status_code=503,
        detail="Anthropic overloaded. Try again shortly."
    ) from last_error


def _parse_json(raw: str) -> dict | list:
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()
    print(f"[PARSE JSON] full raw response:\n{raw}")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"[PARSE JSON ERROR] failed at char {e.pos}. Length: {len(raw)}")
        print(f"[PARSE JSON ERROR] last 200 chars: {raw[-200:]}")
        raise


# ── Identity summary ──────────────────────────────────────────────────────

def build_identity_summary(
    full_name: str,
    age: int | None,
    birthdate: str | None,
    blood_type: str | None,
    zodiac_sign: str | None,
    current_location: str | None,
    past_locations: list[str],
    language: str = "en",
) -> str:
    """
    Build a short identity anchor string for the agent system prompt.
    This is injected as the personality foundation since there's no longer
    a personality survey. Real personality comes from training memories.

    Deliberately minimal — just anchors who the person is.
    The agent learns HOW they are through memories, not survey questions.
    """
    lang_name = LANGUAGE_SCRIPT_NAMES.get(language, language)
    lines = ["IDENTITY FACTS — who this person is:"]

    if full_name:
        lines.append(f"  Name: {full_name}")
    if age:
        lines.append(f"  Age: {age}")
    if birthdate:
        lines.append(f"  Born: {birthdate}")
    if blood_type and blood_type not in ("", "I don't know"):
        lines.append(f"  Blood type: {blood_type}")
    if zodiac_sign:
        lines.append(f"  Zodiac: {zodiac_sign}")
    if current_location:
        lines.append(f"  Currently in: {current_location}")
    if past_locations:
        lines.append(f"  Previously lived: {', '.join(past_locations)}")

    lines.append(f"\n  Primary language: {lang_name}")
    lines.append(
        "\nThis agent has no pre-loaded personality profile. "
        "Everything you know about this person comes from their training memories. "
        "If you don't have a memory about something — say so. Don't invent."
    )

    return "\n".join(lines)


# ── Relationship voice extraction ─────────────────────────────────────────

async def extract_relationship_voice(
    person_name: str,
    person_role: str,
    zone: int,
    how_i_talk_to_them: str,
    chat_samples: list[str],
    language: str,
) -> dict:
    """
    Extract the voice a person uses with one specific person.
    Used when a RelationshipProfile is created or updated with chat samples.
    """
    lang_name = LANGUAGE_SCRIPT_NAMES.get(language, language)
    zone_desc = ZONE_DESCRIPTIONS.get(zone, "")

    samples_block = ""
    if chat_samples:
        samples_block = f"\nReal messages sent TO {person_name}:\n"
        for i, s in enumerate(chat_samples[:12], 1):
            samples_block += f"  {i}. {s}\n"

    prompt = f"""Extract the voice a person uses with one specific person in their life.
Used to make an AI agent sound exactly like them when talking to {person_name}.

Zone: {zone_desc}
Person: {person_name}
Role: {person_role}
Language: {lang_name}

How they describe talking to this person:
{how_i_talk_to_them or "No description provided."}
{samples_block}

Return ONLY valid JSON:
{{
  "tone_summary": "2 sentences max",
  "openness_level": 7.5,
  "warmth_level": 8.0,
  "humor_level": 6.0,
  "formality_level": 2.0,
  "swearing_level": 3.0,
  "affection_level": 9.0,
  "sentence_style": "short/medium/long",
  "topic_range": "one sentence",
  "restricted_topics": ["topic1", "topic2"],
  "key_behaviours": ["behaviour1", "behaviour2"],
  "voice_summary": "4-5 sentences. How to sound when talking to {person_name}. Address form, self-address, tone, rhythm, emotional openness."
}}"""

    raw = await _call_claude(
        [{"role": "user", "content": prompt}],
        model="claude-sonnet-4-6",
        max_tokens=800,
    )
    return _parse_json(raw)


async def assign_person_to_zone(
    person_name: str,
    person_description: str,
) -> int:
    prompt = f"""Assign this person to the correct emotional distance zone.

Person: {person_name}
Description: {person_description}

Zones:
1 = intimate: partner, lover, soulmate
2 = core family: mother, father, sibling, grandparent
3 = chosen close: best friend, mentor, deeply trusted
4 = social circle: friend, colleague, classmate, distant family
5 = formal/stranger: coworker, boss, stranger, unknown

Return ONLY a single integer (1, 2, 3, 4, or 5). Nothing else."""

    raw = await _call_claude(
        [{"role": "user", "content": prompt}],
        max_tokens=10,
    )
    try:
        return int(raw.strip())
    except ValueError:
        return 4


# ── Language naturalizer ──────────────────────────────────────────────────

async def naturalize_response(
    draft_response: str,
    language: str,
    real_samples: list[str],
    zone: int = 4,
    relationship_voice_summary: str = "",
) -> str:
    """
    Layer 2 — rewrite draft to match the trainer's real writing rhythm.

    Short-circuits if no samples and no voice summary — returns draft as-is.
    Injects language pack naturalization rules if a pack exists for this language.
    """
    if not real_samples and not relationship_voice_summary:
        return draft_response

    lang_name = LANGUAGE_SCRIPT_NAMES.get(language, language)
    zone_desc = ZONE_DESCRIPTIONS.get(zone, "")

    samples_block = ""
    if real_samples:
        samples_block = f"\nReal examples of how this person writes ({lang_name}):\n"
        for s in real_samples[:6]:
            samples_block += f'  "{s}"\n'

    voice_block = ""
    if relationship_voice_summary:
        voice_block = f"\nVoice guide:\n{relationship_voice_summary}\n"

    # ── Language pack naturalization rules ────────────────────────────────
    # Injected only if a pack exists — transparent no-op for unsupported languages
    nat_rules = get_naturalize_rules(language)
    pack_block = ""
    if nat_rules:
        pack_block = f"\nLanguage-specific rules:\n{nat_rules}\n"

    prompt = f"""Rewrite this message to sound exactly like how this specific person naturally writes.

DO NOT change meaning, facts, or emotional content.
ONLY change: sentence rhythm, word choice, formality, natural language patterns.

Target language: {lang_name}
Relationship: {zone_desc}
{samples_block}
{voice_block}
{pack_block}

Draft:
{draft_response}

Rules:
- Match rhythm and length of real samples
- Mix languages exactly as they do
- Short if they write short. Fragments if they use fragments.
- Do NOT make it more formal
- Do NOT add content not in the draft
- Output ONLY the rewritten message."""

    return await _call_claude(
        [{"role": "user", "content": prompt}],
        model="claude-haiku-4-5-20251001",
        max_tokens=600,
    )


# ── Language sample extraction ─────────────────────────────────────────────

async def extract_language_samples_from_text(
    text: str,
    language: str,
    agent_id: str,
    user_id: str,
    zone: int = None,
    source: str = "training",
) -> list[dict]:
    """
    Extract natural conversational sentences from training input.
    Stored as LanguageSample rows — used by naturalize_response later.
    """
    if len(text) < 20:
        return []

    prompt = f"""Extract natural conversational sentences from this text.

Text: {text}

Rules:
- Only natural and conversational sentences
- 3-6 sentences maximum
- Preserve EXACTLY as written — do not clean, translate, or fix
- Include language mixing if present
- Skip sentences under 5 words or too generic
- Return ONLY a JSON array of strings.

Example: ["ဒါကြောင့် မသွားတော့ဘူး lol", "အခုတော့ okay ဖြစ်သွားပြီ"]"""

    raw = await _call_claude(
        [{"role": "user", "content": prompt}],
        max_tokens=400,
    )
    try:
        sentences = _parse_json(raw)
        if not isinstance(sentences, list):
            return []
        return [
            {
                "user_id": user_id,
                "agent_id": agent_id,
                "language": language,
                "sample_text": s,
                "relationship_zone": zone,
                "source": source,
            }
            for s in sentences
            if isinstance(s, str) and len(s) > 5
        ]
    except Exception:
        return []