"""Main orchestrator — builds the complete FinancialModel from extracted values.

Entry point: ``build_financial_model(deal_id, db, assumptions)``
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.financial.abatement import calculate_abatement
from app.financial.construction_loan import build_budget_detail, calculate_sources_uses
from app.financial.inputs import get_float, get_list, get_str, resolve_inputs
from app.financial.proforma import calculate_proforma
from app.financial.schemas import (
    CalculatedValue,
    CondoSelloutSummary,
    FinancialModel,
    ModelAssumptions,
    ResolvedField,
    UnitMixRow,
    UnitMixTiered,
)
from app.financial.sensitivity import build_sensitivity_matrix
from app.financial.valuation import calculate_valuation

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Unit mix parser
# ---------------------------------------------------------------------------

_TIER_ALIASES = {
    "fm": "FM",
    "free market": "FM",
    "free-market": "FM",
    "market": "FM",
    "market rate": "FM",
    "market-rate": "FM",
    "421a": "421A",
    "421-a": "421A",
    "affordable": "421A",
    "affordable 421a": "421A",
    "affordable_421a": "421A",
    "mih": "MIH",
    "inclusionary": "MIH",
    "mandatory inclusionary": "MIH",
    "commercial": "Commercial",
    "retail": "Commercial",
}


def _normalize_tier(raw: str | None) -> str:
    """Map a raw tier string to one of FM / 421A / MIH / Commercial."""
    if raw is None:
        return "FM"
    return _TIER_ALIASES.get(raw.lower().strip(), "FM")


def parse_unit_mix(
    raw_mix: list,
    inputs: dict[str, ResolvedField],
) -> UnitMixTiered:
    """Parse extracted unit-mix data into tiered rows.

    ``raw_mix`` should be a list of dicts with keys like:
        tier, beds, baths, units, sf_per_unit, avg_monthly_rent, rent_per_sf
    """
    buckets: dict[str, list[UnitMixRow]] = {
        "FM": [],
        "421A": [],
        "MIH": [],
        "Commercial": [],
    }

    for entry in raw_mix:
        if not isinstance(entry, dict):
            continue

        tier = _normalize_tier(
            entry.get("tier") or entry.get("type") or entry.get("program")
        )

        beds_raw = entry.get("beds") or entry.get("bedrooms") or entry.get("br")
        beds = int(beds_raw) if beds_raw is not None else None

        # Infer bed count from type name if not explicitly provided
        if beds is None:
            type_str = (entry.get("type") or entry.get("tier") or "").lower().strip()
            if "studio" in type_str or type_str == "0br":
                beds = 0
            elif type_str.startswith("1") or "1 bed" in type_str or "1 br" in type_str or "1-bed" in type_str or type_str == "1br":
                beds = 1
            elif type_str.startswith("2") or "2 bed" in type_str or "2 br" in type_str or "2-bed" in type_str or type_str == "2br":
                beds = 2
            elif type_str.startswith("3") or "3 bed" in type_str or "3 br" in type_str or "3-bed" in type_str or type_str == "3br":
                beds = 3
            elif type_str.startswith("4") or "4 bed" in type_str:
                beds = 4

        baths_raw = entry.get("baths") or entry.get("bathrooms")
        baths = int(baths_raw) if baths_raw is not None else None

        units = int(entry.get("units") or entry.get("count") or 0)
        sf = float(entry.get("sf_per_unit") or entry.get("sf") or entry.get("area") or 0)
        rent = float(entry.get("avg_monthly_rent") or entry.get("rent") or entry.get("monthly_rent") or 0)
        rent_psf = float(entry.get("rent_per_sf") or entry.get("rent_psf") or 0)

        if rent_psf == 0 and sf > 0 and rent > 0:
            rent_psf = rent / sf

        buckets.setdefault(tier, []).append(UnitMixRow(
            tier=tier,
            beds=beds,
            baths=baths,
            units=units,
            sf_per_unit=sf,
            avg_monthly_rent=rent,
            rent_per_sf=rent_psf,
        ))

    # Add commercial tier from separate fields if not already present
    if not buckets["Commercial"]:
        commercial_sf = get_float(inputs, "commercial_sf", None)
        commercial_rent = get_float(inputs, "commercial_rent_psf", None) or get_float(inputs, "retail_rent_psf", None)
        commercial_units = int(get_float(inputs, "commercial_units", 0) or 0)
        if commercial_sf and commercial_sf > 0 and commercial_units > 0:
            sf_per = commercial_sf / commercial_units
            monthly_rent = (commercial_rent or 0) * sf_per / 12.0 if commercial_rent else 0
            buckets["Commercial"].append(UnitMixRow(
                tier="Commercial",
                beds=None,
                baths=None,
                units=commercial_units,
                sf_per_unit=sf_per,
                avg_monthly_rent=monthly_rent,
                rent_per_sf=commercial_rent or 0,
            ))

    # Build totals
    all_rows = buckets["FM"] + buckets["421A"] + buckets["MIH"] + buckets["Commercial"]

    # Aggregate total row per bed count
    totals_by_beds: dict[int | None, dict[str, Any]] = {}
    for row in all_rows:
        key = row.beds
        agg = totals_by_beds.setdefault(key, {
            "units": 0, "total_sf": 0.0, "total_rent": 0.0,
        })
        agg["units"] += row.units
        agg["total_sf"] += row.sf_per_unit * row.units
        agg["total_rent"] += row.avg_monthly_rent * row.units

    total_rows: list[UnitMixRow] = []
    for beds_key, agg in sorted(totals_by_beds.items(), key=lambda x: (x[0] is None, x[0] or 0)):
        u = agg["units"]
        sf = agg["total_sf"] / u if u else 0
        rent = agg["total_rent"] / u if u else 0
        rpsf = rent / sf if sf else 0
        total_rows.append(UnitMixRow(
            tier="Total",
            beds=beds_key,
            baths=None,
            units=u,
            sf_per_unit=round(sf, 2),
            avg_monthly_rent=round(rent, 2),
            rent_per_sf=round(rpsf, 4),
        ))

    return UnitMixTiered(
        fm=buckets["FM"],
        affordable_421a=buckets["421A"],
        mih=buckets["MIH"],
        commercial=buckets["Commercial"],
        total=total_rows,
    )


# ---------------------------------------------------------------------------
# Provenance builder
# ---------------------------------------------------------------------------

def _prov(result: Any, formula: str, **kwargs: Any) -> CalculatedValue:
    return CalculatedValue(result=result, formula=formula, inputs=kwargs)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def build_financial_model(
    deal_id: UUID,
    db: Session,
    assumptions: ModelAssumptions | None = None,
) -> FinancialModel:
    """Build the complete financial model for a construction loan deal.

    1. Resolve all extracted values.
    2. Determine assumptions from extracted + defaults.
    3. Calculate each component.
    4. Assemble into FinancialModel.
    """
    errors: list[str] = []

    # ── Step 1: Resolve inputs ──
    inputs, resolve_warnings = resolve_inputs(deal_id, db)
    errors.extend(resolve_warnings)

    # ── Step 2: Assumptions ──
    if assumptions is None:
        assumptions = ModelAssumptions()

    # Override defaults with extracted values when available
    extracted_cap = get_float(inputs, "cap_rate", None)
    if extracted_cap is not None and 0 < extracted_cap < 1:
        assumptions.cap_rate = extracted_cap
    elif extracted_cap is not None and extracted_cap > 1:
        # Likely a percentage like 4.5 → 0.045
        assumptions.cap_rate = extracted_cap / 100.0

    extracted_vacancy = get_float(inputs, "vacancy_rate", None) or get_float(inputs, "vacancy_fm", None)
    if extracted_vacancy is not None:
        if extracted_vacancy > 1:
            extracted_vacancy /= 100.0
        assumptions.vacancy_fm = extracted_vacancy

    # ── Step 3: Area denominators ──
    gsf = get_float(inputs, "gross_sf", 0.0) or get_float(inputs, "gsf", 0.0) or get_float(inputs, "total_sf", 0.0) or 0.0
    zfa = get_float(inputs, "zfa", None) or get_float(inputs, "zoning_floor_area", None)
    nra = get_float(inputs, "nra", 0.0) or get_float(inputs, "net_rentable_area", 0.0) or 0.0
    residential_sf = get_float(inputs, "residential_sf", 0.0) or 0.0
    commercial_sf = get_float(inputs, "commercial_sf", 0.0) or 0.0

    # If GSF not directly extracted, try sum of components
    if gsf == 0.0:
        gsf = residential_sf + commercial_sf
    # If NRA is zero, fall back to GSF
    if nra == 0.0:
        nra = gsf
    # NSF for budget detail (net sellable/rentable)
    nsf = nra if nra > 0 else gsf

    # ── Step 4: Unit mix ──
    raw_unit_mix = get_list(inputs, "unit_mix")
    if not raw_unit_mix:
        raw_unit_mix = get_list(inputs, "unit_mix_detail")
    unit_mix = parse_unit_mix(raw_unit_mix, inputs)

    total_units_residential = sum(
        r.units for r in unit_mix.fm + unit_mix.affordable_421a + unit_mix.mih
    )
    total_units_commercial = sum(r.units for r in unit_mix.commercial)
    total_units_from_mix = total_units_residential + total_units_commercial

    # Raw extracted total_units — now resolved via doc-type priority (see
    # app.financial.inputs.FIELD_SOURCE_PRIORITY), so this reflects the
    # authoritative project_summary_deck / appraisal value.
    total_units_from_field = int(get_float(inputs, "total_units", 0) or 0)
    if total_units_from_field == 0:
        total_units_from_field = int(get_float(inputs, "units", 0) or 0)

    # Reconciliation: prefer the larger of the two when they disagree by more
    # than 10%.  This guards against unit_mix parsing missing rows (e.g. only
    # FM tier parsed while 421A/MIH tiers are dropped) which would silently
    # under-count units and cascade into bad per-unit metrics.
    if total_units_from_mix > 0 and total_units_from_field > 0:
        diff = abs(total_units_from_mix - total_units_from_field)
        if diff / max(total_units_from_mix, total_units_from_field) > 0.10:
            winner = max(total_units_from_mix, total_units_from_field)
            errors.append(
                f"Unit count discrepancy: unit_mix sum = {total_units_from_mix}, "
                f"extracted total_units = {total_units_from_field}. "
                f"Using {winner} (larger value) to avoid under-counting."
            )
            logger.warning(
                "Unit count discrepancy for deal %s: unit_mix=%d, total_units=%d, using %d",
                deal_id, total_units_from_mix, total_units_from_field, winner,
            )
            total_units = winner
        else:
            total_units = total_units_from_mix
    elif total_units_from_mix > 0:
        total_units = total_units_from_mix
    else:
        total_units = total_units_from_field

    # Additional sanity check: gsf / total_units should produce a reasonable
    # average unit size (300-3000 sf).  If not, warn — something is wrong with
    # either the unit count or the GSF.
    if total_units > 0 and gsf > 0:
        avg_unit_sf = gsf / total_units
        if avg_unit_sf < 150 or avg_unit_sf > 5000:
            errors.append(
                f"Implausible average unit size: {avg_unit_sf:,.0f} SF/unit "
                f"(gsf={gsf:,.0f}, units={total_units}). "
                f"Check unit count and GSF extraction."
            )

    # ── Step 5: Sources & Uses ──
    sources_uses = calculate_sources_uses(inputs, assumptions, zfa, gsf, nra)

    loan_amount = get_float(inputs, "loan_amount", 0.0) or get_float(inputs, "construction_loan", 0.0) or 0.0
    tdc = sources_uses.total_uses.total
    equity = tdc - loan_amount if loan_amount else tdc
    if equity < 0:
        equity = 0.0

    # ── Step 6: Budget detail ──
    budget_detail = build_budget_detail(inputs, zfa, gsf, nsf)

    # ── Step 7: Abatement (if applicable) ──
    abatement = None
    abated_ret: float | None = None
    abatement_npv: float = 0.0

    av_prior = get_float(inputs, "av_prior", None) or get_float(inputs, "assessed_value_prior", None)
    if av_prior is not None and av_prior > 0:
        program = get_str(inputs, "abatement_program", "C") or "C"
        # Extract just the option letter
        program_letter = program.strip().upper()
        if program_letter not in ("A", "B", "C"):
            # Try to extract from longer strings like "421-a Option C"
            for letter in ("C", "B", "A"):
                if letter.lower() in program.lower() or f"option {letter.lower()}" in program.lower():
                    program_letter = letter
                    break
            else:
                program_letter = "C"

        borough = get_str(inputs, "borough", "") or ""
        block_lot = get_str(inputs, "block_lot", "") or get_str(inputs, "bbl", "") or ""
        base_tax_rate = get_float(inputs, "tax_rate", None)
        benefit_years = int(get_float(inputs, "benefit_years", 35) or 35)

        abatement = calculate_abatement(
            av_prior=av_prior,
            assumptions=assumptions,
            program_option=program_letter,
            benefit_years=benefit_years,
            borough=borough,
            block_lot=block_lot,
            base_tax_rate=base_tax_rate,
        )
        abatement_npv = abatement.npv_of_tax_savings

        # First year's abated RET for the proforma
        if abatement.years:
            abated_ret = abatement.years[0].abated_ret
    else:
        errors.append(
            "No assessed value prior to construction found — 421(a) abatement schedule skipped."
        )

    # ── Step 8: Pro forma ──
    proforma_sf = gsf if gsf > 0 else 1.0  # avoid division by zero
    proforma_units = total_units if total_units > 0 else 1

    proforma = calculate_proforma(
        unit_mix=unit_mix,
        inputs=inputs,
        assumptions=assumptions,
        total_sf=proforma_sf,
        total_units=proforma_units,
        abated_ret=abated_ret,
    )

    noi = proforma.noi.total

    # ── Step 9: Valuation ──
    valuation = calculate_valuation(
        noi=noi,
        assumptions=assumptions,
        abatement_npv=abatement_npv if abatement_npv else None,
        tdc=tdc,
        loan_amount=loan_amount,
        total_units=proforma_units,
        gsf=gsf if gsf > 0 else 1.0,
        abated_ret=abated_ret,
    )

    # ── Step 9b: Summary metrics (needed by condo sellout) ──
    ltc = loan_amount / tdc if tdc else 0.0

    # ── Step 9c: Condo sellout metrics (for-sale deals) ──
    condo_sellout = None
    projected_sellout = (
        get_float(inputs, "projected_sellout", 0.0)
        or get_float(inputs, "total_sellout", 0.0)
        or get_float(inputs, "gross_sellout", 0.0)
        or 0.0
    )
    appraised_value = (
        get_float(inputs, "appraised_value", 0.0)
        or get_float(inputs, "as_complete_value", 0.0)
        or 0.0
    )
    if projected_sellout > 0:
        condo_profit = projected_sellout - tdc
        condo_margin = condo_profit / tdc if tdc > 0 else 0.0
        condo_roe = condo_profit / equity if equity > 0 else 0.0
        condo_ltv = loan_amount / appraised_value if appraised_value > 0 else 0.0
        condo_sellout = CondoSelloutSummary(
            projected_sellout=projected_sellout,
            total_development_cost=tdc,
            profit=condo_profit,
            profit_margin_on_cost=condo_margin,
            per_unit_sellout=projected_sellout / total_units if total_units > 0 else 0.0,
            per_unit_cost=tdc / total_units if total_units > 0 else 0.0,
            per_sf_sellout=projected_sellout / gsf if gsf > 0 else 0.0,
            per_sf_cost=tdc / gsf if gsf > 0 else 0.0,
            return_on_equity=condo_roe,
            loan_amount=loan_amount,
            ltc=ltc,
            equity=equity,
            appraised_value=appraised_value,
            ltv=condo_ltv,
            total_units=total_units,
            total_gsf=gsf,
        )

    # ── Step 10: Sensitivity matrix ──
    sensitivity = build_sensitivity_matrix(
        base_noi=noi,
        base_cap_rate=assumptions.cap_rate,
        loan_amount=loan_amount,
        tdc=tdc,
        abatement_npv=abatement_npv,
    )

    # ── Step 11: Provenance ──
    provenance: dict[str, CalculatedValue] = {
        "noi": _prov(
            noi,
            "EGI - Total Expenses",
            egi=proforma.egi.total,
            total_expenses=proforma.total_expenses.total,
        ),
        "ltc": _prov(
            ltc,
            "loan_amount / total_development_cost",
            loan_amount=loan_amount,
            total_development_cost=tdc,
        ),
        "yield_on_cost": _prov(
            valuation.yield_on_cost,
            "NOI / TDC",
            noi=noi,
            tdc=tdc,
        ),
        "stabilized_ltv": _prov(
            valuation.stabilized_ltv,
            "loan_amount / total_asset_value",
            loan_amount=loan_amount,
            total_asset_value=valuation.total_asset_value,
        ),
        "debt_yield": _prov(
            valuation.debt_yield,
            "NOI / loan_amount",
            noi=noi,
            loan_amount=loan_amount,
        ),
        "total_asset_value": _prov(
            valuation.total_asset_value,
            "estimated_value_a + abatement_value_b",
            estimated_value_a=valuation.estimated_value_a,
            abatement_value_b=valuation.abatement_value_b,
        ),
        "estimated_value_a": _prov(
            valuation.estimated_value_a,
            "full_tax_noi / cap_rate",
            full_tax_noi=valuation.full_tax_noi,
            cap_rate=assumptions.cap_rate,
        ),
    }

    if abatement_npv:
        provenance["abatement_npv"] = _prov(
            abatement_npv,
            "sum(ret_savings[y] / (1 + discount_rate)^y) for y in 1..35",
            discount_rate=assumptions.discount_rate,
            benefit_years=len(abatement.years) if abatement else 0,
        )

    if condo_sellout is not None:
        provenance["projected_sellout"] = _prov(
            projected_sellout, "extracted from deal documents",
        )
        provenance["profit_margin_on_cost"] = _prov(
            condo_sellout.profit_margin_on_cost, "(projected_sellout - TDC) / TDC",
            projected_sellout=projected_sellout, tdc=tdc,
        )
        provenance["return_on_equity"] = _prov(
            condo_sellout.return_on_equity, "profit / equity",
            profit=condo_sellout.profit, equity=equity,
        )

    return FinancialModel(
        deal_id=str(deal_id),
        assumptions=assumptions,
        sources_uses=sources_uses,
        budget_detail=budget_detail,
        unit_mix=unit_mix,
        proforma=proforma,
        valuation=valuation,
        abatement=abatement,
        condo_sellout=condo_sellout,
        sensitivity=sensitivity,
        ltc=ltc,
        total_development_cost=tdc,
        loan_amount=loan_amount,
        equity=equity,
        total_units=total_units,
        total_gsf=gsf,
        zfa=zfa,
        nra=nra,
        provenance=provenance,
        calculated_at=datetime.now(timezone.utc).isoformat(),
        errors=errors,
    )
