import json
import asyncio
from anthropic import AsyncAnthropic, InternalServerError, APIStatusError
from app.core.config import settings
from sqlalchemy.ext.asyncio import AsyncSession

client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)


EXTRACTION_PROMPT = """You are a deep memory extraction system for a personal AI agent.
Your job is to extract the feeling layer from what this person shared.
Not just what happened — but how it felt, why it mattered, what instinct it formed.

You must return ONLY valid JSON. No explanation. No markdown. Just JSON.

LANGUAGE RULES — critical:
- The *_original fields must preserve EXACTLY how the person said it.
  If they mixed languages (e.g. Burmese + English mid-sentence), keep the mix exactly as-is.
  Do NOT clean it up. Do NOT translate it. Do NOT make it "proper".
  The original field is their authentic voice. Preserve it.
- The base fields (what_happened, how_i_felt, etc.) must always be clean English.
  Translate fully. Rephrase naturally. These are for semantic search — clarity matters.
- If the input is already pure English, both fields will be identical.

Return this exact structure:
{{
  "what_happened": "Clean English — what happened",
  "what_happened_original": "Exact original — preserve any language mix as-is",
  "context": "When, where, who was involved — English",
  "how_i_felt": "Clean English — exact emotional state",
  "how_i_felt_original": "Exact original — preserve any language mix",
  "why_it_mattered": "Clean English — the weight and significance",
  "why_it_mattered_original": "Exact original — preserve any language mix",
  "what_i_learned": "Clean English — lesson formed",
  "what_i_learned_original": "Exact original — preserve any language mix",
  "instinct_formed": "Clean English — future behavior this created",
  "instinct_formed_original": "Exact original — preserve any language mix",
  "cultural_expression_notes": "How their culture or language shapes how they express this",
  "suggested_weight": 0.0,
  "never_forget": false,
  "pattern_tags": [],
  "section": "PAST",
  "cross_sections": [],
  "is_core_memory": false
}}

Rules for suggested_weight (0-10):
  9-10 = life-defining moment, permanent instinct formed
  7-8  = significant experience, clear lesson learned
  5-6  = meaningful but not defining
  3-4  = minor experience, some reflection
  1-2  = passing thought, low impact

Rules for section:
  BASIC   = identity, personality, values, who they are
  PAST    = history, childhood, turning points, lessons
  PRESENT = current life, current feelings, current struggles
  FUTURE  = dreams, goals, legacy, what they want for loved ones

Rules for never_forget:
  true only if suggested_weight >= 8.5

Rules for pattern_tags:
  3-7 tags that describe life areas this touches
  examples: family, money, trust, resilience, career, love, loss, identity"""


FINGERPRINT_PROMPT = """You are analyzing HOW a person communicates — not WHAT they said.
Look only at the writing style, rhythm, voice, and energy of the raw text.
Ignore the content entirely. Focus on the delivery.

You must return ONLY valid JSON. No explanation. No markdown. Just JSON.

Return this exact structure:
{{
  "sentence_rhythm": "One sentence describing their sentence length and rhythm pattern",
  "directness": "One sentence — do they jump straight in, or build up slowly?",
  "humor_style": "One sentence — how do they use humor, if at all?",
  "trailing_style": "One sentence — how do they end thoughts? Firm, trailing off, abrupt?",
  "code_mix_words": ["list", "of", "foreign", "loanwords", "they", "use", "naturally"],
  "filler_patterns": ["list", "of", "filler", "words", "or", "particles", "they", "repeat"],
  "emotional_expression": "One sentence — direct about feelings or wraps them in indirection?",
  "energy_level": "One sentence — calm/intense/fluctuating? What signals this?",
  "sentence_starters": "One sentence — how do they typically open a sentence or thought?"
}}

Rules:
- code_mix_words: only words from a different language than the primary text
  e.g. English words inside Burmese text: ["lol", "okay", "honestly", "actually"]
  e.g. Burmese words inside English text: ["ဟာ", "ပြီး"]
- filler_patterns: words/particles that appear repeatedly and signal rhythm
- If a field is genuinely not observable from this short text, write "not enough data"
- Be SPECIFIC — not generic. "writes short punchy sentences" not "communicates clearly"
- Max 15 words per string value"""


async def extract_memory(
    text: str,
    language: str = "en",
    style_context: str = "",
) -> tuple[dict, int]:
    """
    Returns (extracted_memory_dict, tokens_used).
    tokens_used = input_tokens + output_tokens for this call.
    """
    user_prompt = f"""User's primary language: {language}
Style context: {style_context if style_context else "No prior style data yet"}

What the person shared (may be in {language}, English, or a mix — handle all cases):
{text}

Extract the felt memory. Preserve original voice exactly. Return only JSON."""

    import random
    last_error = None
    max_attempts = 5
    for attempt in range(max_attempts):
        try:
            response = await client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=6000,
                system=EXTRACTION_PROMPT,
                messages=[{"role": "user", "content": user_prompt}]
            )
            break
        except (InternalServerError, APIStatusError) as e:
            status = getattr(e, "status_code", None)
            err_str = str(e).lower()
            is_overload = status == 529 or "overloaded" in err_str or "overload" in err_str
            is_rate_limit = status == 429
            if is_overload or is_rate_limit:
                last_error = e
                if attempt < max_attempts - 1:
                    base_wait = 5 * (attempt + 1) if is_rate_limit else (2 ** attempt)
                    await asyncio.sleep(base_wait + random.uniform(0, 0.5))
                continue
            raise
    else:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="Anthropic is currently overloaded. Please try again in a moment.") from last_error

    tokens_used = response.usage.input_tokens + response.usage.output_tokens

    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    return json.loads(raw), tokens_used


async def extract_voice_fingerprint(
    text: str,
    language: str = "en",
) -> tuple[dict | None, int]:
    """
    Returns (fingerprint_dict_or_None, tokens_used).
    tokens_used = 0 if text is too short or call fails.
    """
    if not text or len(text.strip()) < 30:
        return None, 0

    import random
    user_prompt = f"""Primary language of writer: {language}

Raw text to analyze (focus on HOW they write, not WHAT they say):
{text[:1500]}

Return only JSON."""

    last_error = None
    for attempt in range(3):
        try:
            response = await client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=600,
                system=FINGERPRINT_PROMPT,
                messages=[{"role": "user", "content": user_prompt}]
            )
            tokens_used = response.usage.input_tokens + response.usage.output_tokens
            raw = response.content[0].text.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            raw = raw.strip()
            return json.loads(raw), tokens_used

        except (InternalServerError, APIStatusError) as e:
            status = getattr(e, "status_code", None)
            err_str = str(e).lower()
            if status in (429, 529) or "overload" in err_str:
                last_error = e
                await asyncio.sleep((2 ** attempt) + random.uniform(0, 0.3))
                continue
            return None, 0
        except Exception:
            return None, 0

    return None, 0


def merge_voice_fingerprints(
    existing: dict | None,
    new: dict | None,
) -> dict | None:
    if not new:
        return existing
    if not existing:
        result = dict(new)
        result["sample_count"] = 1
        return result

    merged = dict(existing)
    sample_count = existing.get("sample_count", 1) + 1
    merged["sample_count"] = sample_count

    string_fields = [
        "sentence_rhythm", "directness", "humor_style", "trailing_style",
        "emotional_expression", "energy_level", "sentence_starters",
    ]
    for field in string_fields:
        new_val = new.get(field, "")
        if new_val and new_val != "not enough data":
            existing_val = existing.get(field, "")
            if not existing_val or existing_val == "not enough data":
                merged[field] = new_val
            else:
                if sample_count <= 3:
                    merged[field] = new_val

    for field in ["code_mix_words", "filler_patterns"]:
        existing_list = existing.get(field) or []
        new_list = new.get(field) or []
        combined = list(dict.fromkeys(existing_list + new_list))
        merged[field] = combined[:15]

    return merged


def format_voice_fingerprint_for_prompt(fingerprint: dict | None) -> str:
    if not fingerprint:
        return ""

    sample_count = fingerprint.get("sample_count", 0)
    if sample_count < 2:
        return ""

    lines = ["HOW THIS PERSON WRITES — match this exactly:"]

    fields = [
        ("sentence_rhythm",      "Sentence rhythm"),
        ("directness",           "Directness"),
        ("humor_style",          "Humor"),
        ("trailing_style",       "How they end thoughts"),
        ("emotional_expression", "Emotional expression"),
        ("energy_level",         "Energy"),
        ("sentence_starters",    "How they start sentences"),
    ]

    for key, label in fields:
        val = fingerprint.get(key, "")
        if val and val != "not enough data":
            lines.append(f"  {label}: {val}")

    code_mix = fingerprint.get("code_mix_words") or []
    if code_mix:
        lines.append(f"  Code-mix words they use naturally: {', '.join(code_mix[:8])}")

    fillers = fingerprint.get("filler_patterns") or []
    if fillers:
        lines.append(f"  Filler/rhythm words: {', '.join(fillers[:8])}")

    lines.append(
        f"\n  (Built from {sample_count} training sessions — "
        f"this is how they actually write, not how they should write)"
    )

    return "\n".join(lines)


async def generate_acknowledgment(
    memory: dict,
    user_name: str,
    language: str = "en",
) -> str:
    """
    Generates an acknowledgment message. Returns text only — tokens not tracked
    because this is a UX call after deduction has already been made.
    """
    prompt = f"""The user just shared a memory with their personal AI agent.
The agent should acknowledge it — show it understood the feeling, not just the facts.

User's name: {user_name}
User's primary language: {language}
Memory weight: {memory.get('suggested_weight', 5)}/10
Never forget: {memory.get('never_forget', False)}

What happened: {memory.get('what_happened', '')}
How they felt: {memory.get('how_i_felt', '')}
Instinct formed: {memory.get('instinct_formed', '')}

Write a response that:
- Is 2-4 sentences only
- Shows you felt the weight of what they shared
- Mentions the instinct or lesson formed
- Does NOT say "I have saved this" or "I will remember this" — show don't tell
- Responds in {language} — if the person naturally mixes languages, you can too
- Feels warm and human, not robotic"""

    import random
    last_error = None
    max_attempts = 5
    for attempt in range(max_attempts):
        try:
            response = await client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=300,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text.strip()
        except (InternalServerError, APIStatusError) as e:
            status = getattr(e, "status_code", None)
            err_str = str(e).lower()
            is_overload = status == 529 or "overloaded" in err_str or "overload" in err_str
            is_rate_limit = status == 429
            if is_overload or is_rate_limit:
                last_error = e
                if attempt < max_attempts - 1:
                    base_wait = 5 * (attempt + 1) if is_rate_limit else (2 ** attempt)
                    await asyncio.sleep(base_wait + random.uniform(0, 0.5))
                continue
            raise
    from fastapi import HTTPException
    raise HTTPException(status_code=503, detail="Anthropic is currently overloaded. Please try again in a moment.") from last_error


async def check_duplicate_memory(
    embedding: list[float],
    agent_id: str,
    db: AsyncSession,
    threshold: float = 0.85,
) -> dict | None:
    embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"

    raw_conn = await db.connection()
    asyncpg_conn = await raw_conn.get_raw_connection()
    native_conn = asyncpg_conn.driver_connection

    rows = await native_conn.fetch("""
        SELECT
            id::text AS memory_id,
            what_happened,
            how_i_felt,
            feeling_weight,
            reinforcement_count,
            never_forget,
            section,
            1 - (embedding <=> $1::vector) AS similarity
        FROM memories
        WHERE
            agent_id = $2::uuid
            AND is_active = true
            AND embedding IS NOT NULL
        ORDER BY embedding <=> $1::vector
        LIMIT 1
    """, embedding_str, agent_id)

    if not rows:
        return None

    top = dict(rows[0])
    if top["similarity"] >= threshold:
        return top

    return None


async def reinforce_memory(
    memory_id: str,
    db: AsyncSession,
) -> dict:
    from sqlalchemy import select
    from app.models.user import Memory
    from datetime import datetime
    import uuid

    result = await db.execute(
        select(Memory).where(Memory.id == uuid.UUID(memory_id))
    )
    memory = result.scalar_one_or_none()
    if not memory:
        return {}

    memory.reinforcement_count = (memory.reinforcement_count or 0) + 1
    memory.last_reinforced_at = datetime.utcnow()
    memory.feeling_weight = min(10.0, (memory.feeling_weight or 5.0) + 0.2)
    memory.never_forget = memory.feeling_weight >= 8.5

    await db.commit()

    return {
        "memory_id": str(memory.id),
        "what_happened": memory.what_happened,
        "feeling_weight": memory.feeling_weight,
        "reinforcement_count": memory.reinforcement_count,
    }