"""
app/api/routes/billing.py

Souls billing routes — owner authenticated.

Endpoints:
  GET  /billing/balance          → current souls balance + plan
  GET  /billing/history          → transaction history
  POST /billing/upgrade          → upgrade tester → paid (call after payment)
  POST /billing/refill           → add 1,000 Soul refill pack (call after payment)

Note on payments:
  Payment processing (Stripe etc.) is Phase 2.
  For now, /upgrade and /refill are called manually or via webhook.
  They are admin-style endpoints — protect them with a webhook secret
  before exposing to the internet.
"""

from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import Optional

from app.db.session import get_db
from app.models.user import User, SoulsTransaction
from app.core.security import get_current_user
from app.services.souls import (
    check_balance,
    get_plan,
    get_transaction_history,
    upgrade_to_paid,
    add_refill_pack,
    TESTER_GRANT,
    PAID_GRANT,
    REFILL_SOULS,
    REFILL_PRICE_USD,
    COST_TRAINING_SUBMIT,
    COST_CHAT_EN,
    COST_CHAT_INTL,
)

router = APIRouter()

_REASON_TO_TYPE = {
    "training_submit":      "training",
    "chat_message":         "testing_chat",
    "public_chat_message":  "public_chat",
}

# ── GET /billing/balance ──────────────────────────────────────────────────

@router.get("/balance")
async def get_balance(
    current_user: User         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    """
    Returns current souls balance and plan info.
    Frontend uses this to display the Souls counter in the sidebar.
    """
    balance = await check_balance(str(current_user.id), db)
    plan    = await get_plan(str(current_user.id), db)

    # Compute percentage for UI progress bar
    cap = TESTER_GRANT if plan == "tester" else None   # paid has no cap
    pct = round((balance / cap) * 100, 1) if cap else None

    return {
        "plan":              plan,
        "souls_balance":     balance,
        "tester_cap":        cap,
        "balance_pct":       pct,
        "can_refill":        plan == "paid",
        "can_train":         balance >= COST_TRAINING_SUBMIT,
        "can_chat":          balance >= COST_CHAT_EN,
        "cost_training":     COST_TRAINING_SUBMIT,
        "cost_chat_en":      COST_CHAT_EN,
        "cost_chat_intl":    COST_CHAT_INTL,
        "refill_souls":      REFILL_SOULS,
        "refill_price_usd":  REFILL_PRICE_USD,
    }


# ── GET /billing/history ──────────────────────────────────────────────────

@router.get("/history")
async def get_history(
    current_user: User         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    """Transaction history — last 20 entries."""
    history = await get_transaction_history(str(current_user.id), db)
    return {"transactions": history}


# ── POST /billing/upgrade ─────────────────────────────────────────────────

@router.post("/upgrade")
async def upgrade_plan(
    current_user: User         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    """
    Upgrade from tester → paid plan.
    Grants 1000 Souls (the $4 credit included in $14.99 entry fee).

    Phase 1: call this manually after confirming $14.99 payment.
    Phase 2: call this from Stripe webhook after charge.success.

    Idempotent: if already paid, returns current state without re-granting.
    """
    plan = await get_plan(str(current_user.id), db)

    if plan == "paid":
        balance = await check_balance(str(current_user.id), db)
        return {
            "message":  "Already on paid plan.",
            "plan":     "paid",
            "balance":  balance,
            "granted":  0,
        }

    result = await upgrade_to_paid(str(current_user.id), db)

    return {
        "message": "Upgraded to paid plan. 1,000 Souls credited.",
        **result,
    }


# ── POST /billing/refill ──────────────────────────────────────────────────

@router.post("/refill")
async def purchase_refill(
    current_user: User         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    """
    Purchase a refill pack — 1,000 Souls for $3.99.
    Only available on paid plan.

    Phase 1: call this manually after confirming $3.99 payment.
    Phase 2: call this from Stripe webhook.
    """
    result = await add_refill_pack(str(current_user.id), db)

    return {
        "message":  f"1,000 Souls added.",
        "balance":  result["balance"],
        "credited": result["credited"],
    }

@router.get("/spent-history")
async def get_spent_history(
    current_user: User         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    """
    Returns last 50 spending records for the owner.
    Only includes deduction transactions (amount < 0).
    Filters to the 3 tracked action types only.
    """
    result = await db.execute(
        select(SoulsTransaction)
        .where(
            SoulsTransaction.user_id == current_user.id,
            SoulsTransaction.amount  < 0,
            SoulsTransaction.reason.in_(list(_REASON_TO_TYPE.keys())),
        )
        .order_by(desc(SoulsTransaction.created_at))
        .limit(50)
    )
    txns = result.scalars().all()
 
    records = []
    for t in txns:
        action_type = _REASON_TO_TYPE[t.reason]
        speaker = None
        if action_type == "public_chat" and t.meta:
            speaker = t.meta.get("speaker_name")
 
        records.append({
            "date":        t.created_at.isoformat() if t.created_at else None,
            "type":        action_type,
            "souls_spent": abs(t.amount),
            "speaker":     speaker,
        })
 
    return {"records": records}