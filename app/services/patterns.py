import json
import uuid
from sqlalchemy import text as sa_text
from anthropic import AsyncAnthropic
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from app.core.config import settings
from app.models.user import Memory, PatternAbstraction, AgentProfile, AgentLifecycle
from app.services.embeddings import generate_embedding

client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)


async def should_run_abstraction(agent_id: str, db: AsyncSession) -> bool:
    result = await db.execute(
        select(AgentLifecycle).where(AgentLifecycle.agent_id == agent_id)
    )
    lifecycle = result.scalar_one_or_none()
    if not lifecycle:
        return False
    count = lifecycle.training_session_count or 0
    return count > 0 and count % 10 == 0


async def run_pattern_abstraction(agent_id: str, db: AsyncSession) -> dict | None:
    """
    Extract behavioral patterns from memories.

    Includes BOTH:
    - High-weight memories (feeling_weight >= 5) — significant experiences
    - High-reinforcement low-weight memories (mentioned 3+ times even if low weight)
      These capture quiet recurring behaviors that define a person just as much
      as the dramatic moments do.
    """
    # High-weight memories
    result_high = await db.execute(
        select(Memory)
        .where(
            Memory.agent_id == agent_id,
            Memory.is_active == True,
            Memory.feeling_weight >= 5.0,
        )
        .order_by(Memory.feeling_weight.desc(), Memory.created_at.desc())
        .limit(8)
    )
    high_weight = result_high.scalars().all()

    # High-reinforcement memories (recurring even if low weight)
    result_reinf = await db.execute(
        select(Memory)
        .where(
            Memory.agent_id == agent_id,
            Memory.is_active == True,
            Memory.reinforcement_count >= 2,
            Memory.feeling_weight < 5.0,  # not already captured above
        )
        .order_by(Memory.reinforcement_count.desc())
        .limit(4)
    )
    high_reinf = result_reinf.scalars().all()

    memories = list(high_weight) + list(high_reinf)
    if len(memories) < 3:
        return None

    memory_summaries = []
    memory_ids = []
    for m in memories:
        memory_ids.append(str(m.id))
        memory_summaries.append({
            "what_happened": m.what_happened,
            "how_i_felt": m.how_i_felt,
            "what_i_learned": m.what_i_learned,
            "instinct_formed": m.instinct_formed,
            "feeling_weight": m.feeling_weight,
            "reinforcement_count": m.reinforcement_count,
            "section": m.section,
            "pattern_tags": m.pattern_tags,
        })

    prompt = f"""You are analyzing a person's most significant memories to extract behavioral patterns.
These patterns represent WHO this person is — their instincts, values, and automatic reactions.

Look across ALL memories below. Find the patterns that repeat across multiple memories.
Focus on: what situations trigger the same feeling, what behaviors keep appearing,
what values keep showing up, what this person instinctively does.

Memories (mix of high-impact and recurring low-impact):
{json.dumps(memory_summaries, ensure_ascii=False, indent=2)}

Extract 2-4 patterns. Return ONLY valid JSON as a list:

[
  {{
    "pattern_summary": "English description of the pattern",
    "pattern_summary_original": "Same in the person's natural language/voice",
    "pattern_type": "value OR instinct OR belief OR reaction",
    "abstraction_weight": 7.5,
    "trigger": "what situation activates this pattern",
    "expression": "how this pattern shows in their behavior"
  }}
]

Rules:
- pattern_type: value=what they care about, instinct=automatic behavior,
  belief=how they see the world, reaction=how they respond to situations
- abstraction_weight = weighted average of source memories
- Be SPECIFIC to this person — not generic wisdom
- Conversational, not philosophical
- Only extract patterns that appear in at least 2 memories"""

    response = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}]
    )

    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    patterns = json.loads(raw)
    saved_patterns = []

    for p in patterns:
        # Generate embedding for semantic retrieval
        try:
            embedding = await generate_embedding(p["pattern_summary"])
        except Exception:
            embedding = None

        pattern = PatternAbstraction(
            agent_id=uuid.UUID(agent_id),
            pattern_summary=p["pattern_summary"],
            pattern_summary_original=p.get("pattern_summary_original"),
            source_memory_ids=[uuid.UUID(mid) for mid in memory_ids],
            pattern_type=p["pattern_type"],
            abstraction_weight=p.get("abstraction_weight", 7.0),
        )
        db.add(pattern)
        await db.flush()

        if embedding:
            embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"
            await db.execute(
                sa_text("UPDATE pattern_abstractions SET embedding = :e WHERE id = :id"),
                {"e": embedding_str, "id": str(pattern.id)},
            )

        saved_patterns.append(p)

    # Update wisdom score
    result = await db.execute(
        select(func.avg(PatternAbstraction.abstraction_weight)).where(
            PatternAbstraction.agent_id == uuid.UUID(agent_id)
        )
    )
    avg_wisdom = result.scalar() or 0.0

    result = await db.execute(
        select(AgentProfile).where(AgentProfile.id == uuid.UUID(agent_id))
    )
    agent = result.scalar_one_or_none()
    if agent:
        agent.wisdom_score = round(float(avg_wisdom), 2)

    await db.commit()
    return {"patterns_extracted": len(saved_patterns), "patterns": saved_patterns}