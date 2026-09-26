"""Risk Assessment Report API routes — mirror of OM routes."""

import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.db.session import get_db
from app.models.deal import Deal
from app.models.risk import RiskReport
from app.models.user import User
from app.schemas.risk import (
    RiskReportListResponse,
    RiskReportResponse,
    RiskReportStatusResponse,
)
from app.storage.s3 import download_document

router = APIRouter()


def _to_response(r: RiskReport) -> RiskReportResponse:
    return RiskReportResponse(
        id=str(r.id),
        deal_id=str(r.deal_id),
        version_number=r.version_number,
        page_count=r.page_count,
        file_size=r.file_size,
        overall_risk_rating=r.overall_risk_rating,
        risk_summary=r.risk_summary,
        findings_count=r.findings_count,
        generated_at=r.generated_at,
        status=r.status,
    )


async def _get_deal(deal_id: uuid.UUID, db: AsyncSession) -> Deal:
    result = await db.execute(select(Deal).where(Deal.id == deal_id))
    deal = result.scalar_one_or_none()
    if deal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deal not found")
    return deal


@router.get("/status", response_model=RiskReportStatusResponse)
async def get_risk_status(
    deal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _get_deal(deal_id, db)

    result = await db.execute(
        select(RiskReport)
        .where(RiskReport.deal_id == deal_id)
        .order_by(RiskReport.version_number.desc())
        .limit(1)
    )
    latest = result.scalar_one_or_none()

    if latest is None:
        return RiskReportStatusResponse(deal_id=str(deal_id), status="idle", latest_version=None)

    return RiskReportStatusResponse(
        deal_id=str(deal_id),
        status="ready",
        latest_version=_to_response(latest),
    )


@router.get("/versions", response_model=RiskReportListResponse)
async def list_risk_versions(
    deal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _get_deal(deal_id, db)

    result = await db.execute(
        select(RiskReport)
        .where(RiskReport.deal_id == deal_id)
        .order_by(RiskReport.version_number.desc())
    )
    versions = result.scalars().all()

    return RiskReportListResponse(versions=[_to_response(v) for v in versions])


@router.get("/versions/{version_id}/preview")
async def preview_risk(
    deal_id: uuid.UUID,
    version_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _get_deal(deal_id, db)

    result = await db.execute(
        select(RiskReport).where(
            RiskReport.id == version_id,
            RiskReport.deal_id == deal_id,
        )
    )
    version = result.scalar_one_or_none()
    if version is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Risk report not found")

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
async def download_risk(
    deal_id: uuid.UUID,
    version_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _get_deal(deal_id, db)

    result = await db.execute(
        select(RiskReport).where(
            RiskReport.id == version_id,
            RiskReport.deal_id == deal_id,
        )
    )
    version = result.scalar_one_or_none()
    if version is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Risk report not found")

    try:
        pdf_bytes = download_document(version.s3_key)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to download risk PDF from storage",
        )

    filename = f"Risk_Report_v{version.version_number}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
