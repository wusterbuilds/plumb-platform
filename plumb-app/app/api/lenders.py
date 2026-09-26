"""API routes for Sprint 3: Lenders, appetite, transactions, matching, deal outcomes."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.services import deal_outcome_service, lender_service

router = APIRouter(prefix="/lenders", tags=["lenders"])

# ── Schemas ──


class LenderCreate(BaseModel):
    name: str
    lender_type: str
    general_preferences: dict | None = None
    credit_committee_notes: str | None = None
    relationship_contacts: list | None = None
    notes: str | None = None


class LenderUpdate(BaseModel):
    name: str | None = None
    lender_type: str | None = None
    general_preferences: dict | None = None
    credit_committee_notes: str | None = None
    relationship_contacts: list | None = None
    notes: str | None = None


class AppetiteLog(BaseModel):
    appetite_signal: str  # hungry | active | selective | paused
    property_types: list[str] | None = None
    geographies: list[str] | None = None
    deal_size_min: float | None = None
    deal_size_max: float | None = None
    ltc_max: float | None = None
    rate_indication: str | None = None
    term_range: str | None = None
    recourse_preference: str | None = None
    source: str | None = None
    source_detail: str | None = None


class TransactionLog(BaseModel):
    deal_id: str | None = None
    property_type: str | None = None
    geography: str | None = None
    deal_size: float | None = None
    ltc_quoted: float | None = None
    rate_quoted: str | None = None
    term_quoted: str | None = None
    outcome: str | None = None
    pass_reason: str | None = None
    source: str | None = None


class DistributeRequest(BaseModel):
    lender_id: str
    approach_angle: str | None = None


class ResponseRecord(BaseModel):
    deal_distribution_id: str
    response_type: str  # ioi | term_sheet | pass | no_response | more_info
    terms_offered: dict | None = None
    pass_reason: str | None = None
    notes: str | None = None


class ClosingRecord(BaseModel):
    winning_lender_id: str
    final_terms: dict | None = None
    total_turnaround_days: int | None = None
    notes: str | None = None


# ── Lender CRUD ──

@router.get("")
async def list_lenders(
    search: str | None = None,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    lenders = await lender_service.list_lenders(db, search=search)
    return [
        {
            "id": str(l.id),
            "name": l.name,
            "lender_type": l.lender_type,
            "notes": l.notes,
            "created_at": l.created_at.isoformat() if l.created_at else None,
        }
        for l in lenders
    ]


@router.post("")
async def create_lender(
    body: LenderCreate,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    lender = await lender_service.create_lender(db, **body.model_dump())
    return {"id": str(lender.id), "name": lender.name}


@router.get("/{lender_id}")
async def get_lender(
    lender_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    lender = await lender_service.get_lender(db, lender_id)
    if not lender:
        raise HTTPException(status_code=404, detail="Lender not found")
    appetite = await lender_service.get_latest_appetite(db, lender_id)
    appetite_history = await lender_service.get_appetite_history(db, lender_id)
    transactions = await lender_service.get_transactions(db, lender_id)
    return {
        "id": str(lender.id),
        "name": lender.name,
        "lender_type": lender.lender_type,
        "general_preferences": lender.general_preferences,
        "credit_committee_notes": lender.credit_committee_notes,
        "relationship_contacts": lender.relationship_contacts,
        "notes": lender.notes,
        "current_appetite": {
            "appetite_signal": appetite.appetite_signal,
            "property_types": appetite.property_types,
            "geographies": appetite.geographies,
            "deal_size_min": appetite.deal_size_min,
            "deal_size_max": appetite.deal_size_max,
            "ltc_max": appetite.ltc_max,
            "rate_indication": appetite.rate_indication,
            "is_stale": appetite.is_stale,
            "recorded_at": appetite.recorded_at.isoformat() if appetite.recorded_at else None,
        } if appetite else None,
        "appetite_history": [
            {
                "appetite_signal": a.appetite_signal,
                "source_detail": a.source_detail,
                "recorded_at": a.recorded_at.isoformat() if a.recorded_at else None,
                "is_stale": a.is_stale,
            }
            for a in appetite_history[:20]
        ],
        "transactions": [
            {
                "id": str(t.id),
                "property_type": t.property_type,
                "geography": t.geography,
                "deal_size": t.deal_size,
                "outcome": t.outcome,
                "recorded_at": t.recorded_at.isoformat() if t.recorded_at else None,
            }
            for t in transactions[:20]
        ],
    }


@router.put("/{lender_id}")
async def update_lender(
    lender_id: uuid.UUID,
    body: LenderUpdate,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    updates = body.model_dump(exclude_none=True)
    lender = await lender_service.update_lender(db, lender_id, **updates)
    if not lender:
        raise HTTPException(status_code=404, detail="Lender not found")
    return {"id": str(lender.id), "name": lender.name}


# ── Appetite ──

@router.post("/{lender_id}/appetite")
async def log_appetite(
    lender_id: uuid.UUID,
    body: AppetiteLog,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    appetite = await lender_service.log_appetite(
        db, lender_id=lender_id, recorded_by=user.id, **body.model_dump(),
    )
    return {"id": str(appetite.id), "appetite_signal": appetite.appetite_signal}


# ── Transactions ──

@router.post("/{lender_id}/transactions")
async def log_transaction(
    lender_id: uuid.UUID,
    body: TransactionLog,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    data = body.model_dump(exclude_none=True)
    if "deal_id" in data:
        data["deal_id"] = uuid.UUID(data["deal_id"])
    txn = await lender_service.log_transaction(db, lender_id=lender_id, **data)
    return {"id": str(txn.id)}


# ── Lender Matching ──

match_router = APIRouter(tags=["lender-matching"])


@match_router.get("/deals/{deal_id}/lender-match")
async def match_lenders(
    deal_id: uuid.UUID,
    property_type: str | None = None,
    geography: str | None = None,
    deal_size: float | None = None,
    ltc_requested: float | None = None,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    return await lender_service.match_lenders_for_deal(
        db, property_type=property_type, geography=geography,
        deal_size=deal_size, ltc_requested=ltc_requested,
    )


# ── Deal Outcomes ──

outcomes_router = APIRouter(tags=["deal-outcomes"])


@outcomes_router.post("/deals/{deal_id}/distribute")
async def distribute_deal(
    deal_id: uuid.UUID,
    body: DistributeRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    dist = await deal_outcome_service.distribute_to_lender(
        db, deal_id=deal_id, lender_id=uuid.UUID(body.lender_id),
        distributed_by=user.id, approach_angle=body.approach_angle,
    )
    return {"id": str(dist.id)}


@outcomes_router.get("/deals/{deal_id}/distributions")
async def get_distributions(
    deal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    return await deal_outcome_service.get_responses(db, deal_id)


@outcomes_router.post("/deals/{deal_id}/responses")
async def record_response(
    deal_id: uuid.UUID,
    body: ResponseRecord,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    resp = await deal_outcome_service.record_response(
        db, deal_distribution_id=uuid.UUID(body.deal_distribution_id),
        response_type=body.response_type, terms_offered=body.terms_offered,
        pass_reason=body.pass_reason, notes=body.notes,
    )
    return {"id": str(resp.id)}


@outcomes_router.post("/deals/{deal_id}/close")
async def close_deal(
    deal_id: uuid.UUID,
    body: ClosingRecord,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    closing = await deal_outcome_service.record_closing(
        db, deal_id=deal_id, winning_lender_id=uuid.UUID(body.winning_lender_id),
        final_terms=body.final_terms, total_turnaround_days=body.total_turnaround_days,
        notes=body.notes,
    )
    return {"id": str(closing.id)}
