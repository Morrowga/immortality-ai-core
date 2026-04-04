"""
Language Pack — Burmese (မြန်မာဘာသာ)
Language code: my

Maintained by native Burmese speakers.
Rules are injected into the agent response pipeline (Layers 1, 2, 3).
NOT used during training — training input is the trainer's own voice.

How to contribute:
- Add rules to GENERATION_RULES that Claude consistently gets wrong
- Add to COMMON_MISTAKES as (wrong_example, right_example) pairs
- Keep rules short and specific — vague rules don't help Claude
"""

LANGUAGE_NAME = "Burmese (Myanmar script — မြန်မာဘာသာ). NOT Chinese. NOT Japanese. Myanmar Unicode only."

# ── Layer 1: Generation rules ──────────────────────────────────────────────
# Injected into agent.py system prompt.
# These are the rules Claude needs during initial response generation.

GENERATION_RULES = """
BURMESE LANGUAGE RULES — follow exactly, non-negotiable:

Script:
- Use Myanmar Unicode script only (မြန်မာ)
- NEVER use Chinese, Japanese, or any other CJK characters
- English loanwords are fine — write them in English as Burmese speakers do

Word order:
- Burmese is SOV (Subject → Object → Verb) — verb always comes LAST
- Time expressions come BEFORE the main clause, not after
- Adjectives come BEFORE the noun they modify

Sentence length — most important rule:
- Keep each sentence under 15 words
- If a thought needs more than 15 words — split into 2 sentences
- Do NOT chain multiple clauses with ပြီး repeatedly
- Short punchy sentences sound natural. Long compound sentences sound translated.

Particles and endings:
- Statement: တယ် (casual) / ပါတယ် (polite)
- Question: လား (casual) / ပါသလား (polite)
- Negative: မ + verb + ဘူး
- Do NOT mix casual and polite particles in the same response
- Match particle register to the relationship zone — casual for Zone 1-3, polite for Zone 4-5
- Casual trailing particle ကွာ — use at the end of resigned or self-aware statements
  e.g. "သင်တော့ သင်မယ် ကွာ" not "သင်တော့ သင်မယ်"

Word choice:
- ဆိုကြောင်း — only use after quoting what someone SAID, not after stating a fact
  For "still haven't done X yet" use အခုထိ not ဆိုကြောင်း
- Time words: ဘယ်ချိန် for "when" in casual speech, not ဘယ်တုန်း

Pronouns — use what the address_forms specify:
- ငါ — casual self, Zone 1-2 only
- ကျွန်တော် — male formal self
- ကျမ — female formal self
- Never use ငါ in Zone 4-5 (formal/stranger)
"""

# ── Layer 2: Naturalization rules ─────────────────────────────────────────
# Injected into survey.py → naturalize_response().
# These guide rhythm and style matching after Layer 1 draft.

NATURALIZE_RULES = """
Burmese naturalization rules:

Rhythm:
- Burmese texting and casual speech uses short bursts — match this
- If the draft has a sentence over 12 words, break it
- Fragments are natural in casual Burmese — don't force complete sentences

Code-mixing (Burmese + English):
- Burmese speakers naturally mix English words — this is correct, not wrong
- English words like "okay", "lol", "actually", "honestly" are natural
- Do NOT translate English loanwords back to Burmese if the samples use English

Tone:
- Casual zone (1-3): drop ပါ/ခင်ဗျာ particles, use တယ်/ဘူး freely
- Formal zone (4-5): keep ပါတယ်/ပါဘူး, avoid ငါ
"""

# ── Layer 3: Pronoun correction rules ─────────────────────────────────────
# Injected into chat.py → _correct_pronouns().
# These are the final hard rules enforced after naturalization.

PRONOUN_RULES = """
Burmese pronoun correction rules:

Address forms:
- Particles attach directly to the title/name — no space
  WRONG: မေ မေ   RIGHT: မေမေ
  WRONG: ဦး လေး  RIGHT: ဦးလေး

Self-address register:
- ငါ and ကျွန်တော်/ကျမ must NEVER appear in the same response
- Pick one register and stay consistent throughout

Forbidden particles:
- If နင် or မင်း is in forbidden_particles — remove every instance, no exceptions
- Replace with the correct address form from address_forms

Output rules:
- Output ONLY the corrected Burmese message
- Do NOT explain what you changed
- Do NOT write "Wait" or any self-correction narration
- Do NOT add notes in parentheses or brackets
"""

# ── Common mistakes ────────────────────────────────────────────────────────
# Pairs of (wrong, right) — used as negative examples in Layer 1 prompt.
# Add more as you find them during testing.

COMMON_MISTAKES = [
    (
        "သူမသည် ဈေးသွားပြီး အစားအစာများကို ဝယ်သည်",
        "သူမ ဈေးသွားပြီး စားစရာတွေ ဝယ်လာတယ်",
    ),
    (
        "ကျွန်တော် သွားမည်ဖြစ်သည်",
        "ကျွန်တော် သွားမယ်",
    ),
    (
        "ထိုသို့ဖြစ်သောကြောင့် ကျွန်တော်သည် မသွားနိုင်ခဲ့ပါ",
        "ဒါကြောင့် မသွားနိုင်ခဲ့ဘူး",
    ),
    (
        "သင်သည် မည်သို့နေသနည်း",
        "နေကောင်းလား",
    ),
     # ဆိုကြောင်း used wrongly as a connector after stating a fact
    (
        "အသက် ၂၈ ရောက်နေပြီ ဆိုကြောင်း",
        "အသက် ၂၈ ရောက်နေပြီ အခုထိ",
    ),
    # တုန်း for time when ချိန် or ချိန်လဲ is more natural
    (
        "ဘယ်တုန်းတော့မသိဘူး",
        "ဘယ်ချိန်လဲတော့မသိဘူး",
    ),
    # trailing ကွာ missing in casual self-deprecating statements
    (
        "သင်တော့ သင်မယ်",
        "သင်တော့ သင်မယ် ကွာ",
    ),
    (
        "အမရောပါ",
        "အမရော",
    ),
    (
        "ဘာကိစ္စရှိလဲ ပါ",
        "ဘာကိစ္စရှိလို့လဲ",
    ),
    (
        "အင်း နာမည်တူတာ အံ့သြဘူးလားနော်",
        "အင်း နာမည်တူတာ အံ့သြစရာမှမဟုတ်တာ"
    )
]

# ── Sentence length guide ──────────────────────────────────────────────────
MAX_SENTENCE_WORDS = 15