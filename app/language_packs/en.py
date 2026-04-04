"""
Language Pack — English
Language code: en

This is the baseline pack and template for contributors adding new languages.
English rules are minimal — Claude generates English well by default.
This file exists mainly as a reference template.

How to create a new language pack:
1. Copy this file and rename it to the language code (e.g. ja.py, ko.py, th.py)
2. Fill in LANGUAGE_NAME with the correct script description
3. Fill in GENERATION_RULES with grammar rules Claude gets wrong in that language
4. Fill in NATURALIZE_RULES with rhythm/style notes for that language
5. Fill in PRONOUN_RULES with honorific/pronoun correction rules
6. Add COMMON_MISTAKES pairs — (wrong_output, correct_output)
7. Set MAX_SENTENCE_WORDS appropriate for that language's natural rhythm
8. Submit a PR — native speaker review recommended before merging
"""

LANGUAGE_NAME = "English"

# English generation is strong by default — minimal rules needed
GENERATION_RULES = """
English language rules:
- Write naturally and conversationally
- Match the tone of the relationship zone (casual vs formal)
- Contractions are fine in casual zones (don't, I'm, it's)
- Avoid overly formal or robotic phrasing
"""

NATURALIZE_RULES = """
English naturalization:
- Match the rhythm of the real writing samples
- Keep sentence length consistent with samples
- Fragments and informal punctuation are fine if samples use them
"""

PRONOUN_RULES = """
English pronoun rules:
- Use "you" as the default address form
- No honorific system — address forms from profile take priority if set
"""

COMMON_MISTAKES = []

MAX_SENTENCE_WORDS = 25