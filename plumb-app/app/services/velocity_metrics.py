"""Sprint 1: Deal velocity tracking — stage durations, TTAT, HuRT."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.metrics import DealStageDuration
from app.models.event import Event


async def record_stage_entry(
    db: AsyncSession,
    deal_id: uuid.UUID,
    stage_name: str,
    actor: str | None = None,
    revision_number: int = 1,
) -> DealStageDuration:
    duration = DealStageDuration(
        deal_id=deal_id,
        stage_name=stage_name,
        entered_at=datetime.now(timezone.utc),
        actor=actor,
        revision_number=revision_number,
    )
    db.add(duration)
    await db.flush()
    return duration


async def record_stage_exit(
    db: AsyncSession,
    deal_id: uuid.UUID,
    stage_name: str,
) -> DealStageDuration | None:
    result = await db.execute(
        select(DealStageDuration)
        .where(
            DealStageDuration.deal_id == deal_id,
            DealStageDuration.stage_name == stage_name,
            DealStageDuration.exited_at.is_(None),
        )
        .order_by(DealStageDuration.entered_at.desc())
        .limit(1)
    )
    duration = result.scalar_one_or_none()
    if duration:
        now = datetime.now(timezone.utc)
        duration.exited_at = now
        duration.duration_seconds = int((now - duration.entered_at).total_seconds())
        await db.flush()
    return duration


async def get_deal_velocity(db: AsyncSession, deal_id: uuid.UUID) -> dict:
    result = await db.execute(
        select(DealStageDuration)
        .where(DealStageDuration.deal_id == deal_id)
        .order_by(DealStageDuration.entered_at)
    )
    durations = result.scalars().all()

    stages = []
    total_seconds = 0
    human_wait_seconds = 0
    human_stages = {"extraction_review", "om_review"}

    for d in durations:
        secs = d.duration_seconds or 0
        total_seconds += secs
        if d.stage_name in human_stages:
            human_wait_seconds += secs
        stages.append({
            "stage_name": d.stage_name,
            "entered_at": d.entered_at.isoformat() if d.entered_at else None,
            "exited_at": d.exited_at.isoformat() if d.exited_at else None,
            "duration_seconds": d.duration_seconds,
            "revision_number": d.revision_number,
        })

    return {
        "deal_id": str(deal_id),
        "stages": stages,
        "total_turnaround_seconds": total_seconds,
        "human_wait_seconds": human_wait_seconds,
    }


async def get_aggregate_velocity(db: AsyncSession) -> dict:
    result = await db.execute(
        select(
            DealStageDuration.stage_name,
            func.avg(DealStageDuration.duration_seconds).label("avg_duration"),
            func.min(DealStageDuration.duration_seconds).label("min_duration"),
            func.max(DealStageDuration.duration_seconds).label("max_duration"),
            func.count(DealStageDuration.id).label("count"),
        )
        .where(DealStageDuration.duration_seconds.isnot(None))
        .group_by(DealStageDuration.stage_name)
    )
    rows = result.all()
    return {
        "stages": [
            {
                "stage_name": r.stage_name,
                "avg_duration_seconds": round(float(r.avg_duration), 1) if r.avg_duration else 0,
                "min_duration_seconds": r.min_duration,
                "max_duration_seconds": r.max_duration,
                "count": r.count,
            }
            for r in rows
        ]
    }


async def get_bottlenecks(db: AsyncSession) -> dict:
    result = await db.execute(
        select(
            DealStageDuration.stage_name,
            func.count(DealStageDuration.id).label("waiting_count"),
        )
        .where(DealStageDuration.exited_at.is_(None))
        .group_by(DealStageDuration.stage_name)
        .order_by(func.count(DealStageDuration.id).desc())
    )
    rows = result.all()
    return {
        "bottlenecks": [
            {"stage_name": r.stage_name, "waiting_count": r.waiting_count}
            for r in rows
        ]
    }
