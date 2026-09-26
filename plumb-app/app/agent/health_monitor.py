"""Sprint 4: Deal Health Monitor — 15-minute polling for stale deals and alerts."""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.deal import Deal
from app.models.lender import LenderAppetite
from app.models.metrics import Alert
from app.services.sla_monitor import check_sla_breaches


async def run_health_check(db: AsyncSession) -> dict:
    """Run all health checks. Called by Celery beat every 15 minutes."""
    results = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "sla_breaches": [],
        "stale_appetite": [],
        "stalled_deals": [],
    }

    # 1. SLA breaches
    breaches = await check_sla_breaches(db)
    results["sla_breaches"] = breaches

    # 2. Stale lender appetite data (>90 days)
    now = datetime.now(timezone.utc)
    stale_result = await db.execute(
        select(LenderAppetite).where(
            LenderAppetite.expires_at < now,
            LenderAppetite.is_stale == False,  # noqa: E712
        )
    )
    stale_appetites = stale_result.scalars().all()
    for appetite in stale_appetites:
        appetite.is_stale = True
        results["stale_appetite"].append({
            "lender_id": str(appetite.lender_id),
            "recorded_at": appetite.recorded_at.isoformat() if appetite.recorded_at else None,
            "expires_at": appetite.expires_at.isoformat() if appetite.expires_at else None,
        })

    # 3. Deals stalled in processing states (>24 hours without progress)
    stall_threshold = now - timedelta(hours=24)
    processing_states = ["classifying", "extracting", "market_enrichment", "model_building", "om_drafting"]
    stalled_result = await db.execute(
        select(Deal).where(
            Deal.status.in_(processing_states),
            Deal.updated_at < stall_threshold,
        )
    )
    stalled_deals = stalled_result.scalars().all()
    for deal in stalled_deals:
        results["stalled_deals"].append({
            "deal_id": str(deal.id),
            "property_name": deal.property_name,
            "status": deal.status,
            "updated_at": deal.updated_at.isoformat() if deal.updated_at else None,
        })

        # Create alert for stalled deal
        alert = Alert(
            deal_id=deal.id,
            alert_type="stalled",
            stage_name=deal.status,
            message=f"Deal '{deal.property_name}' stalled in {deal.status} for >24h",
            severity="warning",
        )
        db.add(alert)

    await db.flush()
    return results
