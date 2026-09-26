"""Sprint 3: Lender profiles, appetite tracking, transaction history, matching."""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lender import Lender, LenderAppetite, LenderTransaction


# ── CRUD ──

async def create_lender(db: AsyncSession, name: str, lender_type: str, **kwargs) -> Lender:
    lender = Lender(name=name, lender_type=lender_type, **kwargs)
    db.add(lender)
    await db.flush()
    await db.refresh(lender)
    return lender


async def list_lenders(db: AsyncSession, search: str | None = None) -> list[Lender]:
    query = select(Lender).order_by(Lender.name)
    if search:
        query = query.where(Lender.name.ilike(f"%{search}%"))
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_lender(db: AsyncSession, lender_id: uuid.UUID) -> Lender | None:
    result = await db.execute(select(Lender).where(Lender.id == lender_id))
    return result.scalar_one_or_none()


async def update_lender(db: AsyncSession, lender_id: uuid.UUID, **kwargs) -> Lender | None:
    lender = await get_lender(db, lender_id)
    if not lender:
        return None
    for k, v in kwargs.items():
        if hasattr(lender, k):
            setattr(lender, k, v)
    await db.flush()
    await db.refresh(lender)
    return lender


# ── Appetite ──

async def log_appetite(
    db: AsyncSession,
    lender_id: uuid.UUID,
    appetite_signal: str,
    recorded_by: uuid.UUID | None = None,
    **kwargs,
) -> LenderAppetite:
    now = datetime.now(timezone.utc)
    appetite = LenderAppetite(
        lender_id=lender_id,
        appetite_signal=appetite_signal,
        recorded_by=recorded_by,
        recorded_at=now,
        expires_at=now + timedelta(days=90),
        **kwargs,
    )
    db.add(appetite)
    await db.flush()
    await db.refresh(appetite)
    return appetite


async def get_appetite_history(db: AsyncSession, lender_id: uuid.UUID) -> list[LenderAppetite]:
    result = await db.execute(
        select(LenderAppetite)
        .where(LenderAppetite.lender_id == lender_id)
        .order_by(LenderAppetite.recorded_at.desc())
    )
    return list(result.scalars().all())


async def get_latest_appetite(db: AsyncSession, lender_id: uuid.UUID) -> LenderAppetite | None:
    result = await db.execute(
        select(LenderAppetite)
        .where(LenderAppetite.lender_id == lender_id)
        .order_by(LenderAppetite.recorded_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


# ── Transactions ──

async def log_transaction(db: AsyncSession, lender_id: uuid.UUID, **kwargs) -> LenderTransaction:
    txn = LenderTransaction(lender_id=lender_id, **kwargs)
    db.add(txn)
    await db.flush()
    await db.refresh(txn)
    return txn


async def get_transactions(db: AsyncSession, lender_id: uuid.UUID) -> list[LenderTransaction]:
    result = await db.execute(
        select(LenderTransaction)
        .where(LenderTransaction.lender_id == lender_id)
        .order_by(LenderTransaction.recorded_at.desc())
    )
    return list(result.scalars().all())


# ── Matching ──

async def match_lenders_for_deal(
    db: AsyncSession,
    property_type: str | None = None,
    geography: str | None = None,
    deal_size: float | None = None,
    ltc_requested: float | None = None,
) -> list[dict]:
    """Score and rank lenders by fit. Deterministic — no LLM."""
    now = datetime.now(timezone.utc)

    # Get all lenders with their latest appetite
    lenders_result = await db.execute(select(Lender).order_by(Lender.name))
    all_lenders = lenders_result.scalars().all()

    scored = []
    for lender in all_lenders:
        appetite = await get_latest_appetite(db, lender.id)
        if not appetite or appetite.appetite_signal == "paused":
            continue

        score = 50.0  # Base score

        # Property type match
        if property_type and appetite.property_types:
            if property_type in appetite.property_types:
                score += 20
            else:
                score -= 10

        # Geography match
        if geography and appetite.geographies:
            if geography.lower() in [g.lower() for g in appetite.geographies]:
                score += 15

        # Deal size within range
        if deal_size and appetite.deal_size_min and appetite.deal_size_max:
            if appetite.deal_size_min <= deal_size <= appetite.deal_size_max:
                score += 15
            else:
                score -= 20

        # LTC headroom
        if ltc_requested and appetite.ltc_max:
            if ltc_requested <= appetite.ltc_max:
                score += 10
            else:
                score -= 15

        # Appetite signal bonus
        signal_bonus = {"hungry": 15, "active": 5, "selective": -5}
        score += signal_bonus.get(appetite.appetite_signal, 0)

        # Freshness bonus/penalty
        if appetite.recorded_at:
            age_days = (now - appetite.recorded_at).days
            if age_days < 30:
                score += 10
            elif age_days > 60:
                score -= 10

        # Transaction history bonus
        txn_result = await db.execute(
            select(func.count(LenderTransaction.id))
            .where(LenderTransaction.lender_id == lender.id, LenderTransaction.outcome == "won")
        )
        won_count = txn_result.scalar() or 0
        score += min(won_count * 3, 15)

        # Pass history penalty
        pass_result = await db.execute(
            select(func.count(LenderTransaction.id))
            .where(LenderTransaction.lender_id == lender.id, LenderTransaction.outcome == "passed")
        )
        pass_count = pass_result.scalar() or 0
        score -= min(pass_count * 2, 10)

        scored.append({
            "lender_id": str(lender.id),
            "lender_name": lender.name,
            "lender_type": lender.lender_type,
            "fit_score": round(max(0, min(100, score)), 1),
            "appetite_signal": appetite.appetite_signal,
            "rate_indication": appetite.rate_indication,
            "ltc_max": appetite.ltc_max,
            "notes": lender.notes,
        })

    scored.sort(key=lambda x: x["fit_score"], reverse=True)
    return scored[:25]
