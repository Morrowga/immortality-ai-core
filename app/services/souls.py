"""
app/services/souls.py

Souls billing engine.

All souls operations go through this module.
Never update souls_balance directly — always use deduct() or credit().

Souls → Token conversion:
  1 Soul = 100 tokens  (ceil — always round up)
  1,000 Souls = $5 = 100,000 tokens

Cost is now DYNAMIC — callers measure actual token usage from the Anthropic
response object and call tokens_to_souls() to convert before calling deduct().

Fixed constants (COST_*) are kept only for pre-flight balance checks
and the can_chat / can_train fields in the billing API — they represent
a rough minimum cost so the UI can show a sensible disabled state.

Plans:
  tester  — 600 Souls on signup, no refill, agent stops at 0
  paid    — 500 Souls on activation, can buy refill packs
"""

import math
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from fastapi import HTTPException
import uuid
from datetime import datetime

from app.models.user import User, SoulsTransaction

# ── Conversion ────────────────────────────────────────────────────────────

TOKENS_PER_SOUL = 100   # 1 Soul = 100 tokens


def tokens_to_souls(total_tokens: int) -> int:
    """
    Convert raw token count to Souls. Always rounds UP.
    1 token → 1 Soul (minimum).
    100 tokens → 1 Soul.
    101 tokens → 2 Souls.
    """
    return max(1, math.ceil(total_tokens / TOKENS_PER_SOUL))


# ── Approximate fixed costs — used ONLY for pre-flight UI checks ──────────
# These are rough lower-bound estimates. Actual deduction uses real token counts.

COST_TRAINING_SUBMIT   = 20   # safe lower bound: ~2,000 tokens typical minimum
COST_CHAT_EN           = 30   # safe lower bound: ~3,000 tokens typical minimum
COST_CHAT_INTL         = 35   # safe lower bound: ~3,500 tokens typical minimum

# Languages that use the higher cost (L3 honorific correction active)
INTL_LANGUAGES = {"my", "th", "ko", "ja", "id"}

# Plan grants
TESTER_GRANT = 600
PAID_GRANT   = 1000

# Refill pack
REFILL_SOULS     = 1_000
REFILL_PRICE_USD = 3.99


async def check_balance(user_id: str, db: AsyncSession) -> int:
    """Return current souls_balance for a user."""
    result = await db.execute(
        select(User.souls_balance).where(User.id == uuid.UUID(user_id))
    )
    balance = result.scalar_one_or_none()
    return balance or 0


async def get_plan(user_id: str, db: AsyncSession) -> str:
    """Return user's current plan: 'tester' | 'paid'."""
    result = await db.execute(
        select(User.plan).where(User.id == uuid.UUID(user_id))
    )
    return result.scalar_one_or_none() or "tester"


async def deduct(
    user_id: str,
    cost: int,
    reason: str,
    db: AsyncSession,
    meta: dict = None,
    raise_on_empty: bool = True,
) -> dict:
    """
    Deduct souls from a user's balance atomically.

    cost is in Souls (already converted via tokens_to_souls).

    Returns:
      {"success": True,  "balance": 412, "deducted": 29}
      {"success": False, "balance": 0,   "deducted": 0,  "reason": "insufficient_souls"}

    If raise_on_empty=True (default) → raises HTTP 402 when balance is 0.
    If raise_on_empty=False          → returns success=False silently (background tasks).
    """
    uid = uuid.UUID(user_id)

    # Atomic: fetch + check + deduct in one UPDATE with RETURNING
    result = await db.execute(
        update(User)
        .where(
            User.id == uid,
            User.souls_balance >= cost,
        )
        .values(souls_balance=User.souls_balance - cost)
        .returning(User.souls_balance, User.plan)
    )
    row = result.one_or_none()

    if row is None:
        balance = await check_balance(user_id, db)

        if raise_on_empty:
            plan = await get_plan(user_id, db)
            if plan == "tester":
                raise HTTPException(
                    status_code=402,
                    detail={
                        "code":    "souls_depleted_tester",
                        "message": "Your free Souls have been used. Upgrade to continue.",
                        "balance": balance,
                    }
                )
            else:
                raise HTTPException(
                    status_code=402,
                    detail={
                        "code":    "souls_depleted",
                        "message": "You're out of Souls. Purchase a refill pack to continue.",
                        "balance": balance,
                    }
                )

        return {"success": False, "balance": balance, "deducted": 0, "reason": "insufficient_souls"}

    new_balance = row[0]

    # Log transaction
    txn = SoulsTransaction(
        user_id       = uid,
        amount        = -cost,
        reason        = reason,
        balance_after = new_balance,
        meta          = meta,
    )
    db.add(txn)
    await db.flush()

    return {"success": True, "balance": new_balance, "deducted": cost}


async def credit(
    user_id: str,
    amount: int,
    reason: str,
    db: AsyncSession,
    meta: dict = None,
) -> dict:
    """
    Credit souls to a user's balance.
    Used for: signup grant, paid activation, refill pack purchase.
    """
    uid = uuid.UUID(user_id)

    result = await db.execute(
        update(User)
        .where(User.id == uid)
        .values(souls_balance=User.souls_balance + amount)
        .returning(User.souls_balance)
    )
    row = result.one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="User not found")

    new_balance = row[0]

    txn = SoulsTransaction(
        user_id       = uid,
        amount        = amount,
        reason        = reason,
        balance_after = new_balance,
        meta          = meta,
    )
    db.add(txn)
    await db.flush()

    return {"balance": new_balance, "credited": amount}


async def upgrade_to_paid(user_id: str, db: AsyncSession) -> dict:
    """Upgrade user from tester to paid plan. Grants PAID_GRANT souls."""
    uid = uuid.UUID(user_id)

    await db.execute(
        update(User)
        .where(User.id == uid)
        .values(plan="paid")
    )

    result = await credit(
        user_id=user_id,
        amount=PAID_GRANT,
        reason="signup_paid",
        db=db,
        meta={"note": "Paid plan activation — 1,000 souls included"},
    )

    await db.commit()

    return {
        "plan":    "paid",
        "balance": result["balance"],
        "granted": PAID_GRANT,
    }


async def add_refill_pack(user_id: str, db: AsyncSession) -> dict:
    """Add one refill pack (1,000 Souls) to a paid user."""
    plan = await get_plan(user_id, db)
    if plan != "paid":
        raise HTTPException(
            status_code=403,
            detail="Refill packs are only available on the paid plan."
        )

    result = await credit(
        user_id=user_id,
        amount=REFILL_SOULS,
        reason="refill_pack",
        db=db,
        meta={"price_usd": REFILL_PRICE_USD},
    )

    await db.commit()

    return {
        "balance":  result["balance"],
        "credited": REFILL_SOULS,
    }


async def get_transaction_history(
    user_id: str,
    db: AsyncSession,
    limit: int = 20,
) -> list[dict]:
    """Return recent transactions for a user."""
    from sqlalchemy import desc

    result = await db.execute(
        select(SoulsTransaction)
        .where(SoulsTransaction.user_id == uuid.UUID(user_id))
        .order_by(desc(SoulsTransaction.created_at))
        .limit(limit)
    )
    txns = result.scalars().all()

    return [
        {
            "id":            str(t.id),
            "amount":        t.amount,
            "reason":        t.reason,
            "balance_after": t.balance_after,
            "meta":          t.meta,
            "created_at":    t.created_at.isoformat() if t.created_at else None,
        }
        for t in txns
    ]