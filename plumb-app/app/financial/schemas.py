"""Pydantic v2 schemas for the financial model output.

These are the data shapes consumed by the Excel builder and OM templates.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Editable assumptions
# ---------------------------------------------------------------------------

class ModelAssumptions(BaseModel):
    """User-editable underwriting assumptions."""

    cap_rate: float = 0.045
    vacancy_fm: float = 0.05
    vacancy_affordable: float = 0.025
    vacancy_retail: float = 0.07
    mgmt_fee_pct: float = 0.025
    assessment_growth: float = 0.02
    tax_rate_growth: float = 0.005
    discount_rate: float = 0.05


# ---------------------------------------------------------------------------
# Provenance helpers
# ---------------------------------------------------------------------------

class ResolvedField(BaseModel):
    """A single extracted value after resolution (override vs best-confidence)."""

    field_name: str
    value: Any
    source_doc_id: str | None = None
    source_page: int | None = None
    source_text_snippet: str | None = None
    confidence_score: float | None = None
    was_overridden: bool = False


class CalculatedValue(BaseModel):
    """Provenance wrapper — records how a metric was derived."""

    result: Any
    formula: str
    inputs: dict


# ---------------------------------------------------------------------------
# Sources & Uses
# ---------------------------------------------------------------------------

class SourcesUsesLine(BaseModel):
    label: str
    total: float
    pct_total: float
    per_zfa: float | None = None
    per_gsf: float | None = None
    per_nra: float | None = None
    prior_to_closing: float = 0.0
    at_closing: float = 0.0
    future_funding: float = 0.0


class SourcesUses(BaseModel):
    sources: list[SourcesUsesLine]
    uses: list[SourcesUsesLine]
    total_sources: SourcesUsesLine
    total_uses: SourcesUsesLine


# ---------------------------------------------------------------------------
# Construction budget
# ---------------------------------------------------------------------------

class BudgetLineItem(BaseModel):
    category: str  # acquisition / hard / soft / financing / interest
    label: str
    total_cost: float
    pct_total: float
    per_zfa: float | None = None
    per_gsf: float | None = None
    per_nsf: float | None = None
    spent_to_date: float = 0.0
    at_closing: float = 0.0
    future_funding: float = 0.0
    rate_pct: float | None = None  # e.g. mortgage recording tax 2.80%


# ---------------------------------------------------------------------------
# Unit mix
# ---------------------------------------------------------------------------

class UnitMixRow(BaseModel):
    tier: str  # FM / 421A / MIH / Commercial
    beds: int | None = None
    baths: int | None = None
    units: int = 0
    sf_per_unit: float = 0.0
    avg_monthly_rent: float = 0.0
    rent_per_sf: float = 0.0


class UnitMixTiered(BaseModel):
    fm: list[UnitMixRow] = Field(default_factory=list)
    affordable_421a: list[UnitMixRow] = Field(default_factory=list)
    mih: list[UnitMixRow] = Field(default_factory=list)
    commercial: list[UnitMixRow] = Field(default_factory=list)
    total: list[UnitMixRow] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Pro forma
# ---------------------------------------------------------------------------

class ProFormaLine(BaseModel):
    label: str
    per_sf: float | None = None
    per_unit_yr: float | None = None
    pct_of_egi: float | None = None
    total: float = 0.0
    is_subtotal: bool = False


class RentalProForma(BaseModel):
    income_lines: list[ProFormaLine]
    egi: ProFormaLine
    expense_lines: list[ProFormaLine]
    total_expenses: ProFormaLine
    noi: ProFormaLine


# ---------------------------------------------------------------------------
# Valuation
# ---------------------------------------------------------------------------

class ValuationSummary(BaseModel):
    actual_noi: float
    yield_on_cost: float
    full_tax_noi: float
    cap_rate: float
    estimated_value_a: float
    abatement_value_b: float
    total_asset_value: float
    value_per_unit: float
    value_per_gsf: float
    total_project_cap: float
    construction_loan: float
    stabilized_ltv: float
    debt_yield: float
    debt_per_unit: float
    debt_per_gsf: float


# ---------------------------------------------------------------------------
# 421(a) abatement
# ---------------------------------------------------------------------------

class AbatementYear(BaseModel):
    year: int
    benefit_year_start: str
    taxable_assessment: float
    av_prior: float
    increase_in_av: float
    pct_exempt: float
    exemption_amount: float
    final_taxable_assessment: float
    tax_rate: float
    unabated_ret: float
    abated_ret: float
    ret_savings: float


class AbatementSchedule(BaseModel):
    program_option: str
    borough: str
    block_lot: str
    av_prior_to_construction: float
    assessment_growth_rate: float
    tax_rate_growth: float
    discount_rate: float
    npv_of_tax_savings: float
    years: list[AbatementYear]


# ---------------------------------------------------------------------------
# Condo sellout
# ---------------------------------------------------------------------------

class CondoSelloutSummary(BaseModel):
    """Metrics specific to condo sellout / for-sale development deals."""

    projected_sellout: float = 0.0
    total_development_cost: float = 0.0
    profit: float = 0.0
    profit_margin_on_cost: float = 0.0  # (sellout - TDC) / TDC
    per_unit_sellout: float = 0.0
    per_unit_cost: float = 0.0
    per_sf_sellout: float = 0.0
    per_sf_cost: float = 0.0
    return_on_equity: float = 0.0  # profit / equity
    loan_amount: float = 0.0
    ltc: float = 0.0
    equity: float = 0.0
    appraised_value: float = 0.0
    ltv: float = 0.0  # loan / appraised_value
    total_units: int = 0
    total_gsf: float = 0.0


# ---------------------------------------------------------------------------
# Sensitivity
# ---------------------------------------------------------------------------

class SensitivityCell(BaseModel):
    asset_value: float
    ltv: float
    debt_yield: float


class SensitivityMatrix(BaseModel):
    cap_rates: list[float]
    rent_growth_rates: list[float]
    cells: list[list[SensitivityCell]]
    base_row: int
    base_col: int


# ---------------------------------------------------------------------------
# Top-level financial model
# ---------------------------------------------------------------------------

class FinancialModel(BaseModel):
    model_config = ConfigDict(ser_json_timedelta="iso8601")

    deal_id: str
    assumptions: ModelAssumptions
    sources_uses: SourcesUses
    budget_detail: list[BudgetLineItem]
    unit_mix: UnitMixTiered
    proforma: RentalProForma
    valuation: ValuationSummary
    abatement: AbatementSchedule | None = None
    condo_sellout: CondoSelloutSummary | None = None
    sensitivity: SensitivityMatrix
    ltc: float
    total_development_cost: float
    loan_amount: float
    equity: float
    total_units: int
    total_gsf: float
    zfa: float | None = None
    nra: float
    provenance: dict[str, CalculatedValue] = Field(default_factory=dict)
    calculated_at: str  # ISO timestamp
    errors: list[str] = Field(default_factory=list)
