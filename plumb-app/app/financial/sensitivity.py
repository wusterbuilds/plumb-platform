"""Sensitivity matrix — cap rate vs rent growth grid.

Each cell shows asset value, LTV, and debt yield for one (cap_rate, rent_growth) pair.
"""

from __future__ import annotations

from app.financial.schemas import SensitivityCell, SensitivityMatrix


def build_sensitivity_matrix(
    base_noi: float,
    base_cap_rate: float,
    loan_amount: float,
    tdc: float,
    abatement_npv: float,
    rent_growth_steps: int = 7,
    cap_rate_steps: int = 7,
) -> SensitivityMatrix:
    """Build a cap-rate x rent-growth sensitivity grid.

    Parameters
    ----------
    base_noi : float
        Stabilized NOI from the pro forma.
    base_cap_rate : float
        Base-case cap rate.
    loan_amount : float
        Construction loan amount (for LTV calculation).
    tdc : float
        Total development cost.
    abatement_npv : float
        NPV of 421(a) tax savings (Component B).
    rent_growth_steps : int
        Number of rent-growth columns (default 7).
    cap_rate_steps : int
        Number of cap-rate rows (default 7).
    """

    # Cap rate range: base +/- 75bps in 25bp increments (7 rows)
    half_cap = (cap_rate_steps - 1) // 2  # 3 steps each side
    cap_rates = [
        round(base_cap_rate + (i - half_cap) * 0.0025, 5)
        for i in range(cap_rate_steps)
    ]
    # Ensure no negative or zero cap rates
    cap_rates = [max(c, 0.005) for c in cap_rates]
    base_row = half_cap

    # Rent growth range: -1.5% to +1.5% in 0.5% steps (7 columns)
    half_rent = (rent_growth_steps - 1) // 2  # 3 steps each side
    rent_growth_rates = [
        round((i - half_rent) * 0.005, 5)
        for i in range(rent_growth_steps)
    ]
    base_col = half_rent

    cells: list[list[SensitivityCell]] = []

    for cap in cap_rates:
        row: list[SensitivityCell] = []
        for rg in rent_growth_rates:
            adjusted_noi = base_noi * (1 + rg)
            asset_value = (adjusted_noi / cap) + abatement_npv if cap else 0.0
            ltv = loan_amount / asset_value if asset_value else 0.0
            debt_yield = adjusted_noi / loan_amount if loan_amount else 0.0

            row.append(SensitivityCell(
                asset_value=round(asset_value, 2),
                ltv=round(ltv, 6),
                debt_yield=round(debt_yield, 6),
            ))
        cells.append(row)

    return SensitivityMatrix(
        cap_rates=cap_rates,
        rent_growth_rates=rent_growth_rates,
        cells=cells,
        base_row=base_row,
        base_col=base_col,
    )
