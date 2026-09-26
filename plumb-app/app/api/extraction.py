"""Extraction API endpoints."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.db.events import log_event
from app.db.session import get_db
from app.models.deal import Deal
from app.models.document import Document
from app.models.extraction import CrossReference, ExtractedValue
from app.models.user import User
from app.schemas.enums import (
    CrossRefResolution,
    DealStatus,
    EventType,
    FlagColor,
)
from app.schemas.extraction import (
    CrossReferenceListResponse,
    CrossReferenceResponse,
    DocumentExtractionStatus,
    ExtractionStartResponse,
    ExtractionStatusResponse,
    ExtractedValueListResponse,
    ExtractedValueResponse,
    OverrideRequest,
    ResolveRequest,
)

router = APIRouter(prefix="/deals/{deal_id}/extraction", tags=["extraction"])


@router.post("/start", response_model=ExtractionStartResponse, status_code=status.HTTP_202_ACCEPTED)
async def start_extraction(
    deal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Trigger the extraction pipeline for a deal."""
    result = await db.execute(select(Deal).where(Deal.id == deal_id))
    deal = result.scalar_one_or_none()
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")

    allowed_states = {
        DealStatus.DOCS_RECEIVED.value,
        DealStatus.EXTRACTION_FAILED.value,
    }
    if deal.status not in allowed_states:
        raise HTTPException(
            status_code=422,
            detail=f"Cannot start extraction from state '{deal.status}'. Must be in: {allowed_states}",
        )

    # Verify there are documents to process
    doc_count = await db.execute(
        select(func.count(Document.id)).where(Document.deal_id == deal_id)
    )
    if doc_count.scalar() == 0:
        raise HTTPException(status_code=422, detail="No documents uploaded for this deal")

    # Feature-flag: use agent pipeline or legacy Celery pipeline
    from app.agent import feature_flags

    use_agent = await feature_flags.is_enabled(db, "agent.extraction", deal_id=deal_id)
    if use_agent:
        import asyncio

        from app.db.session import async_session_factory

        async def _run():
            from app.agent.orchestrator import run_deal_pipeline_agent
            async with async_session_factory() as session:
                try:
                    await run_deal_pipeline_agent(db=session, deal_id=deal_id)
                    await session.commit()
                except Exception:
                    await session.rollback()
                    import logging
                    logging.getLogger(__name__).exception(
                        "Agent extraction pipeline failed for deal %s", deal_id
                    )

        asyncio.create_task(_run())
        return ExtractionStartResponse(
            deal_id=deal_id,
            task_id="agent-pipeline",
            message="Agent extraction pipeline started",
        )

    # Legacy Celery pipeline
    from app.tasks.pipeline import run_deal_pipeline

    task = run_deal_pipeline.delay(str(deal_id), str(current_user.id))

    return ExtractionStartResponse(
        deal_id=deal_id,
        task_id=task.id,
        message="Extraction pipeline started",
    )


@router.get("/status", response_model=ExtractionStatusResponse)
async def get_extraction_status(
    deal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the current extraction status for a deal."""
    result = await db.execute(select(Deal).where(Deal.id == deal_id))
    deal = result.scalar_one_or_none()
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")

    # Get document statuses
    docs_result = await db.execute(
        select(Document).where(Document.deal_id == deal_id)
    )
    docs = docs_result.scalars().all()

    doc_statuses = [
        DocumentExtractionStatus(
            doc_id=d.id,
            filename=d.filename,
            document_type=d.document_type,
            status=d.status,
            classification_confidence=d.classification_confidence,
        )
        for d in docs
    ]

    # Count extracted values by flag
    values_result = await db.execute(
        select(ExtractedValue.flag, func.count(ExtractedValue.id))
        .where(ExtractedValue.deal_id == deal_id)
        .group_by(ExtractedValue.flag)
    )
    flags_by_color = dict(values_result.all())
    total_fields = sum(flags_by_color.values())

    return ExtractionStatusResponse(
        deal_id=deal_id,
        deal_status=deal.status,
        documents=doc_statuses,
        total_fields_extracted=total_fields,
        fields_by_flag=flags_by_color,
    )


@router.get("/values", response_model=ExtractedValueListResponse)
async def list_extracted_values(
    deal_id: uuid.UUID,
    flag: FlagColor | None = Query(None, description="Filter by flag color"),
    field_name: str | None = Query(None, description="Filter by field name"),
    doc_id: uuid.UUID | None = Query(None, description="Filter by source document"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List extracted values for a deal, with optional filters."""
    query = select(ExtractedValue).where(ExtractedValue.deal_id == deal_id)

    if flag:
        query = query.where(ExtractedValue.flag == flag.value)
    if field_name:
        query = query.where(ExtractedValue.field_name == field_name)
    if doc_id:
        query = query.where(ExtractedValue.source_doc_id == doc_id)

    query = query.order_by(ExtractedValue.field_name)

    result = await db.execute(query)
    values = result.scalars().all()

    return ExtractedValueListResponse(
        values=[ExtractedValueResponse.model_validate(v) for v in values],
        total=len(values),
    )


@router.put("/values/{value_id}", response_model=ExtractedValueResponse)
async def override_value(
    deal_id: uuid.UUID,
    value_id: uuid.UUID,
    body: OverrideRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Override an extracted value with a human-provided value."""
    result = await db.execute(
        select(ExtractedValue).where(
            ExtractedValue.id == value_id,
            ExtractedValue.deal_id == deal_id,
        )
    )
    ev = result.scalar_one_or_none()
    if not ev:
        raise HTTPException(status_code=404, detail="Extracted value not found")

    # Optimistic concurrency check
    if ev.version != body.version:
        raise HTTPException(
            status_code=409,
            detail=f"Version conflict: expected {body.version}, found {ev.version}. Another user may have modified this value.",
        )

    ev.override_value = body.override_value
    ev.override_reason = body.override_reason
    ev.reviewed_by = current_user.id
    ev.reviewed_at = datetime.now(timezone.utc)
    ev.flag = FlagColor.GREEN.value  # overridden values are always green
    ev.version += 1

    await log_event(
        db=db,
        deal_id=deal_id,
        event_type=EventType.FIELD_OVERRIDDEN.value,
        actor_id=current_user.id,
        payload={
            "value_id": str(value_id),
            "field_name": ev.field_name,
            "original_value": ev.value,
            "override_value": body.override_value,
            "override_reason": body.override_reason,
        },
    )

    await db.flush()
    await db.refresh(ev)
    return ExtractedValueResponse.model_validate(ev)


@router.post("/values/{value_id}/review", response_model=ExtractedValueResponse)
async def review_value(
    deal_id: uuid.UUID,
    value_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Accept an extracted value as-is (mark as reviewed)."""
    result = await db.execute(
        select(ExtractedValue).where(
            ExtractedValue.id == value_id,
            ExtractedValue.deal_id == deal_id,
        )
    )
    ev = result.scalar_one_or_none()
    if not ev:
        raise HTTPException(status_code=404, detail="Extracted value not found")

    ev.reviewed_by = current_user.id
    ev.reviewed_at = datetime.now(timezone.utc)
    ev.flag = FlagColor.GREEN.value
    ev.version += 1

    await log_event(
        db=db,
        deal_id=deal_id,
        event_type=EventType.FIELD_REVIEWED.value,
        actor_id=current_user.id,
        payload={
            "value_id": str(value_id),
            "field_name": ev.field_name,
        },
    )

    await db.flush()
    await db.refresh(ev)
    return ExtractedValueResponse.model_validate(ev)


@router.get("/cross-references", response_model=CrossReferenceListResponse)
async def list_cross_references(
    deal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List cross-reference results for a deal."""
    result = await db.execute(
        select(CrossReference)
        .where(CrossReference.deal_id == deal_id)
        .order_by(CrossReference.rule_name)
    )
    xrefs = result.scalars().all()

    return CrossReferenceListResponse(
        cross_references=[CrossReferenceResponse.model_validate(x) for x in xrefs],
        total=len(xrefs),
    )


@router.post("/cross-references/{xref_id}/resolve", response_model=CrossReferenceResponse)
async def resolve_cross_reference(
    deal_id: uuid.UUID,
    xref_id: uuid.UUID,
    body: ResolveRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Resolve a cross-reference mismatch."""
    result = await db.execute(
        select(CrossReference).where(
            CrossReference.id == xref_id,
            CrossReference.deal_id == deal_id,
        )
    )
    xref = result.scalar_one_or_none()
    if not xref:
        raise HTTPException(status_code=404, detail="Cross-reference not found")

    xref.resolution = body.resolution.value
    xref.resolved_by = current_user.id
    xref.resolved_at = datetime.now(timezone.utc)

    await log_event(
        db=db,
        deal_id=deal_id,
        event_type=EventType.CROSS_REF_RESOLVED.value,
        actor_id=current_user.id,
        payload={
            "xref_id": str(xref_id),
            "rule_name": xref.rule_name,
            "resolution": body.resolution.value,
        },
    )

    await db.flush()
    await db.refresh(xref)
    return CrossReferenceResponse.model_validate(xref)
