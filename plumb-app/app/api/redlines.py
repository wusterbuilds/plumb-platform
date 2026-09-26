"""Expert feedback / redline capture API.

Routes:

- `POST   /deals/{deal_id}/redlines`                   create a redline
- `GET    /deals/{deal_id}/redlines`                   list redlines (optionally for a version)
- `POST   /deals/{deal_id}/om/versions/{version_id}/rerun-with-feedback`
- `POST   /deals/{deal_id}/om/versions/{version_id}/approve`
- `GET    /deals/{deal_id}/om/versions/{version_id}/narratives`
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.db.events import log_event
from app.db.session import get_db
from app.models.deal import Deal
from app.models.draft_redline import DraftRedline
from app.models.om import OMVersion
from app.models.user import User
from app.schemas.enums import EventType
from app.schemas.redline import (
    OMApproveResponse,
    OMNarrativeSnapshot,
    RedlineCreate,
    RedlineListResponse,
    RedlineResponse,
    RerunWithFeedbackResponse,
)
from app.services.redline_service import (
    compute_archetype,
    fetch_relevant_lessons_async,
    list_redlines_for_deal_async,
    store_redline_async,
)


router = APIRouter()


async def _get_deal(deal_id: uuid.UUID, db: AsyncSession) -> Deal:
    result = await db.execute(select(Deal).where(Deal.id == deal_id))
    deal = result.scalar_one_or_none()
    if deal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deal not found")
    return deal


async def _get_version(
    deal_id: uuid.UUID, version_id: uuid.UUID, db: AsyncSession
) -> OMVersion:
    result = await db.execute(
        select(OMVersion).where(
            OMVersion.id == version_id,
            OMVersion.deal_id == deal_id,
        )
    )
    version = result.scalar_one_or_none()
    if version is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="OM version not found")
    return version


def _redline_to_response(r: DraftRedline) -> RedlineResponse:
    return RedlineResponse(
        id=str(r.id),
        deal_id=str(r.deal_id),
        artifact_type=r.artifact_type,
        artifact_ref_id=str(r.artifact_ref_id),
        section_key=r.section_key,
        section_index=r.section_index,
        original_text=r.original_text,
        edited_text=r.edited_text,
        rationale=r.rationale,
        correction_category=r.correction_category,
        severity=r.severity,
        archetype_signature=r.archetype_signature,
        reviewer_id=str(r.reviewer_id) if r.reviewer_id else None,
        reviewer_role=r.reviewer_role,
        episode_id=str(r.episode_id) if r.episode_id else None,
        applied_in_version_id=str(r.applied_in_version_id) if r.applied_in_version_id else None,
        created_at=r.created_at,
    )


@router.post(
    "/deals/{deal_id}/om/versions/{version_id}/redlines",
    response_model=RedlineResponse,
)
async def create_redline(
    deal_id: uuid.UUID,
    version_id: uuid.UUID,
    payload: RedlineCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Capture an expert correction against an OM section.

    Persists a `DraftRedline`, projects it into an `Episode` so the
    correction surfaces on the next narrative regeneration for similar
    deals, and bumps the version's redline_count cache.
    """
    deal = await _get_deal(deal_id, db)
    version = await _get_version(deal_id, version_id, db)

    if not payload.original_text.strip() or not payload.edited_text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="original_text and edited_text are required",
        )

    redline, episode = await store_redline_async(
        db,
        deal=deal,
        artifact_type=payload.artifact_type,
        artifact_ref_id=version.id,
        section_key=payload.section_key,
        section_index=payload.section_index,
        original_text=payload.original_text,
        edited_text=payload.edited_text,
        rationale=payload.rationale,
        correction_category=payload.correction_category,
        severity=payload.severity,
        reviewer_id=current_user.id,
        reviewer_role=getattr(current_user, "role", None) or "cre_expert",
    )

    await log_event(
        db=db,
        deal_id=deal.id,
        event_type=EventType.FIELD_OVERRIDDEN.value,
        actor_id=current_user.id,
        payload={
            "artifact": "om_section",
            "section_key": redline.section_key,
            "category": redline.correction_category,
            "severity": redline.severity,
            "version_id": str(version.id),
            "version_number": version.version_number,
            "episode_id": str(episode.id),
            "archetype": redline.archetype_signature,
        },
    )

    await db.commit()
    return _redline_to_response(redline)


@router.get(
    "/deals/{deal_id}/redlines",
    response_model=RedlineListResponse,
)
async def list_redlines(
    deal_id: uuid.UUID,
    version_id: uuid.UUID | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _get_deal(deal_id, db)
    redlines = await list_redlines_for_deal_async(
        db, deal_id=deal_id, version_id=version_id
    )
    return RedlineListResponse(
        redlines=[_redline_to_response(r) for r in redlines],
        total=len(redlines),
    )


@router.get(
    "/deals/{deal_id}/om/versions/{version_id}/narratives",
    response_model=OMNarrativeSnapshot,
)
async def get_om_narratives(
    deal_id: uuid.UUID,
    version_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the structured narrative_snapshot for a given OM version.

    The redline editor reads this — it cannot redline a PDF iframe.
    """
    await _get_deal(deal_id, db)
    version = await _get_version(deal_id, version_id, db)

    snap = version.narrative_snapshot or {}
    return OMNarrativeSnapshot(
        version_id=str(version.id),
        version_number=version.version_number,
        transaction_overview=list(snap.get("transaction_overview") or []),
        investment_highlights=list(snap.get("investment_highlights") or []),
        market_narrative=list(snap.get("market_narrative") or []),
        sponsor_bios=dict(snap.get("sponsor_bios") or {}),
        redline_count=version.redline_count or 0,
        archetype_signature=version.archetype_signature,
        approval_status=version.approval_status,
    )


@router.post(
    "/deals/{deal_id}/om/versions/{version_id}/rerun-with-feedback",
    response_model=RerunWithFeedbackResponse,
)
async def rerun_om_with_feedback(
    deal_id: uuid.UUID,
    version_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Regenerate the OM with archetype-relevant correction lessons injected.

    Distinct from the existing PUT /narratives endpoint, which simply rewrites
    text and re-renders. This endpoint:

      1. Pulls correction lessons matching the deal's archetype.
      2. Hands those lessons to the OM generation Celery task via the
         per-deal context (the LLM client picks them up automatically).
      3. Returns the lessons that will be applied so the UI can preview
         them ("Re-running with N expert lessons applied").

    The request itself does not block on regeneration — the existing
    OM-status polling infrastructure tracks progress.
    """
    deal = await _get_deal(deal_id, db)
    await _get_version(deal_id, version_id, db)

    fm = (deal.typed_extension or {}).get("financial_model")
    if not fm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot rerun: financial model not yet calculated.",
        )

    lessons = await fetch_relevant_lessons_async(db, deal=deal, limit=10)
    archetype = compute_archetype(deal)

    await log_event(
        db=db,
        deal_id=deal.id,
        event_type=EventType.REVISION_STARTED.value,
        actor_id=current_user.id,
        payload={
            "trigger": "rerun_with_feedback",
            "source_version_id": str(version_id),
            "archetype": archetype,
            "lesson_count": len(lessons),
        },
    )
    await db.commit()

    from app.tasks.om_generation import run_om_generation

    run_om_generation.delay(str(deal.id), str(current_user.id), True)

    return RerunWithFeedbackResponse(
        deal_id=str(deal.id),
        status="generating",
        message=(
            f"Regenerating OM with {len(lessons)} expert lesson(s) applied. "
            "Poll /om/status for progress."
        ),
        lessons_applied=lessons,
    )


@router.post(
    "/deals/{deal_id}/om/versions/{version_id}/approve",
    response_model=OMApproveResponse,
)
async def approve_om_version(
    deal_id: uuid.UUID,
    version_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark an OM version as approved by the reviewer.

    On approval the version is tagged with the deal's archetype signature
    and (if no redlines were filed) becomes exemplar-eligible — meaning a
    future deal of the same archetype can retrieve this version's
    narratives as a few-shot example.
    """
    deal = await _get_deal(deal_id, db)
    version = await _get_version(deal_id, version_id, db)

    archetype = compute_archetype(deal)
    version.approval_status = "approved"
    version.archetype_signature = archetype
    version.exemplar_eligible = (version.redline_count or 0) <= 3

    await log_event(
        db=db,
        deal_id=deal.id,
        event_type=EventType.OM_APPROVED.value,
        actor_id=current_user.id,
        payload={
            "version_id": str(version.id),
            "version_number": version.version_number,
            "archetype": archetype,
            "redline_count": version.redline_count or 0,
            "exemplar_eligible": version.exemplar_eligible,
        },
    )

    await db.commit()
    return OMApproveResponse(
        deal_id=str(deal.id),
        version_id=str(version.id),
        status="approved",
        archetype_signature=archetype,
        exemplar_eligible=version.exemplar_eligible,
    )
