"""421(a) tax abatement schedule generator.

Supports Options A, B, and C with configurable benefit periods.
"""

from __future__ import annotations

import logging
from datetime import datetime

from app.financial.schemas import AbatementSchedule, AbatementYear, ModelAssumptions

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exemption schedules by program option
# ---------------------------------------------------------------------------

def _exemption_schedule_a(benefit_years: int) -> list[float]:
    """Option A: 100% exempt for all benefit years."""
    return [1.0] * benefit_years


def _exemption_schedule_b(benefit_years: int) -> list[float]:
    """Option B: 100% for first 25 years, then decline by 2%/yr to 80%."""
    schedule: list[float] = []
    for yr in range(1, benefit_years + 1):
        if yr <= 25:
            schedule.append(1.0)
        else:
            # Years 26-35: decline from 98% to 80%
            decline_year = yr - 25
            pct = max(0.80, 1.0 - 0.02 * decline_year)
            schedule.append(pct)
    return schedule


def _exemption_schedule_c(benefit_years: int) -> list[float]:
    """Option C: 100% for 25 years, then 10% decline per year for years 26-35.

    Year 26=90%, 27=80%, 28=70%, ..., 35=0%.
    """
    schedule: list[float] = []
    for yr in range(1, benefit_years + 1):
        if yr <= 25:
            schedule.append(1.0)
        else:
            decline_year = yr - 25
            pct = max(0.0, 1.0 - 0.10 * decline_year)
            schedule.append(pct)
    return schedule


_SCHEDULE_FN = {
    "A": _exemption_schedule_a,
    "B": _exemption_schedule_b,
    "C": _exemption_schedule_c,
}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def calculate_abatement(
    av_prior: float,
    assumptions: ModelAssumptions,
    program_option: str = "C",
    benefit_years: int = 35,
    borough: str = "",
    block_lot: str = "",
    base_tax_rate: float | None = None,
) -> AbatementSchedule:
    """Generate the year-by-year 421(a) abatement schedule.

    Parameters
    ----------
    av_prior : float
        Assessed value prior to construction.
    assumptions : ModelAssumptions
        Assessment growth rate, tax rate growth, discount rate.
    program_option : str
        "A", "B", or "C".
    benefit_years : int
        Number of benefit years (default 35).
    borough : str
        NYC borough name for header.
    block_lot : str
        Tax lot identifier.
    base_tax_rate : float | None
        Starting tax rate per $100 AV.  Defaults to ~10.694% (NYC Class 2 FY24 rate).
    """
    option_key = program_option.upper().strip()
    schedule_fn = _SCHEDULE_FN.get(option_key, _exemption_schedule_c)
    pct_exempt_list = schedule_fn(benefit_years)

    if base_tax_rate is None:
        base_tax_rate = 0.10694  # NYC Class 2 rate (per $1 AV)

    assessment_growth = assumptions.assessment_growth
    tax_rate_growth = assumptions.tax_rate_growth
    discount_rate = assumptions.discount_rate

    years: list[AbatementYear] = []
    npv_total = 0.0

    current_year = datetime.now().year
    current_taxable_assessment = av_prior
    current_tax_rate = base_tax_rate

    for i in range(benefit_years):
        yr_num = i + 1
        benefit_year_start = str(current_year + i)

        # Grow the taxable assessment and tax rate
        if i > 0:
            current_taxable_assessment *= (1 + assessment_growth)
            current_tax_rate *= (1 + tax_rate_growth)

        # The increase in AV relative to av_prior
        increase_in_av = current_taxable_assessment - av_prior

        # Exemption applies to the increase
        pct_exempt = pct_exempt_list[i]
        exemption_amount = increase_in_av * pct_exempt

        # Final taxable assessment = current - exemption
        final_taxable = current_taxable_assessment - exemption_amount

        # Taxes
        unabated_ret = current_taxable_assessment * current_tax_rate
        abated_ret = final_taxable * current_tax_rate
        ret_savings = unabated_ret - abated_ret

        # NPV
        discount_factor = (1 + discount_rate) ** yr_num
        npv_total += ret_savings / discount_factor

        years.append(AbatementYear(
            year=yr_num,
            benefit_year_start=benefit_year_start,
            taxable_assessment=round(current_taxable_assessment, 2),
            av_prior=round(av_prior, 2),
            increase_in_av=round(increase_in_av, 2),
            pct_exempt=round(pct_exempt, 4),
            exemption_amount=round(exemption_amount, 2),
            final_taxable_assessment=round(final_taxable, 2),
            tax_rate=round(current_tax_rate, 6),
            unabated_ret=round(unabated_ret, 2),
            abated_ret=round(abated_ret, 2),
            ret_savings=round(ret_savings, 2),
        ))

    return AbatementSchedule(
        program_option=option_key,
        borough=borough,
        block_lot=block_lot,
        av_prior_to_construction=av_prior,
        assessment_growth_rate=assessment_growth,
        tax_rate_growth=tax_rate_growth,
        discount_rate=discount_rate,
        npv_of_tax_savings=round(npv_total, 2),
        years=years,
    )
