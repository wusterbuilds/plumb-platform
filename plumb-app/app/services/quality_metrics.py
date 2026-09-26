"""Sprint 1: Quality scoring — override rates, field accuracy, cross-ref failures."""

import uuid

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.extraction import CrossReference, ExtractedValue


async def get_deal_quality(db: AsyncSession, deal_id: uuid.UUID) -> dict:
    total_q = select(func.count(ExtractedValue.id)).where(ExtractedValue.deal_id == deal_id)
    overridden_q = select(func.count(ExtractedValue.id)).where(
        ExtractedValue.deal_id == deal_id,
        ExtractedValue.override_value.isnot(None),
    )
    xref_total_q = select(func.count(CrossReference.id)).where(CrossReference.deal_id == deal_id)
    xref_fail_q = select(func.count(CrossReference.id)).where(
        CrossReference.deal_id == deal_id,
        CrossReference.result == "mismatch",
    )

    total = (await db.execute(total_q)).scalar() or 0
    overridden = (await db.execute(overridden_q)).scalar() or 0
    xref_total = (await db.execute(xref_total_q)).scalar() or 0
    xref_fail = (await db.execute(xref_fail_q)).scalar() or 0

    return {
        "deal_id": str(deal_id),
        "total_fields": total,
        "overridden_fields": overridden,
        "override_rate": round(overridden / total, 4) if total > 0 else 0,
        "cross_ref_total": xref_total,
        "cross_ref_failures": xref_fail,
        "cross_ref_failure_rate": round(xref_fail / xref_total, 4) if xref_total > 0 else 0,
    }


async def get_aggregate_quality(db: AsyncSession) -> dict:
    total = (await db.execute(select(func.count(ExtractedValue.id)))).scalar() or 0
    overridden = (await db.execute(
        select(func.count(ExtractedValue.id)).where(ExtractedValue.override_value.isnot(None))
    )).scalar() or 0

    return {
        "total_fields": total,
        "overridden_fields": overridden,
        "override_rate": round(overridden / total, 4) if total > 0 else 0,
    }


async def get_field_accuracy(db: AsyncSession) -> dict:
    result = await db.execute(
        select(
            ExtractedValue.field_name,
            func.count(ExtractedValue.id).label("total"),
            func.count(case((ExtractedValue.override_value.isnot(None), 1))).label("overridden"),
        )
        .group_by(ExtractedValue.field_name)
        .order_by(func.count(case((ExtractedValue.override_value.isnot(None), 1))).desc())
    )
    rows = result.all()
    return {
        "fields": [
            {
                "field_name": r.field_name,
                "total": r.total,
                "overridden": r.overridden,
                "override_rate": round(r.overridden / r.total, 4) if r.total > 0 else 0,
            }
            for r in rows
        ]
    }


async def get_prompt_accuracy(db: AsyncSession) -> dict:
    result = await db.execute(
        select(
            ExtractedValue.prompt_version,
            func.count(ExtractedValue.id).label("total"),
            func.count(case((ExtractedValue.override_value.isnot(None), 1))).label("overridden"),
        )
        .where(ExtractedValue.prompt_version.isnot(None))
        .group_by(ExtractedValue.prompt_version)
    )
    rows = result.all()
    return {
        "prompts": [
            {
                "prompt_version": r.prompt_version,
                "total": r.total,
                "overridden": r.overridden,
                "accuracy": round(1 - (r.overridden / r.total), 4) if r.total > 0 else 1.0,
            }
            for r in rows
        ]
    }
