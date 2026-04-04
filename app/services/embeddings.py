import asyncio
import random
from openai import AsyncOpenAI
from app.core.config import settings

client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

# Languages where raw text can be embedded directly without translation.
# These have strong representation in text-embedding-3-small training data.
# All others are translated to English first for consistent vector space.
DIRECTLY_EMBEDDABLE = {"en", "fr", "es", "de", "it", "pt", "nl", "pl", "sv", "da"}


async def generate_embedding(text: str) -> list[float]:
    """
    Embed text directly. Use for storing memories (always stored as English
    after extraction) and for English queries.
    """
    response = await client.embeddings.create(
        model="text-embedding-3-small",
        input=text[:8000],
    )
    return response.data[0].embedding


async def generate_embedding_for_query(
    text: str,
    language: str = "en",
) -> list[float]:
    """
    Embed a query for semantic search against memory vectors.

    Memories are stored as English embeddings (extracted/translated at save time).
    Queries in non-English languages must be translated to English first,
    otherwise the vectors live in different spaces and similarity scores are wrong.

    For directly embeddable languages (English + major European languages),
    embed directly — their vector spaces are close enough to English.

    For Burmese, Thai, Chinese, Korean, Japanese, Arabic, Indonesian etc.
    — translate to English first, then embed.
    """
    if not text or not text.strip():
        return await generate_embedding("empty")

    # Directly embeddable — skip translation
    if language in DIRECTLY_EMBEDDABLE:
        return await generate_embedding(text)

    # Translate to English first
    english_text = await _translate_to_english(text, language)
    return await generate_embedding(english_text)


async def _translate_to_english(text: str, language: str) -> str:
    """
    Translate text to English using Claude Haiku.
    Used only for query embedding — not for storing content.
    Fast and cheap (Haiku, max 200 tokens).
    """
    from anthropic import AsyncAnthropic, InternalServerError, APIStatusError
    ac = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

    prompt = (
        f"Translate the following text to English. "
        f"Return ONLY the translation, nothing else. "
        f"If it is already English or mostly English, return it as-is.\n\n"
        f"{text[:1000]}"
    )

    last_error = None
    for attempt in range(3):
        try:
            resp = await ac.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}],
            )
            translated = resp.content[0].text.strip()
            return translated if translated else text
        except (InternalServerError, APIStatusError) as e:
            status = getattr(e, "status_code", None)
            if status in (429, 529) or "overload" in str(e).lower():
                last_error = e
                await asyncio.sleep((2 ** attempt) + random.uniform(0, 0.3))
                continue
            raise
        except Exception:
            # On any unexpected error, fall back to raw text
            return text

    # All retries failed — fall back to raw text rather than blocking the query
    return text