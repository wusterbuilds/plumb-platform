"""Sprint 1: SLA monitoring — check active deals against SLA targets, generate alerts."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.deal import Deal
from app.models.metrics import Alert, DealStageDuration

# SLA targets in seconds
SLA_TARGETS: dict[str, dict] = {
    "classifying": {"target": 7200, "alert": 14400},
    "extracting": {"target": 7200, "alert": 14400},
    "extraction_review": {"target": 14400, "alert": 28800},
    "market_enrichment": {"target": 3600, "alert": 7200},
    "model_building": {"target": 3600, "alert": 7200},
    "om_drafting": {"target": 7200, "alert": 14400},
    "om_review": {"target": 14400, "alert": 28800},
}


async def check_sla_breaches(db: AsyncSession) -> list[dict]:
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(DealStageDuration)
        .where(DealStageDuration.exited_at.is_(None))
    )
    active_stages = result.scalars().all()

    breaches = []
    for stage in active_stages:
        sla = SLA_TARGETS.get(stage.stage_name)
        if not sla:
            continue

        elapsed = int((now - stage.entered_at).total_seconds())
        if elapsed > sla["alert"]:
            existing = await db.execute(
                select(Alert).where(
                    Alert.deal_id == stage.deal_id,
                    Alert.stage_name == stage.stage_name,
                    Alert.acknowledged == False,  # noqa: E712
                )
            )
            if existing.scalar_one_or_none():
                continue

            alert = Alert(
                deal_id=stage.deal_id,
                alert_type="sla_breach",
                stage_name=stage.stage_name,
                message=f"Deal has been in {stage.stage_name} for {elapsed // 3600}h {(elapsed % 3600) // 60}m (SLA: {sla['alert'] // 3600}h)",
                severity="critical" if elapsed > sla["alert"] * 2 else "warning",
            )
            db.add(alert)
            breaches.append({
                "deal_id": str(stage.deal_id),
                "stage_name": stage.stage_name,
                "elapsed_seconds": elapsed,
                "severity": alert.severity,
            })

    await db.flush()
    return breaches


async def get_active_alerts(db: AsyncSession, deal_id: uuid.UUID | None = None) -> list[dict]:
    query = select(Alert).where(Alert.acknowledged == False)  # noqa: E712
    if deal_id:
        query = query.where(Alert.deal_id == deal_id)
    query = query.order_by(Alert.created_at.desc())

    result = await db.execute(query)
    alerts = result.scalars().all()
    return [
        {
            "id": str(a.id),
            "deal_id": str(a.deal_id),
            "alert_type": a.alert_type,
            "stage_name": a.stage_name,
            "message": a.message,
            "severity": a.severity,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in alerts
    ]


async def acknowledge_alert(db: AsyncSession, alert_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    result = await db.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalar_one_or_none()
    if not alert:
        return False
    alert.acknowledged = True
    alert.acknowledged_by = user_id
    alert.acknowledged_at = datetime.now(timezone.utc)
    await db.flush()
    return True
