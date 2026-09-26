"""Rental pro forma calculation.

Income by tier (FM, 421-A, MIH, Commercial) minus expenses = NOI.
"""

from __future__ import annotations

import logging

from app.financial.inputs import get_float, ResolvedField
from app.financial.schemas import (
    ModelAssumptions,
    ProFormaLine,
    RentalProForma,
    UnitMixRow,
    UnitMixTiered,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _tier_gross(rows: list[UnitMixRow]) -> float:
    """Annual gross income for a tier = sum(units * avg_monthly_rent * 12)."""
    return sum(r.units * r.avg_monthly_rent * 12.0 for r in rows)


def _line(
    label: str,
    total: float,
    total_sf: float,
    total_units: int,
    egi: float,
    is_subtotal: bool = False,
) -> ProFormaLine:
    return ProFormaLine(
        label=label,
        per_sf=total / total_sf if total_sf else None,
        per_unit_yr=total / total_units if total_units else None,
        pct_of_egi=total / egi if egi else None,
        total=total,
        is_subtotal=is_subtotal,
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def calculate_proforma(
    unit_mix: UnitMixTiered,
    inputs: dict[str, ResolvedField],
    assumptions: ModelAssumptions,
    total_sf: float,
    total_units: int,
    abated_ret: float | None = None,
) -> RentalProForma:
    """Build a stabilized rental pro forma.

    Parameters
    ----------
    unit_mix : UnitMixTiered
        Tiered unit mix with per-unit rents.
    inputs : dict
        Resolved extracted values — used for individual expense items.
    assumptions : ModelAssumptions
        Vacancy, management fee, etc.
    total_sf : float
        Total rentable / gross SF for per-SF columns.
    total_units : int
        Total residential + commercial units.
    abated_ret : float | None
        First-year abated real estate tax (from abatement schedule).
        If provided, a "Real Estate Tax Savings" line is added.
    """

    # ===== INCOME =====
    gross_fm = _tier_gross(unit_mix.fm)
    vacancy_fm = -gross_fm * assumptions.vacancy_fm

    gross_421a = _tier_gross(unit_mix.affordable_421a)
    gross_mih = _tier_gross(unit_mix.mih)
    vacancy_affordable = -(gross_421a + gross_mih) * assumptions.vacancy_affordable

    gross_retail = _tier_gross(unit_mix.commercial)
    vacancy_retail = -gross_retail * assumptions.vacancy_retail

    # Other income (parking, laundry, storage, etc.)
    other_income = get_float(inputs, "other_income", 0.0) or 0.0

    egi_total = (
        gross_fm + vacancy_fm
        + gross_421a + gross_mih + vacancy_affordable
        + gross_retail + vacancy_retail
        + other_income
    )

    income_lines: list[ProFormaLine] = []

    # Only include non-zero income tiers
    if gross_fm:
        income_lines.append(_line("Gross Residential Income (FM)", gross_fm, total_sf, total_units, egi_total))
        income_lines.append(_line("Vacancy (FM)", vacancy_fm, total_sf, total_units, egi_total))
    if gross_421a:
        income_lines.append(_line("Gross Residential Income (421-A)", gross_421a, total_sf, total_units, egi_total))
    if gross_mih:
        income_lines.append(_line("Gross Residential Income (MIH)", gross_mih, total_sf, total_units, egi_total))
    if gross_421a or gross_mih:
        income_lines.append(_line("Vacancy (Affordable)", vacancy_affordable, total_sf, total_units, egi_total))
    if gross_retail:
        income_lines.append(_line("Gross Retail Income", gross_retail, total_sf, total_units, egi_total))
        income_lines.append(_line("Vacancy (Retail)", vacancy_retail, total_sf, total_units, egi_total))
    if other_income:
        income_lines.append(_line("Other Income", other_income, total_sf, total_units, egi_total))

    egi_line = _line("Effective Gross Income", egi_total, total_sf, total_units, egi_total, is_subtotal=True)

    # ===== EXPENSES =====
    expense_lines: list[ProFormaLine] = []

    # Try to get individual expense items from extraction
    expense_field_map = [
        ("real_estate_taxes", "Real Estate Taxes"),
        ("insurance", "Insurance"),
        ("repairs_maintenance", "Repairs & Maintenance"),
        ("payroll", "Payroll / Staff"),
        ("utilities", "Utilities"),
        ("elevator", "Elevator"),
        ("legal_professional", "Legal & Professional"),
        ("admin", "Administrative"),
        ("marketing", "Marketing & Advertising"),
        ("reserves", "Replacement Reserves"),
    ]

    has_individual_expenses = False
    expense_total = 0.0

    for field_name, label in expense_field_map:
        val = get_float(inputs, field_name, None)
        if val is not None and val != 0.0:
            has_individual_expenses = True
            expense_lines.append(_line(label, val, total_sf, total_units, egi_total))
            expense_total += val

    if not has_individual_expenses:
        # Fall back to total_expenses from inputs
        extracted_total = get_float(inputs, "total_expenses", None)
        if extracted_total is not None and extracted_total > 0:
            # Subtract management fee if it will be added separately
            mgmt = egi_total * assumptions.mgmt_fee_pct
            if extracted_total > mgmt:
                non_mgmt = extracted_total - mgmt
                expense_lines.append(
                    _line("Operating Expenses", non_mgmt, total_sf, total_units, egi_total)
                )
                expense_total += non_mgmt
            else:
                expense_lines.append(
                    _line("Operating Expenses", extracted_total, total_sf, total_units, egi_total)
                )
                expense_total += extracted_total

    # Management fee (always calculated from EGI)
    mgmt_fee = egi_total * assumptions.mgmt_fee_pct
    expense_lines.append(_line("Management Fee", mgmt_fee, total_sf, total_units, egi_total))
    expense_total += mgmt_fee

    # Real estate tax savings from abatement
    if abated_ret is not None:
        # Find the unabated RET line — if we already have "Real Estate Taxes", the savings
        # is the difference between unabated and abated
        unabated_ret = get_float(inputs, "real_estate_taxes", None)
        if unabated_ret is not None and unabated_ret > 0:
            savings = -(unabated_ret - abated_ret)
            expense_lines.append(
                _line("Real Estate Tax Savings (421-A)", savings, total_sf, total_units, egi_total)
            )
            expense_total += savings
        else:
            # If no unabated line, add the abated tax as the RET line
            expense_lines.append(
                _line("Real Estate Taxes (Abated)", abated_ret, total_sf, total_units, egi_total)
            )
            expense_total += abated_ret

    total_expenses_line = _line(
        "Total Expenses", expense_total, total_sf, total_units, egi_total, is_subtotal=True
    )

    noi_total = egi_total - expense_total
    noi_line = _line("Net Operating Income", noi_total, total_sf, total_units, egi_total, is_subtotal=True)

    return RentalProForma(
        income_lines=income_lines,
        egi=egi_line,
        expense_lines=expense_lines,
        total_expenses=total_expenses_line,
        noi=noi_line,
    )
