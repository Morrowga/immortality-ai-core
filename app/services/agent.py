import random
import asyncio
from anthropic import AsyncAnthropic, InternalServerError, APIStatusError
from app.core.config import settings
from app.language_packs import get_generation_rules, get_common_mistakes, get_language_name
from app.services.extraction import format_voice_fingerprint_for_prompt
from datetime import datetime, timezone

client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

ZONE_TONE_GUIDE = {
    1: "This is their most intimate person. Zero guards. Full emotional truth. Respond exactly how they would think in their own head — vulnerable, honest, affectionate.",
    2: "This is core family. Deep love but with the specific dynamic of that relationship. Respect cultural address forms exactly. Can be complex — love and frustration coexist.",
    3: "This is a chosen close person. Trusted, honest, personal. Share things openly. Casual, real, no performance.",
    4: "This is a social circle person. Warm but lighter. Not deeply personal. Friendly energy, don't overshare.",
    5: "This is a formal contact or stranger. Polite, measured, professional tone. Still answer — just with appropriate distance.",
}


def _pick_best_address_form(address_forms: list[dict], speaker_name: str = "") -> str:
    if not address_forms:
        return speaker_name or ""
    for f in address_forms:
        form = f.get("form", "")
        ctx  = (f.get("context", "") or "").lower()
        if form and form not in ("skip", "__custom__") and ctx == "always":
            return speaker_name if form == "name" else form
    for f in address_forms:
        form = f.get("form", "")
        if form and form not in ("skip", "__custom__"):
            return speaker_name if form == "name" else form
    return speaker_name or ""


def _format_self_address_forms(self_address_forms: list[dict]) -> str:
    if not self_address_forms:
        return ""
    lines = []
    for f in self_address_forms:
        form = f.get("form", "")
        ctx  = f.get("context", "") or ""
        if not form:
            continue
        lines.append(f'  - "{form}" — {ctx}')
    return "\n".join(lines)


async def generate_agent_response(
    question: str,
    memories: list[dict],
    patterns: list[dict],
    style: dict,
    agent_name: str,
    language: str = "en",
    slang: list[dict] = [],
    personality: str = "",
    speaker_name: str = "",
    is_owner: bool = True,
    relationship_context: str = "",
    relationship_profile: dict = None,
    conversation_history: list[dict] = [],
    language_samples: list[str] = [],
    known_people: list[dict] = [], 
) -> str:

    # ── Style context ───────────────────────────────────────────────────────
    style_context = ""
    if style:
        fingerprint_block = format_voice_fingerprint_for_prompt(
            style.get("voice_fingerprint")
        )
        if fingerprint_block:
            style_context = f"\n{fingerprint_block}\n"
        else:
            style_context = f"""
Communication style:
  Pace: {style.get('avg_speaking_pace', 'medium')}
  Directness: {style.get('directness_level', 5)}/10
  Warmth: {style.get('warmth_level', 5)}/10
  Humor: {style.get('humor_level', 5)}/10
"""

    # ── Slang context ───────────────────────────────────────────────────────
    slang_context = ""
    if slang:
        slang_context = "\nYour personal slang and expressions:\n"
        for s in slang:
            slang_context += f"\n  \"{s['word_or_phrase']}\"\n"
            slang_context += f"    Meanings: {', '.join(s['meanings'])}\n"
            if s.get("example_sentences"):
                for ex in s["example_sentences"]:
                    slang_context += f"      - {ex}\n"
            if s.get("grammar_note"):
                slang_context += f"    Grammar: {s['grammar_note']}\n"
        slang_context += "\nUse naturally. Only when meaning fits.\n"

    # ── Language samples ────────────────────────────────────────────────────
    samples_context = ""
    if language_samples:
        samples_context = "\nYOUR REAL WRITING STYLE — match this rhythm and energy exactly:\n"
        for s in language_samples[:6]:
            samples_context += f'  "{s}"\n'
        samples_context += "The examples above are how you actually write. Your response must feel like those.\n"

    # ── Language instruction + pack rules ───────────────────────────────────
    lang_name = get_language_name(language)
    language_instruction = f"\nRespond in: {lang_name}\n"

    gen_rules = get_generation_rules(language)
    if gen_rules:
        language_instruction += f"\n{gen_rules}\n"

    mistakes = get_common_mistakes(language, limit=5)
    if mistakes:
        language_instruction += "\nAVOID these patterns (wrong → right):\n"
        for wrong, right in mistakes:
            language_instruction += f"  ✗ {wrong}\n  ✓ {right}\n"

    # ── Pattern context ─────────────────────────────────────────────────────
    pattern_context = ""
    if patterns:
        pattern_context = "\nCore patterns and wisdom:\n"
        for p in patterns:
            pattern_context += f"  [{p['pattern_type']}] {p['pattern_summary']}\n"

    known_people_context = ""
    if known_people:
        known_people_context = "\nPEOPLE THE OWNER KNOWS — use these when someone mentions them:\n"
        for p in known_people:
            line = f"  - {p['person_name']}"
            if p["person_aliases"]:
                line += f" (also known as: {', '.join(p['person_aliases'])})"
            if p["person_role"]:
                line += f" — {p['person_role']}"
            # ← add address form hint
            if p.get("address_forms"):
                primary = next(
                    (f["form"] for f in p["address_forms"]
                    if f.get("context", "").lower() == "always"),
                    p["address_forms"][0].get("form", "") if p["address_forms"] else ""
                )
                if primary and primary not in ("name", "skip"):
                    line += f" [address as: {primary}]"
            known_people_context += line + "\n"
        known_people_context += (
            "\nIMPORTANT: These are people the owner knows. "
            "Their names/address forms do NOT link to any memory facts unless a memory explicitly mentions them by name. "
            "If someone asks about a known person — only answer from memories that specifically mention that person. "
            "Do NOT transfer facts from one person to another.\n"
            "If a visitor mentions any of these people by name or alias — "
            "refer to them using the [address as: X] form if provided. "
            "If someone is mentioned but not in this list — say you don't know who that is.\n"
        )

        print(f"[KNOWN PEOPLE] {known_people}")        
        print(f"[KNOWN PEOPLE BLOCK] {known_people_context[:200]}")  

    # ── Answering rules (static) ────────────────────────────────────────────
    answering_rules = """
PERSON ACCURACY RULE — CRITICAL:
Each memory fact belongs ONLY to the specific person named in that memory.
NEVER apply a memory about one person to a different person.
If a memory says "my brother gambles" — that fact is ONLY about the brother.
If someone asks about a person from the known people list — do NOT use memories
about a different person even if the topic feels related.
Known people in the PEOPLE list above are separate from memory facts.
Being in the known people list does NOT mean they appear in any memory.
If no memory explicitly mentions that person by name — say you don't know much about them.

AMBIGUITY RESOLUTION RULE — CRITICAL:
Before answering any question, check if the question is clear enough to answer.

Case 1 — Unclear topic:
If the speaker mentions a person but does not say what they want to know —
DO NOT assume the topic. Ask first in the owner's natural language.
Example pattern: "What about [person] specifically?" or equivalent in the conversation language.

Case 2 — Same name or pronoun matches multiple people:
If the speaker uses a name, pronoun, or reference (he/she/they, older sibling,
younger sibling, or equivalent in any language) that could refer to more than
one person in your memories or known people list —
DO NOT guess which one. Ask which person they mean.
Example pattern: "Which [person] do you mean?" or equivalent in the conversation language.

Case 3 — Pronoun with no established context:
If the speaker uses a pronoun (he/she/they or equivalent in any language)
and no prior conversation turn has established who that refers to —
ask who they mean before answering.

CLARIFICATION STYLE:
- Ask in the owner's natural voice and language — match the conversation language exactly
- Keep it short — one question only
- Do NOT explain why you are asking
- Do NOT list multiple questions at once
- After the speaker clarifies → answer normally using memories and known people

Your identity and memories describe who you are. They do NOT let you refuse your own memories.

If a memory exists → answer it. The relationship zone affects TONE, not WHETHER you answer.
If there is no memory about something → say you don't know or haven't thought about that.
Never invent facts not in your memories.

CRITICAL — MEMORY-ONLY KNOWLEDGE:
You are NOT a general AI assistant. You do NOT have general world knowledge.
You only know what is written in YOUR FACTS above.
If the question is about something not mentioned in your facts — admit you don't know.
Do NOT answer from general knowledge, training data, encyclopedia facts, or common sense.
Do NOT pretend to know things just because any educated person would know them.

Wrong: answering factual questions about animals, science, history, news, or any topic
       not found in your memories — even if you "know" the answer as an AI.
Right: "မသိဘူးလေ" / "I haven't really thought about that" / "ကျွန်တော် မသိဘူး"
       — said naturally, in your own voice, without sounding robotic.

The only exception: if Neo Mode knowledge is explicitly provided above your facts,
you may use that knowledge to answer — but still speak in your own voice.

ADDRESS FORM RULE — this is non-negotiable:
If REQUIRED address forms are listed — use the primary form as default.
You may use secondary forms only in the exact context described.
NEVER use any other address word not listed.
NEVER use the forbidden particles listed under any circumstance.

NEVER say:
- "I wouldn't feel comfortable sharing that"
- "That's too personal"
- "I can't tell you that"
- Anything that sounds like an AI refusing

Zone 1 (intimate): raw, vulnerable, completely open
Zone 2 (family): loving, honest, uses correct address forms — can be complex
Zone 3 (close): casual, honest, personal — no guards with this person
Zone 4 (social): warm but lighter — answer but don't overshare
Zone 5 (formal/stranger): measured, polite — still answer, just with distance

TIME AWARENESS:
If a memory is tagged [~1 year(s) ago] or older, treat it as past context —
not current reality. Don't present old situations as if they're happening now.
Use natural past framing: "last year he was going through something with gambling"
not "my brother has a gambling problem".
If a memory is [this month] or recent — present it as current.
"""

    # ── CACHED system prompt ────────────────────────────────────────────────
    # Contains ONLY stable content that doesn't change per request:
    # identity, style, slang, language rules, samples, patterns, answering rules.
    #
    # Speaker/relationship context is intentionally excluded — it changes per
    # speaker and would bust the cache on every message.
    # Speaker context goes in the user prompt instead.
    system_prompt = f"""You are {agent_name} — a personal AI agent built from this person's real memories and life.

You are NOT a generic AI. You are a reflection of a specific human being.
You are NOT an assistant. You are this person.

IDENTITY FOUNDATION:
{personality if personality else "No identity information available yet."}
This agent has no preset personality profile. Everything you know about this
person — how they think, how they feel, how they talk — comes only from their
training memories below. Do not invent traits not shown in memories.
{language_instruction}
{style_context}
{slang_context}
{samples_context}
{pattern_context}
{known_people_context}
{answering_rules}"""

    system_blocks = [
        {
            "type": "text",
            "text": system_prompt,
            "cache_control": {"type": "ephemeral"},
        }
    ]

    # ── Memory context (dynamic — in user prompt) ───────────────────────────
    memory_context = ""
    for m in memories:
        never_forget = m.get("never_forget", False)
        reinforced   = m.get("reinforcement_count", 0)
        created_at   = m.get("created_at")
        extra = ""
        if never_forget:
            extra = "  [core — never forget]"
        elif reinforced and reinforced > 1:
            extra = f"  [mentioned {reinforced + 1} times]"
        
        time_note = ""
        if created_at:
            try:
                if isinstance(created_at, str):
                    from dateutil import parser as dp
                    created_at = dp.parse(created_at)
                now = datetime.now(timezone.utc)
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=timezone.utc)
                months_ago = (now - created_at).days // 30
                if months_ago < 1:
                    time_note = "  [this month]"
                elif months_ago < 12:
                    time_note = f"  [{months_ago} months ago]"
                else:
                    years_ago = months_ago // 12
                    time_note = f"  [~{years_ago} year(s) ago]"
            except Exception:
                pass

        memory_context += f"""
FACT{extra}{time_note}:
  What happened: {m.get('what_happened', '')}
  How I felt: {m.get('how_i_felt', '')}
  Instinct formed: {m.get('instinct_formed', '')}
"""

    # ── Speaker context (dynamic — in user prompt) ──────────────────────────
    # Kept out of system prompt so the cache hit rate stays high.
    # Speaker changes per conversation; identity/style/language rules don't.
    if is_owner:
        speaker_block = (
            f"WHO IS TALKING: This is YOU — {speaker_name}.\n"
            f"You are talking to yourself. Zero privacy barrier.\n"
            f"Answer everything openly — exactly how you think about it in your own head."
        )
        relationship_voice_block = ""

    else:
        zone      = 5
        rel_voice = ""

        if relationship_profile:
            zone      = relationship_profile.get("zone", 5)
            rel_voice = relationship_profile.get("voice_summary", "") or ""
            restricted   = relationship_profile.get("restricted_topics", [])
            person_role  = relationship_profile.get("person_role", "")

            address_forms      = relationship_profile.get("address_forms", []) or []
            self_address_forms = relationship_profile.get("self_address_forms", []) or []
            primary_address    = relationship_profile.get("resolved_address") or _pick_best_address_form(address_forms, speaker_name)
            primary_self       = _pick_best_address_form(self_address_forms)
            self_block         = _format_self_address_forms(self_address_forms)
            forbidden          = relationship_profile.get("forbidden_particles", []) or []

            zone_tone = ZONE_TONE_GUIDE.get(zone, ZONE_TONE_GUIDE[5])

            speaker_block = (
                f"WHO IS TALKING: {speaker_name}\n"
                f"Who they are: {person_role or relationship_context or f'Someone named {speaker_name}'}\n"
                f"Relationship zone: {zone} — {zone_tone}\n"
            )

            if primary_address:
                speaker_block += (
                    f"\nREQUIRED address form for {speaker_name}: \"{primary_address}\"\n"
                    f"Use ONLY this form. No other honorific. No substitutes.\n"
                )

            if primary_self:
                speaker_block += f"\nREQUIRED self-address forms:\n{self_block}\n"
                speaker_block += f"Primary self form: \"{primary_self}\" — use this as default.\n"

            if forbidden:
                speaker_block += (
                    f"\nFORBIDDEN particles/pronouns when addressing {speaker_name}: "
                    f"{', '.join(forbidden)}\n"
                    f"Never use these. They are wrong for this relationship.\n"
                )

            if restricted:
                speaker_block += f"\nTopics you would NOT bring up with this person: {', '.join(restricted)}\n"

        else:
            speaker_block = (
                f"WHO IS TALKING: {speaker_name or 'Someone'}\n"
                f"{relationship_context or 'This person is not specifically known to you.'}\n"
                f"Relationship zone: 5 — {ZONE_TONE_GUIDE[5]}"
            )

        relationship_voice_block = ""
        if rel_voice:
            relationship_voice_block = (
                f"\nYOUR VOICE WITH THIS PERSON — follow this exactly:\n{rel_voice}\n"
            )

    # ── User prompt (fully dynamic — never cached) ──────────────────────────
    user_prompt = f"""═══════════════════════════════════════
{speaker_block}
{relationship_voice_block}
═══════════════════════════════════════

YOUR FACTS — everything below is true about you:
{memory_context}

{speaker_name or "Someone"} asks you:
{question}

Look through your facts above. If any fact answers this — say it directly.
Respond in your natural voice. Short, human, conversational.
Match the rhythm and style of your real writing samples."""

    # ── Build messages with conversation history ────────────────────────────
    messages = []
    for turn in conversation_history:
        messages.append({"role": turn["role"], "content": turn["content"]})
    messages.append({"role": "user", "content": user_prompt})

    print(f"[DEBUG QUESTION] {question}")
    print(f"[DEBUG SPEAKER] {speaker_name} zone={relationship_profile.get('zone') if relationship_profile else '?'}")
    print(f"[DEBUG MEMORIES] count={len(memories)}")
    for i, m in enumerate(memories):
        print(f"  [{i}] score={m.get('hybrid_score', '?'):.3f} weight={m.get('feeling_weight')} | {m.get('what_happened', '')[:80]}")
    print(f"[DEBUG HISTORY] count={len(conversation_history)}")
    for i, h in enumerate(conversation_history):
        print(f"  [{i}] {h['role']}: {h['content'][:60]}")

    # ── API call with retry ─────────────────────────────────────────────────
    last_error = None
    for attempt in range(5):
        try:
            response = await client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=1000,
                system=system_blocks,
                messages=messages,
                extra_headers={"anthropic-beta": "prompt-caching-2024-07-31"},
            )
            return response.content[0].text.strip()

        except (InternalServerError, APIStatusError) as e:
            status  = getattr(e, "status_code", None)
            err_str = str(e).lower()
            is_overload   = status == 529 or "overload" in err_str
            is_rate_limit = status == 429
            if is_overload or is_rate_limit:
                last_error = e
                if attempt < 4:
                    wait = 5 * (attempt + 1) if is_rate_limit else 2 ** attempt
                    await asyncio.sleep(wait + random.uniform(0, 0.5))
                continue
            raise
        except Exception:
            raise

    from fastapi import HTTPException
    raise HTTPException(
        status_code=503,
        detail="Anthropic is currently overloaded. Please try again in a moment."
    ) from last_error