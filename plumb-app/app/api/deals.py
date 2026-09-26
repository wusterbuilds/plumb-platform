import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.db.events import log_event
from app.db.session import get_db
from app.models.deal import Deal
from app.models.event import Event
from app.models.user import User
from app.schemas.deal import (
    DealCreate,
    DealListResponse,
    DealResponse,
    DealUpdate,
    TransitionRequest,
)
from app.schemas.enums import DealStatus, EventType
from app.schemas.event import EventListResponse, EventResponse
from app.state_machine.engine import transition

router = APIRouter(prefix="/deals", tags=["deals"])


@router.post("", response_model=DealResponse, status_code=status.HTTP_201_CREATED)
async def create_deal(
    body: DealCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    deal = Deal(
        deal_type=body.deal_type.value,
        deal_subtype=body.deal_subtype.value if body.deal_subtype else None,
        capital_ask=body.capital_ask.value if body.capital_ask else None,
        status=DealStatus.DOCS_RECEIVED.value,
        property_name=body.property_name,
        property_address=body.property_address,
        property_type=body.property_type.value if body.property_type else None,
        typed_extension=body.typed_extension,
        created_by=current_user.id,
    )
    db.add(deal)
    await db.flush()
    await db.refresh(deal)

    await log_event(
        db=db,
        deal_id=deal.id,
        event_type=EventType.DEAL_CREATED.value,
        actor_id=current_user.id,
        payload={"deal_type": deal.deal_type, "property_address": deal.property_address},
    )

    return deal


@router.get("", response_model=DealListResponse)
async def list_deals(
    status_filter: DealStatus | None = Query(None, alias="status"),
    deal_type: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(Deal)
    if status_filter:
        query = query.where(Deal.status == status_filter.value)
    if deal_type:
        query = query.where(Deal.deal_type == deal_type)
    query = query.order_by(Deal.updated_at.desc())

    result = await db.execute(query)
    deals = result.scalars().all()

    count_query = select(func.count(Deal.id))
    if status_filter:
        count_query = count_query.where(Deal.status == status_filter.value)
    if deal_type:
        count_query = count_query.where(Deal.deal_type == deal_type)
    total = (await db.execute(count_query)).scalar() or 0

    return DealListResponse(deals=deals, total=total)


@router.get("/{deal_id}", response_model=DealResponse)
async def get_deal(
    deal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Deal).where(Deal.id == deal_id))
    deal = result.scalar_one_or_none()
    if deal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deal not found")
    return deal


@router.patch("/{deal_id}", response_model=DealResponse)
async def update_deal(
    deal_id: uuid.UUID,
    body: DealUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Deal).where(Deal.id == deal_id))
    deal = result.scalar_one_or_none()
    if deal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deal not found")

    # Optimistic concurrency check
    if deal.version != body.version:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Version conflict: expected {body.version}, current is {deal.version}. "
            f"Another user may have modified this deal.",
        )

    update_data = body.model_dump(exclude_unset=True, exclude={"version"})
    changed_fields = []
    for field, value in update_data.items():
        if value is not None:
            # Convert enums to their string value
            if hasattr(value, "value"):
                value = value.value
            setattr(deal, field, value)
            changed_fields.append(field)

    if changed_fields:
        deal.version += 1
        await log_event(
            db=db,
            deal_id=deal.id,
            event_type=EventType.DEAL_UPDATED.value,
            actor_id=current_user.id,
            payload={"updated_fields": changed_fields},
            revision_number=deal.revision_number,
        )

    await db.flush()
    await db.refresh(deal)
    return deal


@router.post("/{deal_id}/transition", response_model=DealResponse)
async def transition_deal(
    deal_id: uuid.UUID,
    body: TransitionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    deal = await transition(
        db=db,
        deal_id=deal_id,
        target_status=body.target_status,
        actor_id=current_user.id,
        reason=body.reason,
        dead_reason=body.dead_reason,
    )

    # Feature-flag: use agent pipeline or legacy Celery pipeline
    from app.agent import feature_flags

    if body.target_status == DealStatus.MARKET_ENRICHMENT:
        use_agent = await feature_flags.is_enabled(db, "agent.research", deal_id=deal_id)
        if use_agent:
            import asyncio
            asyncio.create_task(
                _run_agent_pipeline_background(deal_id, current_user.id)
            )
        else:
            from app.tasks.market_enrichment import run_market_enrichment
            run_market_enrichment.delay(str(deal_id), str(current_user.id))

    if body.target_status == DealStatus.MODEL_BUILDING:
        use_agent = await feature_flags.is_enabled(db, "agent.underwriting", deal_id=deal_id)
        if use_agent:
            import asyncio
            asyncio.create_task(
                _run_agent_pipeline_background(deal_id, current_user.id)
            )
        else:
            from app.tasks.model_building import run_model_building
            run_model_building.delay(str(deal_id), str(current_user.id))

    return deal


async def _run_agent_pipeline_background(
    deal_id: uuid.UUID, actor_id: uuid.UUID,
) -> None:
    """Run agent pipeline in background with a fresh DB session."""
    import logging

    from app.agent.orchestrator import run_deal_pipeline_agent
    from app.db.session import async_session_factory

    async with async_session_factory() as session:
        try:
            await run_deal_pipeline_agent(db=session, deal_id=deal_id)
            await session.commit()
        except Exception:
            await session.rollback()
            logging.getLogger(__name__).exception(
                "Background agent pipeline failed for deal %s", deal_id
            )


@router.get("/{deal_id}/events", response_model=EventListResponse)
async def list_deal_events(
    deal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Verify deal exists
    deal_result = await db.execute(select(Deal).where(Deal.id == deal_id))
    if deal_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deal not found")

    result = await db.execute(
        select(Event).where(Event.deal_id == deal_id).order_by(Event.timestamp.asc())
    )
    events = result.scalars().all()

    return EventListResponse(events=events, total=len(events))
