"""Financial model API routes."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.db.session import get_db, sync_session_factory
from app.models.deal import Deal
from app.models.user import User
from app.schemas.financial import AssumptionsUpdate, CalculateRequest, CalculateResponse

router = APIRouter()


async def _get_deal(deal_id: uuid.UUID, db: AsyncSession) -> Deal:
    result = await db.execute(select(Deal).where(Deal.id == deal_id))
    deal = result.scalar_one_or_none()
    if deal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deal not found")
    return deal


@router.post("/calculate", response_model=CalculateResponse)
async def calculate_financial_model(
    deal_id: uuid.UUID,
    request: CalculateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Run financial model calculations for a deal."""
    deal = await _get_deal(deal_id, db)

    from app.financial.engine import build_financial_model
    from app.financial.schemas import ModelAssumptions

    sync_db = sync_session_factory()
    try:
        assumptions = ModelAssumptions(**(request.assumptions or {})) if request.assumptions else None
        model = build_financial_model(deal_id, sync_db, assumptions)
        model_dict = model.model_dump()

        # Store in typed_extension
        deal.typed_extension = {**(deal.typed_extension or {}), "financial_model": model_dict}
        deal.version += 1
        await db.flush()

        return CalculateResponse(deal_id=str(deal_id), status="success", model=model_dict)
    except Exception as e:
        return CalculateResponse(deal_id=str(deal_id), status="error", errors=[str(e)])
    finally:
        sync_db.close()


@router.get("/model")
async def get_financial_model(
    deal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the calculated financial model for a deal."""
    deal = await _get_deal(deal_id, db)

    fm = (deal.typed_extension or {}).get("financial_model")
    if not fm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Financial model not yet calculated",
        )
    return fm


@router.get("/excel")
async def download_excel(
    deal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Download the Excel workbook for a deal."""
    deal = await _get_deal(deal_id, db)

    fm = (deal.typed_extension or {}).get("financial_model")
    if not fm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Financial model not yet calculated",
        )

    from app.financial.excel_builder import build_excel
    from app.financial.schemas import FinancialModel

    model = FinancialModel(**fm)
    excel_bytes = build_excel(model, deal.property_name or "Deal")

    filename = f"{deal.property_name or 'Deal'} - Financial Model.xlsx"
    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.put("/assumptions")
async def update_assumptions(
    deal_id: uuid.UUID,
    update: AssumptionsUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update financial assumptions and recalculate."""
    deal = await _get_deal(deal_id, db)

    # Merge new assumptions with existing
    existing = (deal.typed_extension or {}).get("financial_model", {}).get("assumptions", {})
    new_assumptions = {**existing, **{k: v for k, v in update.model_dump().items() if v is not None}}

    from app.financial.engine import build_financial_model
    from app.financial.schemas import ModelAssumptions

    sync_db = sync_session_factory()
    try:
        assumptions = ModelAssumptions(**new_assumptions)
        model = build_financial_model(deal_id, sync_db, assumptions)
        model_dict = model.model_dump()

        deal.typed_extension = {**(deal.typed_extension or {}), "financial_model": model_dict}
        deal.version += 1
        await db.flush()

        return {"deal_id": str(deal_id), "status": "recalculated", "model": model_dict}
    finally:
        sync_db.close()
