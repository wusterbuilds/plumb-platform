"""Page registry and manifest builder for OM generation.

Determines which pages to include in the OM and in what order,
then builds the per-page context dicts for Jinja2 rendering.
"""

from __future__ import annotations

import math
from typing import Any

from app.om.schemas import OMContext


# ---------------------------------------------------------------------------
# Formatting helpers (also registered as Jinja2 filters in builder.py)
# ---------------------------------------------------------------------------

def format_currency(value: Any) -> str:
    """Format as whole-dollar currency: $1,234,567"""
    if value is None:
        return ""
    try:
        num = float(value)
    except (TypeError, ValueError):
        return str(value)
    if num < 0:
        return f"-${abs(num):,.0f}"
    return f"${num:,.0f}"


def format_currency_sf(value: Any) -> str:
    """Format as per-SF currency: $12.34"""
    if value is None:
        return ""
    try:
        num = float(value)
    except (TypeError, ValueError):
        return str(value)
    if num < 0:
        return f"-${abs(num):,.2f}"
    return f"${num:,.2f}"


def format_pct(value: Any) -> str:
    """Format decimal as percentage: 0.05 -> 5.00%"""
    if value is None:
        return ""
    try:
        num = float(value)
    except (TypeError, ValueError):
        return str(value)
    return f"{num * 100:.2f}%"


def format_number(value: Any) -> str:
    """Format with thousands separator: 1,234"""
    if value is None:
        return ""
    try:
        num = float(value)
    except (TypeError, ValueError):
        return str(value)
    if num == int(num):
        return f"{int(num):,}"
    return f"{num:,.2f}"


def format_pct_raw(value: Any) -> str:
    """Format already-percentage value: 5.0 -> 5.00%"""
    if value is None:
        return ""
    try:
        num = float(value)
    except (TypeError, ValueError):
        return str(value)
    return f"{num:.2f}%"


# ---------------------------------------------------------------------------
# Shared context builder
# ---------------------------------------------------------------------------

def _base_ctx(ctx: OMContext) -> dict:
    """Fields included in every page context."""
    return {
        "property_name": ctx.property_name,
        "property_address": ctx.property_address,
        "deal_type_label": ctx.deal_type_label,
        # logo_path and styles_path are injected by builder.py at render time
    }


# ---------------------------------------------------------------------------
# Individual page builders
# ---------------------------------------------------------------------------

def _cover(ctx: OMContext) -> dict:
    base = _base_ctx(ctx)
    base["hero_image_url"] = ctx.hero_image_url

    # Auto-generate cover headline from financial model data
    fm = ctx.financial_model
    sources_uses = fm.get("sources_uses", {})
    valuation = fm.get("valuation", {})

    # Try to get loan amount from various locations in the financial model
    loan_amount = (
        sources_uses.get("loan_amount")
        or valuation.get("loan_amount")
        or fm.get("loan_amount")
    )
    ltc = (
        sources_uses.get("ltc")
        or valuation.get("ltc")
        or fm.get("ltc")
    )

    # Build headline: "$X MILLION CONSTRUCTION FINANCING REQUEST (Y% LTC)"
    headline_parts = []
    if loan_amount:
        try:
            amount = float(loan_amount)
            if amount >= 1_000_000:
                headline_parts.append(f"${amount / 1_000_000:.1f} Million")
            else:
                headline_parts.append(format_currency(amount))
        except (TypeError, ValueError):
            pass

    headline_parts.append("Construction Financing Request")

    if ltc:
        try:
            ltc_val = float(ltc)
            if ltc_val < 1:
                ltc_val *= 100
            headline_parts[-1] += f" ({ltc_val:.0f}% LTC)"
        except (TypeError, ValueError):
            pass

    # deal_type_label comes from the ctx, not financial model
    # Skip appending property type to headline — the section header already has it

    base["deal_headline"] = " ".join(headline_parts) if headline_parts else ctx.property_name
    return base


def _section_divider(ctx: OMContext, title: str) -> dict:
    base = _base_ctx(ctx)
    base["title"] = title
    return base


def _transaction_overview(ctx: OMContext) -> dict:
    base = _base_ctx(ctx)
    base["narrative_paragraphs"] = ctx.transaction_overview or []

    # Build key metrics for the summary box
    fm = ctx.financial_model
    sources_uses = fm.get("sources_uses", {})
    valuation = fm.get("valuation", {})
    condo = fm.get("condo_sellout") or {}

    key_metrics = []

    loan_amount = (
        sources_uses.get("loan_amount")
        or valuation.get("loan_amount")
        or fm.get("loan_amount")
    )
    if loan_amount:
        key_metrics.append({"label": "Loan Request", "value": format_currency(loan_amount)})

    ltc = sources_uses.get("ltc") or valuation.get("ltc") or fm.get("ltc")
    if ltc:
        key_metrics.append({"label": "LTC", "value": format_pct(ltc) if float(ltc) < 1 else format_pct_raw(float(ltc))})

    tdc = (
        sources_uses.get("total_development_cost")
        or fm.get("total_development_cost")
        or fm.get("tdc")
    )
    if tdc:
        key_metrics.append({"label": "Total Development Cost", "value": format_currency(tdc)})

    total_units = fm.get("total_units") or fm.get("inputs", {}).get("total_units")
    if total_units:
        key_metrics.append({"label": "Total Units", "value": format_number(total_units)})

    # Condo-specific metrics
    gross_sellout = condo.get("projected_sellout") or condo.get("gross_sellout")
    if gross_sellout:
        key_metrics.append({"label": "Gross Sellout", "value": format_currency(gross_sellout)})

    profit_margin = condo.get("profit_margin_on_cost") or condo.get("profit_margin")
    if profit_margin:
        key_metrics.append({"label": "Profit Margin", "value": format_pct(profit_margin) if float(profit_margin) < 1 else format_pct_raw(float(profit_margin))})

    # Rental-specific metrics (only if no condo data)
    if not gross_sellout:
        noi = fm.get("proforma", {}).get("noi", {})
        noi_total = noi.get("total") if isinstance(noi, dict) else None
        if noi_total:
            key_metrics.append({"label": "Net Operating Income", "value": format_currency(noi_total)})

    base["key_metrics"] = key_metrics
    return base


def _investment_highlights(ctx: OMContext) -> dict:
    base = _base_ctx(ctx)
    base["highlights"] = ctx.investment_highlights or []
    return base


def _sources_uses(ctx: OMContext) -> dict:
    base = _base_ctx(ctx)
    fm = ctx.financial_model
    su = fm.get("sources_uses", {})

    headers = ["", "Total", "$/GSF", "$/NRA", "%"]

    def _format_row(row: dict, is_total: bool = False) -> dict:
        return {
            "cells": [
                row.get("label", ""),
                format_currency(row.get("total")),
                format_currency_sf(row.get("per_gsf")) if row.get("per_gsf") else "—",
                format_currency_sf(row.get("per_nra")) if row.get("per_nra") else "—",
                format_pct(row.get("pct_total")) if row.get("pct_total") is not None else "—",
            ],
            "css_class": "total-row" if is_total else "",
        }

    sources_rows = [_format_row(r) for r in su.get("sources", [])]
    if su.get("total_sources"):
        sources_rows.append(_format_row(su["total_sources"], is_total=True))

    uses_rows = [_format_row(r) for r in su.get("uses", []) if r.get("total", 0) != 0]
    if su.get("total_uses"):
        uses_rows.append(_format_row(su["total_uses"], is_total=True))

    base["headers"] = headers
    base["sources_rows"] = sources_rows
    base["uses_rows"] = uses_rows
    return base


def _financing_assumptions(ctx: OMContext) -> dict:
    base = _base_ctx(ctx)
    fm = ctx.financial_model
    valuation = fm.get("valuation", {})
    assumptions_data = fm.get("assumptions", {})

    assumptions = []

    # Loan amount — check top-level fm, then valuation, then sources_uses
    loan_amount = fm.get("loan_amount") or valuation.get("loan_amount")
    if loan_amount:
        assumptions.append({"label": "Loan Amount", "value": format_currency(loan_amount)})

    ltc = fm.get("ltc") or valuation.get("ltc")
    if ltc:
        assumptions.append({"label": "Loan-to-Cost", "value": format_pct(ltc)})

    # From assumptions dict
    for label, key, formatter in [
        ("Interest Rate", "interest_rate", format_pct_raw),
        ("Cap Rate", "cap_rate", format_pct),
        ("Vacancy (Free Market)", "vacancy_fm", format_pct),
        ("Vacancy (Affordable)", "vacancy_affordable", format_pct),
        ("Management Fee", "mgmt_fee_pct", format_pct),
    ]:
        val = assumptions_data.get(key)
        if val is not None:
            assumptions.append({"label": label, "value": formatter(val)})

    # From valuation
    for label, key, formatter in [
        ("Interest Reserve", "interest_reserve", format_currency),
        ("Recourse", "recourse", None),
    ]:
        val = valuation.get(key)
        if val is not None:
            assumptions.append({
                "label": label,
                "value": formatter(val) if formatter else str(val),
            })

    base["assumptions"] = assumptions
    return base


def _renderings_page(ctx: OMContext, images: list[dict]) -> dict:
    """Build context for a single renderings page with up to 3 images."""
    base = _base_ctx(ctx)
    base["images"] = images
    return base


def _development_overview(ctx: OMContext) -> dict:
    base = _base_ctx(ctx)
    stats = ctx.property_stats or {}

    # Fallback: build property stats from financial model + market_context
    if not stats:
        from collections import OrderedDict
        stats = OrderedDict()
        fm = ctx.financial_model
        mc = ctx.market_context or {}

        stats["Address"] = ctx.property_address or ""
        if mc.get("borough"):
            stats["Borough"] = mc["borough"]
        if mc.get("neighborhood"):
            stats["Neighborhood"] = mc["neighborhood"]
        if mc.get("zoning_district"):
            stats["Zoning"] = mc["zoning_district"]
        if mc.get("lot_area"):
            stats["Lot Area"] = mc["lot_area"] if isinstance(mc["lot_area"], str) else format_number(mc["lot_area"])
        if mc.get("far"):
            stats["FAR"] = str(mc["far"])
        if mc.get("mih_option"):
            stats["MIH"] = "Yes"

        zfa = fm.get("zfa")
        if zfa:
            stats["ZFA"] = format_number(zfa)
        gsf = fm.get("total_gsf")
        if gsf:
            stats["Gross SF"] = format_number(gsf)
        nra = fm.get("nra")
        if nra and nra != gsf:
            stats["Net Rentable Area"] = format_number(nra)
        total_units = fm.get("total_units")
        if total_units:
            stats["Total Units"] = format_number(total_units)

        # Unit breakdown from unit_mix
        um = fm.get("unit_mix", {})
        fm_rows = um.get("fm", [])
        affordable_rows = um.get("affordable_421a", []) + um.get("mih", [])
        if fm_rows:
            fm_units = sum(r.get("units", 0) for r in fm_rows)
            if fm_units:
                stats["Market Rate Units"] = format_number(fm_units)
        if affordable_rows:
            aff_units = sum(r.get("units", 0) for r in affordable_rows)
            if aff_units:
                stats["Affordable Units"] = format_number(aff_units)

        # Remove empty values
        stats = OrderedDict((k, v) for k, v in stats.items() if v not in (None, "", "0"))

    base["property_stats"] = stats
    base["lot_map_url"] = ctx.lot_map_url
    return base


def _construction_budget(ctx: OMContext, line_slice: list[dict], headers: list[str] | None = None) -> dict:
    base = _base_ctx(ctx)
    fm = ctx.financial_model
    budget = fm.get("construction_budget", {})
    default_headers = [
        "Item", "Total Cost", "% Total", "$/ZFA", "$/GSF", "$/NSF",
        "Spent to Date", "At Closing", "Future Funding",
    ]
    base["budget_headers"] = headers or budget.get("headers", default_headers)

    # Transform budget_detail rows into {cells: [...]} format for fin_table
    formatted_lines = []
    for row in line_slice:
        if "cells" in row:
            formatted_lines.append(row)
        else:
            # budget_detail format: {label, total_cost, pct_total, per_zfa, per_gsf, per_nsf, spent_to_date, at_closing, future_funding}
            is_total = row.get("category") == "total" or row.get("label", "").lower().startswith("total")
            is_category = row.get("category") in ("hard", "soft", "financing", "acquisition") or is_total
            formatted_lines.append({
                "cells": [
                    row.get("label", ""),
                    format_currency(row.get("total_cost")),
                    format_pct(row.get("pct_total")) if row.get("pct_total") else "—",
                    format_currency_sf(row.get("per_zfa")) if row.get("per_zfa") else "—",
                    format_currency_sf(row.get("per_gsf")) if row.get("per_gsf") else "—",
                    format_currency_sf(row.get("per_nsf")) if row.get("per_nsf") else "—",
                    format_currency(row.get("spent_to_date")) if row.get("spent_to_date") else "—",
                    format_currency(row.get("at_closing")) if row.get("at_closing") else "—",
                    format_currency(row.get("future_funding")) if row.get("future_funding") else "—",
                ],
                "css_class": "total-row" if is_total else ("category-header" if is_category else ""),
            })
    base["budget_lines"] = formatted_lines
    return base


def _budget_summary(ctx: OMContext) -> dict:
    base = _base_ctx(ctx)
    fm = ctx.financial_model
    budget_summary = fm.get("budget_summary", {})
    base["sources"] = budget_summary.get("sources", [])
    base["uses"] = budget_summary.get("uses", [])
    base["sources_headers"] = budget_summary.get("sources_headers")
    base["uses_headers"] = budget_summary.get("uses_headers")
    return base


def _unit_mix(ctx: OMContext) -> dict:
    base = _base_ctx(ctx)
    fm = ctx.financial_model
    um = fm.get("unit_mix", {})
    is_condo = bool(fm.get("condo_sellout"))

    # unit_mix is stored as {"fm": [...], "affordable_421a": [...], "mih": [...], "commercial": [...], "total": [...]}
    # Transform into tiered format the template expects: [{name, headers, rows: [{cells: [...]}]}]
    tier_label_map = {
        "fm": "Free Market",
        "affordable_421a": "421-a Affordable",
        "mih": "MIH",
        "commercial": "Commercial",
        "total": "Total",
    }

    def _beds_label(beds):
        if beds is None:
            return "—"
        if beds == 0:
            return "Studio"
        return f"{beds} BR"

    # Check if we have per-unit pricing data
    has_pricing = False
    for key in ["fm", "affordable_421a", "mih", "commercial", "total"]:
        for row in um.get(key, []):
            if is_condo and (row.get("avg_price") or row.get("price_per_sf")):
                has_pricing = True
                break
            elif not is_condo and (row.get("avg_monthly_rent") and row.get("avg_monthly_rent") != 0):
                has_pricing = True
                break

    def _format_row(row):
        units = row.get("units", 0) or 0
        sf = row.get("sf_per_unit", 0) or 0
        total_sf = int(units * sf) if units and sf else 0

        if is_condo and has_pricing:
            return {"cells": [
                _beds_label(row.get("beds")),
                row.get("baths") or "—",
                format_number(row.get("units")),
                format_number(row.get("sf_per_unit")),
                format_currency(row.get("avg_price")) if row.get("avg_price") else "—",
                format_currency_sf(row.get("price_per_sf")) if row.get("price_per_sf") else "—",
            ]}
        elif is_condo:
            # No per-unit pricing — show unit count and SF breakdown
            return {"cells": [
                _beds_label(row.get("beds")),
                format_number(row.get("units")),
                format_number(row.get("sf_per_unit")),
                format_number(total_sf) if total_sf else "—",
            ]}
        elif has_pricing:
            return {"cells": [
                _beds_label(row.get("beds")),
                row.get("baths") or "—",
                format_number(row.get("units")),
                format_number(row.get("sf_per_unit")),
                format_currency(row.get("avg_monthly_rent")) if row.get("avg_monthly_rent") else "—",
                format_currency_sf(row.get("rent_per_sf")) if row.get("rent_per_sf") else "—",
            ]}
        else:
            return {"cells": [
                _beds_label(row.get("beds")),
                format_number(row.get("units")),
                format_number(row.get("sf_per_unit")),
                format_number(total_sf) if total_sf else "—",
            ]}

    # Determine headers based on deal type and pricing availability
    if is_condo and has_pricing:
        tier_headers = ["Beds", "Baths", "Units", "SF/Unit", "Avg Price", "Price/SF"]
    elif is_condo:
        tier_headers = ["Beds", "Units", "SF/Unit", "Total SF"]
    elif has_pricing:
        tier_headers = ["Beds", "Baths", "Units", "SF/Unit", "Avg Monthly Rent", "Rent/SF"]
    else:
        tier_headers = ["Beds", "Units", "SF/Unit", "Total SF"]

    tiers = um.get("tiers", [])
    if not tiers:
        tier_keys = ["fm", "affordable_421a", "mih", "commercial"]
        non_total_tiers = []
        for key in tier_keys:
            rows = um.get(key, [])
            if rows:
                formatted = [_format_row(r) for r in rows]
                # Add summary row
                total_units = sum(r.get("units", 0) or 0 for r in rows)
                total_sf = sum(int((r.get("units", 0) or 0) * (r.get("sf_per_unit", 0) or 0)) for r in rows)
                avg_sf = int(total_sf / total_units) if total_units else 0
                if is_condo and not has_pricing:
                    formatted.append({"cells": ["Total", format_number(total_units), format_number(avg_sf), format_number(total_sf)], "css_class": "total-row"})
                elif not is_condo and not has_pricing:
                    formatted.append({"cells": ["Total", format_number(total_units), format_number(avg_sf), format_number(total_sf)], "css_class": "total-row"})
                else:
                    formatted.append({"cells": ["Total", "—", format_number(total_units), format_number(avg_sf), "—", "—"], "css_class": "total-row"})
                non_total_tiers.append({
                    "name": tier_label_map.get(key, key),
                    "headers": tier_headers,
                    "rows": formatted,
                })
        tiers = non_total_tiers

        # Only add Total tier if there are multiple unit tiers
        # (otherwise Total = the single tier, which is redundant)
        total_rows = um.get("total", [])
        if total_rows and len(non_total_tiers) > 1:
            tiers.append({
                "name": "Total",
                "headers": tier_headers,
                "rows": [_format_row(r) for r in total_rows],
                "css_class": "total-tier",
            })

    base["tiers"] = tiers
    base["is_condo"] = is_condo
    return base


def _rental_proforma(ctx: OMContext) -> dict:
    base = _base_ctx(ctx)
    fm = ctx.financial_model
    base["proforma"] = fm.get("proforma", {})
    return base


def _condo_sellout(ctx: OMContext) -> dict:
    """Build context for the condo sellout analysis page."""
    base = _base_ctx(ctx)
    fm = ctx.financial_model
    condo = fm.get("condo_sellout") or {}

    # Engine stores "projected_sellout" — map to display name "gross_sellout"
    gross_sellout = condo.get("projected_sellout") or condo.get("gross_sellout") or 0
    net_sellout = condo.get("net_sellout") or gross_sellout
    closing_costs = gross_sellout - net_sellout if gross_sellout and net_sellout else 0

    tdc = condo.get("total_development_cost") or fm.get("total_development_cost") or 0
    profit = condo.get("profit") or (net_sellout - tdc if net_sellout and tdc else 0)
    profit_margin = condo.get("profit_margin_on_cost") or condo.get("profit_margin") or (profit / tdc if tdc else 0)

    equity = condo.get("equity") or fm.get("equity") or 0
    roe = condo.get("return_on_equity") or (profit / equity if equity else None)

    total_units = condo.get("total_units") or fm.get("total_units") or 0
    total_gsf = condo.get("total_gsf") or fm.get("total_gsf") or 0

    per_unit_sellout = condo.get("per_unit_sellout") or (gross_sellout / total_units if total_units else None)
    per_unit_cost = condo.get("per_unit_cost") or (tdc / total_units if total_units else None)
    per_sf_sellout = condo.get("per_sf_sellout") or (gross_sellout / total_gsf if total_gsf else None)
    per_sf_cost = condo.get("per_sf_cost") or (tdc / total_gsf if total_gsf else None)

    loan_amount = condo.get("loan_amount") or fm.get("loan_amount") or 0
    ltc = condo.get("ltc") or fm.get("ltc")
    ltv = condo.get("ltv")

    base["gross_sellout"] = gross_sellout
    base["closing_costs"] = closing_costs
    base["net_sellout"] = net_sellout
    base["tdc"] = tdc
    base["profit"] = profit
    base["profit_margin"] = profit_margin
    base["equity"] = equity
    base["roe"] = roe
    base["per_unit_sellout"] = per_unit_sellout
    base["per_unit_cost"] = per_unit_cost
    base["per_sf_sellout"] = per_sf_sellout
    base["per_sf_cost"] = per_sf_cost
    base["loan_amount"] = loan_amount
    base["ltc"] = ltc
    base["ltv"] = ltv
    base["total_units"] = total_units
    base["total_gsf"] = total_gsf
    return base


def _valuation_summary(ctx: OMContext) -> dict:
    base = _base_ctx(ctx)
    fm = ctx.financial_model
    val = fm.get("valuation", {})

    # valuation may have a pre-built "sections" list or flat keys — handle both
    sections = val.get("sections", [])
    if not sections:
        # Build display sections from flat valuation keys
        income_section = {"header": "Income & Valuation", "rows": []}
        debt_section = {"header": "Debt Metrics", "rows": []}
        cap_section = {"header": "Capitalization", "rows": []}

        field_map = [
            ("actual_noi", "NOI (With Abatement)", format_currency, income_section),
            ("full_tax_noi", "NOI (Full Tax)", format_currency, income_section),
            ("cap_rate", "Cap Rate", format_pct, income_section),
            ("yield_on_cost", "Yield on Cost", format_pct, income_section),
            ("estimated_value_a", "Estimated Value (Abated)", format_currency, income_section),
            ("abatement_value_b", "Abatement Benefit Value", format_currency, income_section),
            ("total_asset_value", "Total Asset Value", format_currency, income_section),
            ("value_per_unit", "Value Per Unit", format_currency, debt_section),
            ("value_per_gsf", "Value Per GSF", format_currency_sf, debt_section),
            ("construction_loan", "Construction Loan", format_currency, debt_section),
            ("stabilized_ltv", "Stabilized LTV", format_pct, debt_section),
            ("debt_yield", "Debt Yield", format_pct, debt_section),
            ("debt_per_unit", "Debt Per Unit", format_currency, debt_section),
            ("debt_per_gsf", "Debt Per GSF", format_currency_sf, debt_section),
            ("total_project_cap", "Total Project Capitalization", format_currency, cap_section),
        ]
        for key, label, formatter, section in field_map:
            v = val.get(key)
            if v is not None:
                try:
                    num_v = float(v)
                except (TypeError, ValueError):
                    continue
                # Skip zero-value income items for condo deals
                if num_v == 0 and key in ("actual_noi", "full_tax_noi", "yield_on_cost",
                                           "estimated_value_a", "abatement_value_b",
                                           "total_asset_value", "stabilized_ltv", "debt_yield",
                                           "value_per_unit", "value_per_gsf"):
                    continue
                section["rows"].append({"label": label, "value": formatter(v)})

        for s in [income_section, debt_section, cap_section]:
            if s["rows"]:
                sections.append(s)

    base["valuation_sections"] = sections
    return base


def _abatement_schedule(ctx: OMContext, years: list[dict], assumptions: list[dict] | None = None, headers: list[str] | None = None) -> dict:
    base = _base_ctx(ctx)
    fm = ctx.financial_model
    abatement = fm.get("abatement", {})
    base["years_page1"] = years
    base["abatement_assumptions"] = assumptions
    base["abatement_headers"] = headers or abatement.get("headers")
    return base


def _market_narrative_page(ctx: OMContext, sections: list[dict], page_idx: int) -> dict:
    base = _base_ctx(ctx)
    mc = ctx.market_context or {}
    base["submarket_name"] = mc.get("submarket_name", "")
    base["narrative_sections"] = sections
    # Only include images on the first market narrative page
    if page_idx == 0:
        base["market_images"] = ctx.market_images or []
    else:
        base["market_images"] = []
    return base


def _rent_comps(ctx: OMContext) -> dict:
    base = _base_ctx(ctx)
    base["rent_comps"] = ctx.rent_comps or []
    return base


def _sales_comps(ctx: OMContext, comps_slice: list | None = None) -> dict:
    base = _base_ctx(ctx)
    comps = comps_slice if comps_slice is not None else (ctx.sales_comps or [])
    base["sales_comps"] = comps
    # Show cap_rate column if any comp has it
    base["show_cap_rate"] = any(c.get("cap_rate") for c in comps if isinstance(c, dict))
    return base


def _lease_comps(ctx: OMContext) -> dict:
    base = _base_ctx(ctx)
    base["lease_comps"] = ctx.lease_comps or []
    return base


def _sponsor_bio(ctx: OMContext, sponsor: dict) -> dict:
    base = _base_ctx(ctx)
    base["sponsor_name"] = sponsor.get("name", "")
    base["sponsor_logos"] = sponsor.get("logos", [])

    narrative = sponsor.get("narrative", [])

    # Fallback: build structured bio from sponsor data fields
    if not narrative:
        narrative = _build_sponsor_narrative(ctx, sponsor.get("name", ""))

    base["sponsor_narrative"] = narrative

    # Build structured data for the template
    base["sponsor_credentials"] = sponsor.get("credentials", [])
    base["sponsor_projects"] = sponsor.get("completed_projects", []) + sponsor.get("current_projects", [])
    return base


def _build_sponsor_narrative(ctx: OMContext, sponsor_name: str) -> list[str]:
    """Build sponsor narrative paragraphs from structured deal.sponsor data."""
    # Find matching sponsor in the raw deal sponsor list
    # The sponsor data in ctx.sponsor_data has limited fields; we need the raw data
    # which was passed through as-is from deal.sponsor
    # Look for raw sponsor data attached to the sponsor_data entry
    raw = None
    for s in (ctx.sponsor_data or []):
        if s.get("name") == sponsor_name:
            raw = s
            break
    if not raw:
        return []

    # Try to find the full sponsor record - it may have been stored in market_context
    # or in the sponsor_data dict itself with extra fields
    # Check if the raw sponsor data has the detailed fields
    mc = ctx.market_context or {}

    paragraphs = []

    # Build an overview paragraph from available fields
    entity = raw.get("sponsor_entity", "")
    experience = raw.get("years_experience", "")
    total_value = raw.get("total_development_value", "")
    total_units = raw.get("total_units_developed", "")

    if entity or experience:
        intro = f"{sponsor_name}"
        if entity:
            intro += f", through {entity},"
        if experience:
            intro += f" brings {experience} of real estate development experience"
        else:
            intro += " is an experienced real estate developer"
        intro += "."
        paragraphs.append(intro)

    if total_value:
        # Truncate if too long
        val_str = total_value
        if len(val_str) > 200:
            val_str = val_str[:val_str.rfind(";", 0, 200) + 1] if ";" in val_str[:200] else val_str[:200]
        paragraphs.append(f"Total development portfolio: {val_str}")

    # Completed projects
    completed = raw.get("completed_projects", [])
    if completed:
        projects_text = "Completed projects include: "
        project_items = []
        for p in completed:
            name = p.get("name", "")
            loc = p.get("location", "")
            val = p.get("value", "")
            item = name
            if loc:
                item += f" ({loc})"
            if val:
                item += f" — {val}"
            project_items.append(item)
        projects_text += "; ".join(project_items) + "."
        paragraphs.append(projects_text)

    # Current projects
    current = raw.get("current_projects", [])
    if current:
        projects_text = "Current development pipeline includes: "
        project_items = []
        for p in current:
            name = p.get("name", "")
            loc = p.get("location", "")
            units = p.get("units")
            status = p.get("status", "")
            item = name
            if loc:
                item += f" ({loc})"
            if units:
                item += f", {units} units"
            if status:
                item += f" — {status}"
            project_items.append(item)
        projects_text += "; ".join(project_items) + "."
        paragraphs.append(projects_text)

    # Notable achievements (pick top 3)
    achievements = raw.get("notable_achievements", [])
    if achievements:
        top = achievements[:4]
        paragraphs.append("Key achievements: " + ". ".join(top) + ".")

    return paragraphs


def _sponsor_projects(ctx: OMContext, sponsor: dict) -> dict:
    base = _base_ctx(ctx)
    base["sponsor_name"] = sponsor.get("name", "")
    base["projects"] = sponsor.get("projects", [])
    return base


def _back_cover(ctx: OMContext) -> dict:
    return _base_ctx(ctx)


# ---------------------------------------------------------------------------
# Main manifest builder
# ---------------------------------------------------------------------------

def build_page_manifest(ctx: OMContext) -> list[dict]:
    """Return ordered list of pages to render.

    Each page dict:
        {
            "template": "pages/<name>.html",
            "ctx": {page-specific context dict},
            "page_type": "<name>"
        }
    """
    pages: list[dict] = []

    def _add(template: str, page_ctx: dict, page_type: str) -> None:
        pages.append({
            "template": f"pages/{template}",
            "ctx": page_ctx,
            "page_type": page_type,
        })

    # 1. Cover — always
    _add("cover.html", _cover(ctx), "cover")

    # 2. Section divider: EXECUTIVE SUMMARY — always
    _add("section_divider.html", _section_divider(ctx, "EXECUTIVE SUMMARY"), "section_divider")

    # 3. Transaction overview — always
    _add("transaction_overview.html", _transaction_overview(ctx), "transaction_overview")

    # 4. Investment highlights — only if content exists
    if ctx.investment_highlights:
        _add("investment_highlights.html", _investment_highlights(ctx), "investment_highlights")

    # 5. Sources & Uses + Financing Assumptions (combined for density)
    su_ctx = _sources_uses(ctx)
    fa_ctx = _financing_assumptions(ctx)
    su_ctx["assumptions"] = fa_ctx.get("assumptions", [])
    _add("sources_uses.html", su_ctx, "sources_uses")

    # 7. Section divider: PROJECT OVERVIEW — always
    _add("section_divider.html", _section_divider(ctx, "PROJECT OVERVIEW"), "section_divider")

    # 8. Renderings — only if rendering_images is not empty
    rendering_images = ctx.rendering_images or []
    if rendering_images:
        # <=3 images = 1 page, >3 = 2 pages
        if len(rendering_images) <= 3:
            _add("renderings.html", _renderings_page(ctx, rendering_images), "renderings")
        else:
            # Split: first 3 on page 1, rest on page 2
            _add("renderings.html", _renderings_page(ctx, rendering_images[:3]), "renderings")
            _add("renderings.html", _renderings_page(ctx, rendering_images[3:6]), "renderings")

    # 9. Development overview — always
    _add("development_overview.html", _development_overview(ctx), "development_overview")

    # 10. Section divider: FINANCIAL OVERVIEW — always
    _add("section_divider.html", _section_divider(ctx, "FINANCIAL OVERVIEW"), "section_divider")

    # 11. Construction budget — only if budget lines exist
    fm = ctx.financial_model
    budget = fm.get("construction_budget", {})
    budget_lines = budget.get("rows", budget.get("lines", []))
    # Fallback: engine stores budget as "budget_detail" (a flat array)
    if not budget_lines:
        budget_lines = list(fm.get("budget_detail", []))

    # If budget_detail only has category summaries, supplement with Acquisition from S&U
    if budget_lines:
        has_acquisition = any(r.get("label", "").lower().startswith("acqui") for r in budget_lines)
        if not has_acquisition:
            su = fm.get("sources_uses", {})
            acq = next((u for u in su.get("uses", []) if u.get("label", "").lower().startswith("acqui")), None)
            if acq and acq.get("total", 0) > 0:
                budget_lines.insert(0, {
                    "category": "acquisition",
                    "label": acq["label"],
                    "total_cost": acq["total"],
                    "pct_total": acq.get("pct_total"),
                    "per_zfa": acq.get("per_zfa"),
                    "per_gsf": acq.get("per_gsf"),
                    "per_nsf": acq.get("per_nra"),
                    "spent_to_date": acq.get("prior_to_closing", 0),
                    "at_closing": acq.get("at_closing", 0),
                    "future_funding": acq.get("future_funding", 0),
                })

        # Add total row if not already present
        has_total = any(r.get("category") == "total" or r.get("label", "").lower().startswith("total") for r in budget_lines)
        if not has_total:
            tdc = fm.get("total_development_cost") or sum(r.get("total_cost", 0) for r in budget_lines)
            if tdc:
                budget_lines.append({
                    "category": "total",
                    "label": "Total Development Cost",
                    "total_cost": tdc,
                    "pct_total": 1.0,
                    "per_zfa": None,
                    "per_gsf": tdc / fm.get("total_gsf", 1) if fm.get("total_gsf") else None,
                    "per_nsf": tdc / fm.get("nra", 1) if fm.get("nra") else None,
                    "spent_to_date": sum(r.get("spent_to_date", 0) or 0 for r in budget_lines),
                    "at_closing": sum(r.get("at_closing", 0) or 0 for r in budget_lines),
                    "future_funding": sum(r.get("future_funding", 0) or 0 for r in budget_lines),
                })

    budget_headers = budget.get("headers")

    if budget_lines:
        if len(budget_lines) > 30:
            midpoint = math.ceil(len(budget_lines) / 2)
            _add("construction_budget.html", _construction_budget(ctx, budget_lines[:midpoint], budget_headers), "construction_budget")
            _add("construction_budget.html", _construction_budget(ctx, budget_lines[midpoint:], budget_headers), "construction_budget")
        else:
            _add("construction_budget.html", _construction_budget(ctx, budget_lines, budget_headers), "construction_budget")

    # 12. Budget summary — only if sources or uses exist
    budget_summary = fm.get("budget_summary", {})
    if budget_summary.get("sources") or budget_summary.get("uses"):
        _add("budget_summary.html", _budget_summary(ctx), "budget_summary")

    # 13. Unit mix — only if unit data exists
    um = fm.get("unit_mix", {})
    has_unit_data = bool(um.get("tiers") or um.get("fm") or um.get("total"))
    if has_unit_data:
        _add("unit_mix.html", _unit_mix(ctx), "unit_mix")

    # 14. Rental proforma — only if NOI > 0 (skip for condo/for-sale deals)
    proforma = fm.get("proforma", {})
    noi_data = proforma.get("noi", {})
    noi_total = 0
    if isinstance(noi_data, dict):
        try:
            noi_total = float(noi_data.get("total", 0) or 0)
        except (TypeError, ValueError):
            noi_total = 0
    if noi_total > 0:
        _add("rental_proforma.html", _rental_proforma(ctx), "rental_proforma")

    # 15. Valuation summary — always
    _add("valuation_summary.html", _valuation_summary(ctx), "valuation_summary")

    # 15b. Condo sellout analysis — only for condo deals
    condo_sellout = fm.get("condo_sellout")
    if condo_sellout:
        _add("condo_sellout.html", _condo_sellout(ctx), "condo_sellout")

    # 16. Abatement schedule — only if abatement data exists
    abatement = fm.get("abatement")
    if abatement:
        all_years = abatement.get("years", [])
        assumptions = abatement.get("assumptions", [])
        headers = abatement.get("headers")

        # Always 2 pages: years 1-18 and years 19-35
        page1_years = [y for y in all_years if y.get("year", 0) <= 18]
        page2_years = [y for y in all_years if y.get("year", 0) > 18]

        # If years aren't tagged with a "year" field, split by index
        if not page1_years and not page2_years and all_years:
            page1_years = all_years[:18]
            page2_years = all_years[18:]

        _add("abatement_schedule.html", _abatement_schedule(ctx, page1_years, assumptions, headers), "abatement_schedule")
        if page2_years:
            _add("abatement_schedule.html", _abatement_schedule(ctx, page2_years, None, headers), "abatement_schedule")

    # 17. Section divider: MARKET OVERVIEW — always
    _add("section_divider.html", _section_divider(ctx, "MARKET OVERVIEW"), "section_divider")

    # 18. Market narrative — only if content exists
    market_sections = ctx.market_narrative or []
    if market_sections:
        if len(market_sections) <= 2:
            _add("market_narrative.html", _market_narrative_page(ctx, market_sections, 0), "market_narrative")
        else:
            midpoint = math.ceil(len(market_sections) / 2)
            _add("market_narrative.html", _market_narrative_page(ctx, market_sections[:midpoint], 0), "market_narrative")
            _add("market_narrative.html", _market_narrative_page(ctx, market_sections[midpoint:], 1), "market_narrative")

    # 19. Rent comps — only if data exists
    if ctx.rent_comps:
        _add("rent_comps.html", _rent_comps(ctx), "rent_comps")

    # 20. Sales comps — limit to top 20 building-level transactions
    if ctx.sales_comps:
        comps = ctx.sales_comps
        # Cap at 20 most relevant comps to avoid data dumps
        MAX_SALES_COMPS = 20
        if len(comps) > MAX_SALES_COMPS:
            comps = comps[:MAX_SALES_COMPS]
        COMPS_PER_PAGE = 15
        if len(comps) <= COMPS_PER_PAGE:
            _add("sales_comps.html", _sales_comps(ctx, comps), "sales_comps")
        else:
            for start in range(0, len(comps), COMPS_PER_PAGE):
                _add("sales_comps.html", _sales_comps(ctx, comps[start:start + COMPS_PER_PAGE]), "sales_comps")

    # 21. Lease comps — only if data exists and financial model has commercial units
    has_commercial = bool(fm.get("unit_mix", {}).get("commercial"))
    if ctx.lease_comps and has_commercial:
        _add("lease_comps.html", _lease_comps(ctx), "lease_comps")

    # 22. Section divider: DEVELOPMENT TEAM OVERVIEW — only if sponsor_data
    sponsor_data = ctx.sponsor_data or []
    if sponsor_data:
        _add("section_divider.html", _section_divider(ctx, "DEVELOPMENT TEAM OVERVIEW"), "section_divider")

        # 23. For each sponsor: bio page + optional projects page
        for sponsor in sponsor_data:
            _add("sponsor_bio.html", _sponsor_bio(ctx, sponsor), "sponsor_bio")
            if sponsor.get("projects"):
                _add("sponsor_projects.html", _sponsor_projects(ctx, sponsor), "sponsor_projects")

    # 24. Back cover — always
    _add("back_cover.html", _back_cover(ctx), "back_cover")

    return pages
