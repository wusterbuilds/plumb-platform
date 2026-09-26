"""Valuation calculations — asset value, LTV, debt yield, per-unit metrics."""

from __future__ import annotations

from app.financial.schemas import ModelAssumptions, ValuationSummary


def calculate_valuation(
    noi: float,
    assumptions: ModelAssumptions,
    abatement_npv: float | None,
    tdc: float,
    loan_amount: float,
    total_units: int,
    gsf: float,
    abated_ret: float | None = None,
) -> ValuationSummary:
    """Compute stabilized valuation metrics.

    Parameters
    ----------
    noi : float
        Net operating income from the pro forma (reflects abated taxes if applicable).
    assumptions : ModelAssumptions
        Cap rate and other assumptions.
    abatement_npv : float | None
        NPV of 421(a) tax savings (Component B of total asset value).
    tdc : float
        Total development cost.
    loan_amount : float
        Construction loan amount.
    total_units : int
        Total number of units (residential + commercial).
    gsf : float
        Gross square footage.
    abated_ret : float | None
        Year-1 abated real estate taxes (for computing full-tax NOI).
    """
    cap_rate = assumptions.cap_rate

    # Actual NOI (with abated taxes)
    actual_noi = noi

    # Yield on cost
    yield_on_cost = actual_noi / tdc if tdc else 0.0

    # Full-tax NOI = NOI adjusted as if paying full (unabated) taxes
    # If abated_ret is provided, the proforma NOI already reflects the lower tax.
    # full_tax_noi restores the unabated tax burden.
    full_tax_noi = actual_noi  # Default: same as actual
    # (In a future refinement we could subtract the savings that were added back.)

    # Component A: Direct cap value on full-tax NOI
    estimated_value_a = full_tax_noi / cap_rate if cap_rate else 0.0

    # Component B: NPV of 421(a) tax savings
    abatement_value_b = abatement_npv if abatement_npv else 0.0

    # Total asset value
    total_asset_value = estimated_value_a + abatement_value_b

    # Per-unit and per-GSF
    value_per_unit = total_asset_value / total_units if total_units else 0.0
    value_per_gsf = total_asset_value / gsf if gsf else 0.0

    # Leverage metrics
    stabilized_ltv = loan_amount / total_asset_value if total_asset_value else 0.0
    debt_yield = actual_noi / loan_amount if loan_amount else 0.0
    debt_per_unit = loan_amount / total_units if total_units else 0.0
    debt_per_gsf = loan_amount / gsf if gsf else 0.0

    return ValuationSummary(
        actual_noi=actual_noi,
        yield_on_cost=yield_on_cost,
        full_tax_noi=full_tax_noi,
        cap_rate=cap_rate,
        estimated_value_a=estimated_value_a,
        abatement_value_b=abatement_value_b,
        total_asset_value=total_asset_value,
        value_per_unit=value_per_unit,
        value_per_gsf=value_per_gsf,
        total_project_cap=tdc,
        construction_loan=loan_amount,
        stabilized_ltv=stabilized_ltv,
        debt_yield=debt_yield,
        debt_per_unit=debt_per_unit,
        debt_per_gsf=debt_per_gsf,
    )
