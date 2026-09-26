"""OM (Offering Memorandum) API routes."""

import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user, get_current_user_or_query_token
from app.db.session import get_db
from app.models.deal import Deal
from app.models.om import OMVersion
from app.models.user import User
from app.schemas.om import (
    OMGenerateRequest,
    OMGenerateResponse,
    OMNarrativeUpdate,
    OMStatusResponse,
    OMVersionListResponse,
    OMVersionResponse,
)
from app.storage.s3 import download_document, get_presigned_url

router = APIRouter()


def _om_version_to_response(v: OMVersion) -> OMVersionResponse:
    return OMVersionResponse(
        id=str(v.id),
        deal_id=str(v.deal_id),
        version_number=v.version_number,
        page_count=v.page_count,
        file_size=v.file_size,
        generated_at=v.generated_at,
        status=v.status,
    )


async def _get_deal(deal_id: uuid.UUID, db: AsyncSession) -> Deal:
    result = await db.execute(select(Deal).where(Deal.id == deal_id))
    deal = result.scalar_one_or_none()
    if deal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deal not found")
    return deal


@router.post("/generate", response_model=OMGenerateResponse)
async def generate_om(
    deal_id: uuid.UUID,
    request: OMGenerateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Trigger OM generation as an async Celery task."""
    deal = await _get_deal(deal_id, db)

    # Verify deal is in OM_DRAFTING or later state
    allowed_statuses = {
        "om_drafting", "om_review", "lender_outreach", "tracking",
        "term_sheet_received", "closed",
    }
    if deal.status not in allowed_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Deal must be in OM_DRAFTING or later state to generate OM. Current: {deal.status}",
        )

    # Verify financial model exists
    fm = (deal.typed_extension or {}).get("financial_model")
    if not fm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Financial model not yet calculated. Run model building first.",
        )

    from app.tasks.om_generation import run_om_generation

    run_om_generation.delay(str(deal_id), str(current_user.id), request.regenerate_narratives)

    return OMGenerateResponse(
        deal_id=str(deal_id),
        status="generating",
        message="OM generation started. Poll /status for progress.",
    )


@router.get("/status", response_model=OMStatusResponse)
async def get_om_status(
    deal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get OM generation status and latest version."""
    await _get_deal(deal_id, db)

    result = await db.execute(
        select(OMVersion)
        .where(OMVersion.deal_id == deal_id)
        .order_by(OMVersion.version_number.desc())
        .limit(1)
    )
    latest = result.scalar_one_or_none()

    if latest is None:
        return OMStatusResponse(deal_id=str(deal_id), status="idle", latest_version=None)

    om_status = "generating" if latest.status == "generating" else "ready"
    return OMStatusResponse(
        deal_id=str(deal_id),
        status=om_status,
        latest_version=_om_version_to_response(latest),
    )


@router.get("/versions", response_model=OMVersionListResponse)
async def list_om_versions(
    deal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all OM versions for a deal."""
    await _get_deal(deal_id, db)

    result = await db.execute(
        select(OMVersion)
        .where(OMVersion.deal_id == deal_id)
        .order_by(OMVersion.version_number.desc())
    )
    versions = result.scalars().all()

    return OMVersionListResponse(
        versions=[_om_version_to_response(v) for v in versions],
    )


@router.get("/versions/{version_id}/preview")
async def preview_om(
    deal_id: uuid.UUID,
    version_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return HTML pages for in-app preview."""
    await _get_deal(deal_id, db)

    result = await db.execute(
        select(OMVersion).where(
            OMVersion.id == version_id,
            OMVersion.deal_id == deal_id,
        )
    )
    version = result.scalar_one_or_none()
    if version is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="OM version not found")

    if version.status == "generating":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="OM is still generating. Try again shortly.",
        )

    if not version.html_s3_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="HTML preview not available for this version",
        )

    try:
        html_bytes = download_document(version.html_s3_key)
        html_pages = json.loads(html_bytes)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load HTML preview from storage",
        )

    return {"deal_id": str(deal_id), "version_id": str(version_id), "pages": html_pages}


@router.get("/versions/{version_id}/download")
async def download_om(
    deal_id: uuid.UUID,
    version_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_or_query_token),
):
    """Download the OM PDF."""
    await _get_deal(deal_id, db)

    result = await db.execute(
        select(OMVersion).where(
            OMVersion.id == version_id,
            OMVersion.deal_id == deal_id,
        )
    )
    version = result.scalar_one_or_none()
    if version is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="OM version not found")

    if version.status == "generating":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="OM is still generating. Try again shortly.",
        )

    try:
        pdf_bytes = download_document(version.s3_key)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to download OM PDF from storage",
        )

    filename = f"OM_v{version.version_number}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


@router.put("/versions/{version_id}/narratives")
async def update_narratives(
    deal_id: uuid.UUID,
    version_id: uuid.UUID,
    update: OMNarrativeUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update narrative text and trigger re-render."""
    await _get_deal(deal_id, db)

    result = await db.execute(
        select(OMVersion).where(
            OMVersion.id == version_id,
            OMVersion.deal_id == deal_id,
        )
    )
    version = result.scalar_one_or_none()
    if version is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="OM version not found")

    # Merge updates into existing narrative snapshot
    current_narratives = version.narrative_snapshot or {}
    update_data = update.model_dump(exclude_unset=True)
    merged = {**current_narratives, **{k: v for k, v in update_data.items() if v is not None}}

    version.narrative_snapshot = merged
    await db.flush()

    # Trigger regeneration with the updated narratives (skip LLM narrative generation)
    from app.tasks.om_generation import run_om_generation

    run_om_generation.delay(str(deal_id), str(current_user.id), False)

    return {
        "deal_id": str(deal_id),
        "version_id": str(version_id),
        "status": "regenerating",
        "message": "Narratives updated. New OM version being generated with updated text.",
    }
