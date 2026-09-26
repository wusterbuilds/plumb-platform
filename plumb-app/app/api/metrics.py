"""API routes for Sprint 1: Metrics (velocity, quality, cost, SLA)."""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.services import cost_metrics, quality_metrics, sla_monitor, velocity_metrics

router = APIRouter(prefix="/metrics", tags=["metrics"])


# ── Velocity ──

@router.get("/velocity")
async def get_aggregate_velocity(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    return await velocity_metrics.get_aggregate_velocity(db)


@router.get("/velocity/{deal_id}")
async def get_deal_velocity(
    deal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    return await velocity_metrics.get_deal_velocity(db, deal_id)


@router.get("/velocity/bottlenecks")
async def get_bottlenecks(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    return await velocity_metrics.get_bottlenecks(db)


# ── Quality ──

@router.get("/quality")
async def get_aggregate_quality(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    return await quality_metrics.get_aggregate_quality(db)


@router.get("/quality/{deal_id}")
async def get_deal_quality(
    deal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    return await quality_metrics.get_deal_quality(db, deal_id)


@router.get("/quality/fields")
async def get_field_accuracy(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    return await quality_metrics.get_field_accuracy(db)


@router.get("/quality/prompts")
async def get_prompt_accuracy(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    return await quality_metrics.get_prompt_accuracy(db)


# ── Cost ──

@router.get("/cost")
async def get_aggregate_cost(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    return await cost_metrics.get_aggregate_cost(db)


@router.get("/cost/{deal_id}")
async def get_deal_cost(
    deal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    return await cost_metrics.get_deal_cost(db, deal_id)


@router.get("/cost/prompts")
async def get_prompt_costs(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    return await cost_metrics.get_prompt_costs(db)


# ── SLA / Alerts ──

@router.get("/alerts")
async def get_alerts(
    deal_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    return await sla_monitor.get_active_alerts(db, deal_id=deal_id)


@router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    success = await sla_monitor.acknowledge_alert(db, alert_id, user.id)
    return {"acknowledged": success}


@router.post("/sla/check")
async def trigger_sla_check(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    breaches = await sla_monitor.check_sla_breaches(db)
    return {"breaches": breaches}
