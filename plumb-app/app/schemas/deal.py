import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.enums import CapitalAsk, DealStatus, DealSubtype, DealType, PropertyType


# --- Typed extensions (deal-type-specific fields) ---


class ConstructionLoanExtension(BaseModel):
    total_development_cost: float | None = None
    land_cost: float | None = None
    hard_costs: float | None = None
    soft_costs: float | None = None
    financing_costs: float | None = None
    equity_contribution: float | None = None
    loan_amount_requested: float | None = None
    ltc_requested: float | None = None
    ltc_calculated: float | None = None
    draw_schedule: list[dict] | None = None
    completion_date: str | None = None
    projected_sellout: float | None = None
    projected_sellout_per_sf: float | None = None
    profit_margin_on_cost: float | None = None
    unit_mix: list[dict] | None = None


class StabilizedDebtExtension(BaseModel):
    gross_potential_rent: float | None = None
    vacancy_rate: float | None = None
    effective_gross_income: float | None = None
    operating_expenses: dict | None = None
    noi: float | None = None
    dscr: float | None = None
    ltv: float | None = None
    cap_rate: float | None = None
    debt_yield: float | None = None
    loan_amount: float | None = None
    interest_rate_assumption: float | None = None
    amortization: int | None = None
    loan_term: int | None = None
    unit_mix: list[dict] | None = None
    tenant_schedule: list[dict] | None = None


class ValueAddExtension(BaseModel):
    current_noi: float | None = None
    stabilized_noi: float | None = None
    noi_delta: float | None = None
    renovation_budget: float | None = None
    renovation_timeline: str | None = None
    lease_up_assumptions: dict | None = None
    current_occupancy: float | None = None
    stabilized_occupancy: float | None = None
    current_dscr: float | None = None
    stabilized_dscr: float | None = None
    exit_cap_rate: float | None = None


# --- Request schemas ---


class DealCreate(BaseModel):
    deal_type: DealType
    deal_subtype: DealSubtype | None = None
    capital_ask: CapitalAsk | None = None
    property_name: str | None = None
    property_address: str | None = None
    property_type: PropertyType | None = None
    typed_extension: dict | None = None


class DealUpdate(BaseModel):
    deal_subtype: DealSubtype | None = None
    capital_ask: CapitalAsk | None = None
    property_name: str | None = None
    property_address: str | None = None
    property_type: PropertyType | None = None
    sponsor: dict | None = None
    regulatory: dict | None = None
    typed_extension: dict | None = None
    version: int = Field(..., description="Current version for optimistic concurrency check")


class TransitionRequest(BaseModel):
    target_status: DealStatus
    reason: str | None = None
    dead_reason: str | None = None


# --- Response schemas ---


class DealResponse(BaseModel):
    id: uuid.UUID
    deal_type: DealType
    deal_subtype: DealSubtype | None
    capital_ask: CapitalAsk | None
    status: DealStatus
    revision_number: int
    property_name: str | None
    property_address: str | None
    property_type: PropertyType | None
    sponsor: Any | None
    regulatory: Any | None
    typed_extension: Any | None
    market_context: Any | None = None
    created_at: datetime
    updated_at: datetime
    version: int
    created_by: uuid.UUID

    model_config = {"from_attributes": True}


class DealListResponse(BaseModel):
    deals: list[DealResponse]
    total: int
