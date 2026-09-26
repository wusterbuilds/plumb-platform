"""Market intelligence API routes."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.db.session import get_db
from app.models.deal import Deal
from app.models.market import MarketData
from app.models.user import User

router = APIRouter(prefix="/deals/{deal_id}/market", tags=["market"])


class MarketDataResponse(BaseModel):
    id: uuid.UUID
    deal_id: uuid.UUID
    data_source: str
    data_type: str
    data: dict | None
    source_url: str | None
    confidence_score: float | None

    model_config = {"from_attributes": True}


class MarketDataListResponse(BaseModel):
    records: list[MarketDataResponse]
    total: int


class EnrichResponse(BaseModel):
    status: str
    task_id: str


class ImportResponse(BaseModel):
    status: str
    importer: str | None
    records_imported: int
    warnings: list[str]


class ValidationFlag(BaseModel):
    field: str
    borrower_value: str | None = None
    market_value: str | None = None
    severity: str
    explanation: str


class ValidationResponse(BaseModel):
    flags: list[ValidationFlag]
    overall_assessment: str | None
    summary: str | None


async def _get_deal(deal_id: uuid.UUID, db: AsyncSession) -> Deal:
    result = await db.execute(select(Deal).where(Deal.id == deal_id))
    deal = result.scalar_one_or_none()
    if deal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deal not found")
    return deal


@router.post("/enrich", response_model=EnrichResponse)
async def trigger_enrichment(
    deal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Manually trigger market enrichment pipeline for a deal."""
    deal = await _get_deal(deal_id, db)

    from app.tasks.market_enrichment import run_market_enrichment
    task = run_market_enrichment.delay(str(deal_id), str(current_user.id))

    return EnrichResponse(status="started", task_id=task.id)


@router.get("/status")
async def get_enrichment_status(
    deal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get enrichment progress per fetcher."""
    deal = await _get_deal(deal_id, db)

    result = await db.execute(
        select(MarketData)
        .where(MarketData.deal_id == deal_id)
    )
    records = result.scalars().all()

    sources = {}
    for rec in records:
        key = rec.data_source
        sources[key] = {
            "data_source": rec.data_source,
            "data_type": rec.data_type,
            "status": "success" if rec.data else "empty",
            "confidence": rec.confidence_score,
            "source_url": rec.source_url,
        }

    expected = ["zola", "acris", "dob", "news", "ag_refb"]
    fetcher_status = {}
    for src in expected:
        if src in sources:
            fetcher_status[src] = sources[src]
        else:
            fetcher_status[src] = {"data_source": src, "status": "pending"}

    return {
        "deal_id": str(deal_id),
        "deal_status": deal.status,
        "fetchers": fetcher_status,
        "total_records": len(records),
        "has_market_context": deal.market_context is not None,
    }


@router.get("/context")
async def get_market_context(
    deal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the assembled market_context JSON."""
    deal = await _get_deal(deal_id, db)
    if deal.market_context is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Market context not yet assembled",
        )
    return deal.market_context


@router.get("/data", response_model=MarketDataListResponse)
async def list_market_data(
    deal_id: uuid.UUID,
    data_source: str | None = None,
    data_type: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List individual market_data records for a deal."""
    await _get_deal(deal_id, db)

    query = select(MarketData).where(MarketData.deal_id == deal_id)
    if data_source:
        query = query.where(MarketData.data_source == data_source)
    if data_type:
        query = query.where(MarketData.data_type == data_type)
    query = query.order_by(MarketData.created_at.desc())

    result = await db.execute(query)
    records = result.scalars().all()

    return MarketDataListResponse(records=records, total=len(records))


@router.post("/import", response_model=ImportResponse)
async def import_market_data(
    deal_id: uuid.UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload a CoStar/Argus/MarketProof file, auto-detect format, import."""
    await _get_deal(deal_id, db)

    file_bytes = await file.read()
    filename = file.filename or "unknown"

    from app.importers.registry import detect_importer
    importer = detect_importer(file_bytes, filename)

    if importer is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Could not detect importer for '{filename}'. "
                   "Supported formats: CoStar comp/market exports, Argus DCF, MarketProof exports.",
        )

    import_result = importer.run(file_bytes, filename)

    record = MarketData(
        deal_id=deal_id,
        data_source=import_result.data_source,
        data_type=import_result.data_type,
        data={"records": import_result.records, "warnings": import_result.warnings},
        confidence_score=0.9,
    )
    db.add(record)
    await db.flush()

    return ImportResponse(
        status="imported",
        importer=import_result.data_source,
        records_imported=len(import_result.records),
        warnings=import_result.warnings,
    )


@router.get("/validation", response_model=ValidationResponse)
async def get_validation(
    deal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return borrower assumption validation flags."""
    deal = await _get_deal(deal_id, db)
    mc = deal.market_context
    if mc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Market context not yet assembled",
        )

    flags = mc.get("validation_flags", [])
    return ValidationResponse(
        flags=[ValidationFlag(**f) for f in flags if isinstance(f, dict)],
        overall_assessment=mc.get("overall_assessment"),
        summary=mc.get("validation_summary"),
    )
