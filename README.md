# Immortality

A personal AI agent platform where each user builds one agent trained on their own memories, stories, emotions, and life experiences. The agent learns to respond as that specific person — not as a generic assistant.

Instead of chatting with an AI that knows nothing about you, people in your life can chat with an agent built entirely from your actual memories — one that knows how you think, feel, and communicate.

> **Core principle:** The agent only knows what is in its training memories. It does not answer from general AI knowledge. If a memory does not exist for a topic, the agent admits it does not know. This is intentional and enforced at the prompt level.

---

## Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI + PostgreSQL + pgvector |
| Frontend | Next.js 14 + Zustand + TanStack Query |
| AI Models | Claude Sonnet 4.6 + Haiku 4.5 + OpenAI text-embedding-3-small |
| Auth | JWT + bcrypt |
| Migrations | Alembic |

---

## How It Works

**Training** — the owner shares memories through a conversational interface. Each memory is extracted by Haiku, embedded via OpenAI, and stored as a vector in PostgreSQL. A Wisdom Score (0–100) reflects how much the agent has learned.

**Chat pipeline (3 layers):**
1. **Layer 1 — Claude Sonnet** generates a response grounded in retrieved memories
2. **Layer 2 — Haiku** naturalizes the response to match the owner's real voice
3. **Layer 3 — Haiku** corrects pronouns and honorifics for the specific relationship

**Public chat** — the owner shares a passphrase-protected link. Visitors chat with the agent; all Soul costs are deducted from the owner's balance.

**Neo Mode** — optional knowledge packages (system or custom) that extend the agent beyond personal memories into specific domains like gaming, finance, or fitness.

---

## Billing — Souls

API costs are measured in Souls, deducted after each call based on actual token usage.

| Plan | Details |
|---|---|
| Tester | Free · 600 Souls on signup |
| Paid | $14.99 one-time · 1,000 Souls included |
| Refill | $4 per 1,000 Souls (paid plan only) |

1 Soul = 100 tokens (always rounded up). A typical chat message costs 15–50 Souls depending on language and layers active.

---

## Key Concepts

- **Owner** — the person who creates and trains the agent
- **Agent** — the AI representation built from the owner's memories
- **Memory** — an extracted emotional experience stored as a vector embedding
- **Wisdom Score** — numeric measure of how much the agent has learned
- **Neo Mode** — installable knowledge packages that extend the agent's expertise
- **Souls** — the credit currency used to pay for AI calls

---

## Environment Variables

```env
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/immortality
DATABASE_URL_SYNC=postgresql://user:pass@localhost:5432/immortality
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
SECRET_KEY=your-secret-key-here
ALLOWED_ORIGINS=["http://localhost:3000"]
ACCESS_TOKEN_EXPIRE_MINUTES=10080
VOICE_ENABLED=false
```
