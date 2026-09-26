"""Sprint 3: Deal outcome capture — distributions, responses, closings."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.deal_outcome import DealClosing, DealDistribution, LenderResponse


async def distribute_to_lender(
    db: AsyncSession,
    deal_id: uuid.UUID,
    lender_id: uuid.UUID,
    distributed_by: uuid.UUID | None = None,
    approach_angle: str | None = None,
) -> DealDistribution:
    dist = DealDistribution(
        deal_id=deal_id,
        lender_id=lender_id,
        distributed_by=distributed_by,
        approach_angle=approach_angle,
    )
    db.add(dist)
    await db.flush()
    await db.refresh(dist)
    return dist


async def get_distributions(db: AsyncSession, deal_id: uuid.UUID) -> list[DealDistribution]:
    result = await db.execute(
        select(DealDistribution)
        .where(DealDistribution.deal_id == deal_id)
        .order_by(DealDistribution.distributed_at.desc())
    )
    return list(result.scalars().all())


async def record_response(
    db: AsyncSession,
    deal_distribution_id: uuid.UUID,
    response_type: str,
    terms_offered: dict | None = None,
    pass_reason: str | None = None,
    notes: str | None = None,
) -> LenderResponse:
    resp = LenderResponse(
        deal_distribution_id=deal_distribution_id,
        response_type=response_type,
        terms_offered=terms_offered,
        pass_reason=pass_reason,
        notes=notes,
    )
    db.add(resp)
    await db.flush()
    await db.refresh(resp)
    return resp


async def get_responses(db: AsyncSession, deal_id: uuid.UUID) -> list[dict]:
    result = await db.execute(
        select(DealDistribution, LenderResponse)
        .outerjoin(LenderResponse, LenderResponse.deal_distribution_id == DealDistribution.id)
        .where(DealDistribution.deal_id == deal_id)
        .order_by(DealDistribution.distributed_at.desc())
    )
    rows = result.all()
    return [
        {
            "distribution_id": str(dist.id),
            "lender_id": str(dist.lender_id),
            "distributed_at": dist.distributed_at.isoformat() if dist.distributed_at else None,
            "approach_angle": dist.approach_angle,
            "response": {
                "id": str(resp.id),
                "response_type": resp.response_type,
                "response_at": resp.response_at.isoformat() if resp.response_at else None,
                "terms_offered": resp.terms_offered,
                "pass_reason": resp.pass_reason,
                "notes": resp.notes,
            } if resp else None,
        }
        for dist, resp in rows
    ]


async def record_closing(
    db: AsyncSession,
    deal_id: uuid.UUID,
    winning_lender_id: uuid.UUID,
    final_terms: dict | None = None,
    total_turnaround_days: int | None = None,
    notes: str | None = None,
) -> DealClosing:
    closing = DealClosing(
        deal_id=deal_id,
        winning_lender_id=winning_lender_id,
        final_terms=final_terms,
        total_turnaround_days=total_turnaround_days,
        notes=notes,
    )
    db.add(closing)
    await db.flush()
    await db.refresh(closing)
    return closing


async def get_closing(db: AsyncSession, deal_id: uuid.UUID) -> DealClosing | None:
    result = await db.execute(
        select(DealClosing).where(DealClosing.deal_id == deal_id)
    )
    return result.scalar_one_or_none()
