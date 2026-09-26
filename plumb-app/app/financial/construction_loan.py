"""Sources & Uses and Construction Budget calculations."""

from __future__ import annotations

import logging

from app.financial.inputs import get_float, get_list, get_str
from app.financial.schemas import (
    BudgetLineItem,
    ModelAssumptions,
    ResolvedField,
    SourcesUses,
    SourcesUsesLine,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _pct(part: float, whole: float) -> float:
    return part / whole if whole else 0.0


def _per(total: float, denom: float | None) -> float | None:
    if denom is None or denom == 0:
        return None
    return total / denom


def _make_line(
    label: str,
    total: float,
    tdc: float,
    zfa: float | None,
    gsf: float,
    nra: float,
    prior_to_closing: float = 0.0,
    at_closing: float = 0.0,
    future_funding: float = 0.0,
) -> SourcesUsesLine:
    return SourcesUsesLine(
        label=label,
        total=total,
        pct_total=_pct(total, tdc),
        per_zfa=_per(total, zfa),
        per_gsf=_per(total, gsf),
        per_nra=_per(total, nra),
        prior_to_closing=prior_to_closing,
        at_closing=at_closing,
        future_funding=future_funding,
    )


# ---------------------------------------------------------------------------
# Sources & Uses
# ---------------------------------------------------------------------------

def calculate_sources_uses(
    inputs: dict[str, ResolvedField],
    assumptions: ModelAssumptions,
    zfa: float | None,
    gsf: float,
    nra: float,
) -> SourcesUses:
    """Build the Sources & Uses summary.

    Sources = Construction Loan + Sponsor Equity = TDC
    Uses    = Acquisition + Hard Costs + Soft Costs + Financing + Interest = TDC
    """
    # --- Uses ---
    acquisition = get_float(inputs, "acquisition_cost", 0.0) or get_float(inputs, "purchase_price", 0.0) or 0.0
    hard_costs = get_float(inputs, "hard_costs", 0.0) or 0.0
    soft_costs = get_float(inputs, "soft_costs", 0.0) or 0.0
    financing_costs = get_float(inputs, "financing_costs", 0.0) or 0.0
    interest_reserve = get_float(inputs, "interest_reserve", 0.0) or 0.0

    tdc = get_float(inputs, "total_development_cost", 0.0) or 0.0
    if tdc == 0.0:
        tdc = acquisition + hard_costs + soft_costs + financing_costs + interest_reserve

    use_lines = [
        _make_line("Acquisition", acquisition, tdc, zfa, gsf, nra,
                    prior_to_closing=acquisition),
        _make_line("Hard Costs", hard_costs, tdc, zfa, gsf, nra,
                    future_funding=hard_costs),
        _make_line("Soft Costs", soft_costs, tdc, zfa, gsf, nra,
                    future_funding=soft_costs),
        _make_line("Financing Costs", financing_costs, tdc, zfa, gsf, nra,
                    at_closing=financing_costs),
        _make_line("Interest Reserve", interest_reserve, tdc, zfa, gsf, nra,
                    future_funding=interest_reserve),
    ]

    total_uses = _make_line(
        "Total Uses", tdc, tdc, zfa, gsf, nra,
        prior_to_closing=sum(u.prior_to_closing for u in use_lines),
        at_closing=sum(u.at_closing for u in use_lines),
        future_funding=sum(u.future_funding for u in use_lines),
    )

    # --- Sources ---
    loan_amount = get_float(inputs, "loan_amount", 0.0) or get_float(inputs, "construction_loan", 0.0) or 0.0
    equity = tdc - loan_amount if loan_amount else tdc
    if equity < 0:
        equity = 0.0

    source_lines = [
        _make_line("Construction Loan", loan_amount, tdc, zfa, gsf, nra,
                    future_funding=loan_amount),
        _make_line("Sponsor Equity", equity, tdc, zfa, gsf, nra,
                    prior_to_closing=acquisition,
                    at_closing=financing_costs,
                    future_funding=max(0.0, equity - acquisition - financing_costs)),
    ]

    total_sources = _make_line(
        "Total Sources", tdc, tdc, zfa, gsf, nra,
        prior_to_closing=sum(s.prior_to_closing for s in source_lines),
        at_closing=sum(s.at_closing for s in source_lines),
        future_funding=sum(s.future_funding for s in source_lines),
    )

    return SourcesUses(
        sources=source_lines,
        uses=use_lines,
        total_sources=total_sources,
        total_uses=total_uses,
    )


# ---------------------------------------------------------------------------
# Budget detail
# ---------------------------------------------------------------------------

_CATEGORY_MAP = {
    "acquisition": "acquisition",
    "land": "acquisition",
    "hard": "hard",
    "construction": "hard",
    "soft": "soft",
    "professional": "soft",
    "financing": "financing",
    "closing": "financing",
    "interest": "interest",
    "carry": "interest",
}


def _classify_category(raw: str) -> str:
    """Map a raw category string to one of the canonical budget categories."""
    lower = raw.lower().strip()
    for keyword, cat in _CATEGORY_MAP.items():
        if keyword in lower:
            return cat
    return "soft"  # default


def _timing_for_category(category: str, total: float) -> tuple[float, float, float]:
    """Return (spent_to_date, at_closing, future_funding) based on category."""
    if category == "acquisition":
        return (total, 0.0, 0.0)
    if category == "financing":
        return (0.0, total, 0.0)
    # hard, soft, interest → future
    return (0.0, 0.0, total)


def build_budget_detail(
    inputs: dict[str, ResolvedField],
    zfa: float | None,
    gsf: float,
    nsf: float,
) -> list[BudgetLineItem]:
    """Build detailed budget line items from extracted inputs.

    If the extraction includes a structured `construction_budget_detail` or
    `sources_and_uses` list, parse it.  Otherwise create category-level lines
    from high-level cost fields.
    """
    items: list[BudgetLineItem] = []

    # Try structured data first
    raw_detail = get_list(inputs, "construction_budget_detail")
    if not raw_detail:
        raw_detail = get_list(inputs, "sources_and_uses")
    if not raw_detail:
        raw_detail = get_list(inputs, "budget_detail")

    # Compute TDC for percentages
    tdc = get_float(inputs, "total_development_cost", 0.0) or 0.0

    if raw_detail:
        for entry in raw_detail:
            if not isinstance(entry, dict):
                continue
            label = entry.get("label", entry.get("name", entry.get("item", "Unknown")))
            total_cost = float(entry.get("total_cost", entry.get("amount", entry.get("total", 0))))
            category = _classify_category(entry.get("category", label))
            rate_pct = entry.get("rate_pct") or entry.get("rate")
            if rate_pct is not None:
                rate_pct = float(rate_pct)
            spent, closing, future = _timing_for_category(category, total_cost)
            items.append(BudgetLineItem(
                category=category,
                label=str(label),
                total_cost=total_cost,
                pct_total=_pct(total_cost, tdc) if tdc else 0.0,
                per_zfa=_per(total_cost, zfa),
                per_gsf=_per(total_cost, gsf),
                per_nsf=_per(total_cost, nsf),
                spent_to_date=spent,
                at_closing=closing,
                future_funding=future,
                rate_pct=rate_pct,
            ))
    else:
        # Fallback: category-level aggregates
        category_fields = [
            ("acquisition", "Acquisition Cost", "acquisition_cost"),
            ("hard", "Hard Costs", "hard_costs"),
            ("soft", "Soft Costs", "soft_costs"),
            ("financing", "Financing Costs", "financing_costs"),
            ("interest", "Interest Reserve", "interest_reserve"),
        ]
        for category, label, field_name in category_fields:
            val = get_float(inputs, field_name, 0.0) or 0.0
            if val == 0.0:
                continue
            spent, closing, future = _timing_for_category(category, val)
            items.append(BudgetLineItem(
                category=category,
                label=label,
                total_cost=val,
                pct_total=_pct(val, tdc) if tdc else 0.0,
                per_zfa=_per(val, zfa),
                per_gsf=_per(val, gsf),
                per_nsf=_per(val, nsf),
                spent_to_date=spent,
                at_closing=closing,
                future_funding=future,
            ))

    # Recalculate TDC if not provided
    if tdc == 0.0 and items:
        tdc = sum(i.total_cost for i in items)
        for item in items:
            item.pct_total = _pct(item.total_cost, tdc)

    return items
