"""Risk Report tools — compile findings, generate narrative, render PDF."""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.tools.base import PlumbTool, ToolContext, ToolPermission, ToolResult

logger = logging.getLogger(__name__)


def _first_sponsor(sponsor_field) -> dict:
    """Return the first sponsor dict regardless of whether the column holds a
    list or a single object."""
    if not sponsor_field:
        return {}
    if isinstance(sponsor_field, list):
        return sponsor_field[0] if sponsor_field and isinstance(sponsor_field[0], dict) else {}
    if isinstance(sponsor_field, dict):
        return sponsor_field
    return {}


def _reconciled_address(deal) -> str:
    """Return the best display address for the subject property.

    Shares the same reconciliation logic as om_generation: if the stored
    property_address contradicts the extracted borough (e.g. address says
    ', NJ' but borough is Queens), prefer a composed address built from the
    extracted borough + neighborhood. Keeps the risk report honest about
    geography even when the deal was created with a placeholder address.
    """
    from app.tasks.om_generation import _reconcile_property_address
    fm = (deal.typed_extension or {}).get("financial_model") or {}
    return _reconcile_property_address(deal, fm)


def _fmt_money(value) -> str:
    try:
        return f"${float(value):,.0f}"
    except (TypeError, ValueError):
        return "N/A"


def _coerce_int(value) -> int | None:
    """Best-effort int coercion that tolerates descriptive strings.

    Sponsor records sometimes carry human-readable values like
    '890+ units across all projects (269 — Flushing Square; …)'. Pull the
    first contiguous run of digits out so downstream formatting does not
    crash.
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
    import re
    m = re.search(r"\d[\d,]*", str(value))
    if not m:
        return None
    try:
        return int(m.group(0).replace(",", ""))
    except ValueError:
        return None


def _fmt_pct(value) -> str:
    try:
        return f"{float(value) * 100:.1f}%"
    except (TypeError, ValueError):
        return "N/A"


def _check_capital_stack(findings: list, fm: dict) -> None:
    """Capital stack risk: leverage, equity, contingency."""
    sources_uses = fm.get("sources_uses", {}) or {}
    loan = fm.get("loan_amount") or sources_uses.get("loan_amount") or 0
    tdc = fm.get("total_development_cost") or fm.get("tdc") or 0
    equity = sources_uses.get("equity") or fm.get("equity") or 0
    ltc = fm.get("ltc") or 0
    if not ltc and loan and tdc:
        try:
            ltc = float(loan) / float(tdc)
        except (TypeError, ValueError, ZeroDivisionError):
            ltc = 0

    if ltc and tdc and loan:
        if ltc >= 0.70:
            findings.append({
                "category": "capital_stack",
                "severity": "critical" if ltc >= 0.75 else "warning",
                "title": f"Loan-to-Cost at {ltc*100:.1f}%",
                "description": (
                    f"Requested loan of {_fmt_money(loan)} against TDC of {_fmt_money(tdc)} "
                    f"implies LTC of {ltc*100:.1f}%, above the 60-65% peer band for "
                    f"ground-up condo construction. Consider stress-testing at 65% LTC "
                    f"(implied loan {_fmt_money(float(tdc)*0.65)})."
                ),
                "source": "Pro Forma — Sources & Uses",
                "evidence": f"{_fmt_money(loan)} loan / {_fmt_money(tdc)} TDC = {ltc*100:.2f}% LTC",
            })
        elif 0 < ltc <= 0.60:
            findings.append({
                "category": "capital_stack",
                "severity": "positive",
                "title": f"Conservative Leverage at {ltc*100:.1f}% LTC",
                "description": (
                    f"LTC of {ltc*100:.1f}% provides a meaningful cushion to the typical "
                    f"60-65% peer band for ground-up NYC condo construction."
                ),
                "source": "Pro Forma — Sources & Uses",
                "evidence": f"{_fmt_money(loan)} loan / {_fmt_money(tdc)} TDC",
            })

    if equity and tdc:
        try:
            equity_pct = float(equity) / float(tdc)
        except (TypeError, ValueError, ZeroDivisionError):
            equity_pct = 0
        if 0 < equity_pct < 0.20:
            findings.append({
                "category": "capital_stack",
                "severity": "warning",
                "title": f"Sponsor Equity at {equity_pct*100:.1f}% of TDC",
                "description": (
                    f"Sponsor equity of {_fmt_money(equity)} represents {equity_pct*100:.1f}% "
                    f"of TDC, below the 20-25% threshold most construction lenders require "
                    f"for first-time or mid-market sponsors."
                ),
                "source": "Pro Forma — Sources & Uses",
                "evidence": f"{_fmt_money(equity)} equity / {_fmt_money(tdc)} TDC",
            })

    hard_costs = fm.get("hard_costs") or 0
    contingency = (
        fm.get("hard_cost_contingency")
        or fm.get("contingency")
        or fm.get("soft_cost_contingency")
        or 0
    )
    if hard_costs and contingency:
        try:
            cont_pct = float(contingency) / float(hard_costs)
        except (TypeError, ValueError, ZeroDivisionError):
            cont_pct = 0
        if 0 < cont_pct < 0.05:
            findings.append({
                "category": "construction",
                "severity": "warning",
                "title": f"Thin Hard-Cost Contingency ({cont_pct*100:.1f}%)",
                "description": (
                    f"Hard-cost contingency of {_fmt_money(contingency)} is {cont_pct*100:.1f}% "
                    f"of {_fmt_money(hard_costs)} hard costs, below the 5% market norm for "
                    f"ground-up residential in NYC. At 5%, TDC would increase by "
                    f"{_fmt_money(float(hard_costs)*0.05 - float(contingency))}."
                ),
                "source": "Pro Forma — Development Budget",
                "evidence": f"{_fmt_money(contingency)} contingency / {_fmt_money(hard_costs)} hard costs",
            })


def _check_construction(findings: list, fm: dict) -> None:
    """Construction basis and cost discipline."""
    tdc = fm.get("total_development_cost") or 0
    units = fm.get("total_units") or 0
    gsf = fm.get("total_gsf") or 0

    if tdc and units:
        try:
            cost_per_unit = float(tdc) / int(units)
        except (TypeError, ValueError, ZeroDivisionError):
            cost_per_unit = 0
        if cost_per_unit:
            findings.append({
                "category": "construction",
                "severity": "info",
                "title": f"Cost Basis: {_fmt_money(cost_per_unit)}/unit",
                "description": (
                    f"All-in cost per unit of {_fmt_money(cost_per_unit)} "
                    f"({_fmt_money(tdc)} TDC across {units:,} units). Benchmark against "
                    f"comparable NYC ground-up condo basis of $750K-$1.2M/unit depending on "
                    f"finish level and location."
                ),
                "source": "Pro Forma — Total Development Cost",
                "evidence": f"{_fmt_money(tdc)} / {units:,} units",
            })
    if tdc and gsf:
        try:
            cost_per_sf = float(tdc) / float(gsf)
        except (TypeError, ValueError, ZeroDivisionError):
            cost_per_sf = 0
        if cost_per_sf:
            findings.append({
                "category": "construction",
                "severity": "info",
                "title": f"Cost Basis: ${cost_per_sf:,.0f}/GSF",
                "description": (
                    f"All-in cost per gross square foot of ${cost_per_sf:,.0f} across "
                    f"{int(gsf):,} GSF. Credit committee should benchmark against recent "
                    f"comparable deliveries."
                ),
                "source": "Pro Forma — Total Development Cost",
                "evidence": f"{_fmt_money(tdc)} / {int(gsf):,} GSF",
            })


def _check_zoning(findings: list, reg: dict, mc: dict) -> None:
    """Zoning, entitlements, regulatory approvals."""
    if not isinstance(reg, dict):
        reg = {}

    zoning = mc.get("zoning_district") or mc.get("zoning") if isinstance(mc, dict) else None
    mih_option = reg.get("mih_option")
    approval_date = reg.get("approval_date")
    ulurp = reg.get("ulurp_numbers")
    variance = reg.get("variance_granted")
    affordable_pct = reg.get("affordable_percentage")

    if mih_option and affordable_pct:
        findings.append({
            "category": "zoning",
            "severity": "info",
            "title": f"MIH Option {mih_option} Requires {affordable_pct} Affordable",
            "description": (
                f"Project is subject to Mandatory Inclusionary Housing Option {mih_option}, "
                f"requiring {affordable_pct} of residential units at designated AMI bands. "
                f"Affordable units will not contribute to condo sellout and affect NIBT."
            ),
            "source": (
                f"Regulatory — ULURP {ulurp}" if ulurp else "Regulatory — MIH Overlay"
            ),
            "evidence": f"MIH Option {mih_option}, {affordable_pct} affordable requirement",
        })

    if ulurp and approval_date:
        findings.append({
            "category": "zoning",
            "severity": "positive",
            "title": "ULURP Approval in Place",
            "description": (
                f"Discretionary land-use approval ULURP {ulurp} granted {approval_date}. "
                f"Removes entitlement risk from the critical path."
            ),
            "source": "Regulatory — ULURP Record",
            "evidence": f"ULURP {ulurp} approved {approval_date}",
        })
    elif mih_option and not approval_date:
        findings.append({
            "category": "zoning",
            "severity": "critical",
            "title": "Discretionary Action Not Yet Approved",
            "description": (
                "Project relies on an MIH rezoning or special permit, but no approval date "
                "is documented in the deal package. Entitlement risk should be resolved "
                "before term sheet issuance."
            ),
            "source": "Regulatory — ULURP Record",
            "evidence": "No approval_date in regulatory record",
        })

    if variance:
        findings.append({
            "category": "zoning",
            "severity": "info",
            "title": "BSA Variance Granted",
            "description": (
                f"Project relies on a Board of Standards and Appeals variance: {variance}. "
                f"Confirm the variance is not conditional on milestones that could lapse."
            ),
            "source": "Regulatory — BSA Record",
            "evidence": f"Variance: {variance}",
        })

    if zoning:
        findings.append({
            "category": "zoning",
            "severity": "info",
            "title": f"As-of-Right Zoning: {zoning}",
            "description": (
                f"Subject sits in {zoning}. Confirm the project is built to as-of-right "
                f"envelope or that any overrides (special district, bonus FAR) are "
                f"documented in the entitlement package."
            ),
            "source": "ZoLa / Regulatory Record",
            "evidence": f"Zoning district: {zoning}",
        })


def _check_sponsor(findings: list, sponsor: dict, mc: dict) -> None:
    """Sponsor track record and counterparty risk."""
    if not sponsor:
        findings.append({
            "category": "sponsor",
            "severity": "warning",
            "title": "Sponsor Profile Not Documented",
            "description": (
                "Sponsor name and track record not present in the deal package. "
                "Obtain a sponsor bio and schedule of completed projects before "
                "committee review."
            ),
            "source": "Deal Package",
            "evidence": "No sponsor object in extracted data",
        })
        return

    years = sponsor.get("years_experience")
    completed = sponsor.get("completed_projects") or []
    total_value = sponsor.get("total_development_value")
    total_units = _coerce_int(sponsor.get("total_units_developed"))
    name = sponsor.get("name") or sponsor.get("sponsor_name") or "Sponsor"

    if years and completed:
        count = len(completed) if isinstance(completed, list) else 0
        findings.append({
            "category": "sponsor",
            "severity": "positive",
            "title": f"{name} — {years} Years, {count} Completed Projects",
            "description": (
                f"{name} reports {years} years of experience with {count} completed "
                f"projects"
                + (f", {total_units:,} total units" if total_units else "")
                + (f", {_fmt_money(total_value)} total development value" if total_value else "")
                + ". Track record supports execution capability on a project of this scale."
            ),
            "source": "Sponsor Bio — Deal Package",
            "evidence": f"{years} years, {count} completed projects",
        })
    elif not completed:
        findings.append({
            "category": "sponsor",
            "severity": "warning",
            "title": "Sponsor Track Record Not Substantiated",
            "description": (
                f"{name} has no completed-projects schedule in the deal package. "
                f"Lender diligence should obtain a schedule of comparable completed "
                f"projects before term sheet."
            ),
            "source": "Sponsor Bio — Deal Package",
            "evidence": "No completed_projects in sponsor record",
        })

    permits = mc.get("permits") if isinstance(mc, dict) else None
    if isinstance(permits, dict):
        violations = permits.get("open_violations") or permits.get("violations") or []
        if isinstance(violations, list) and violations:
            findings.append({
                "category": "sponsor",
                "severity": "warning" if len(violations) < 3 else "critical",
                "title": f"{len(violations)} Open DOB Violation(s) at Subject",
                "description": (
                    f"NYC Department of Buildings shows {len(violations)} open violation(s) "
                    f"on record for the subject property. Resolution status should be "
                    f"confirmed before closing."
                ),
                "source": "NYC DOB — Violations Record",
                "evidence": f"Open violations: {violations[:3]}",
            })


def _check_market(findings: list, fm: dict, mc: dict) -> None:
    """Market / absorption / comparable validation."""
    condo = fm.get("condo_sellout") or {}
    projected_sellout = condo.get("projected_sellout") or fm.get("projected_sellout") or 0
    per_sf_sellout = condo.get("per_sf_sellout") or fm.get("per_sf_sellout") or 0
    profit_margin = condo.get("profit_margin_on_cost") or fm.get("profit_margin_on_cost") or 0
    absorption = mc.get("absorption_rate") if isinstance(mc, dict) else None
    comps = mc.get("comparable_sales") or [] if isinstance(mc, dict) else []

    # Profit margin thin / healthy
    if profit_margin:
        try:
            pm = float(profit_margin)
        except (TypeError, ValueError):
            pm = 0
        if 0 < pm < 0.12:
            findings.append({
                "category": "market",
                "severity": "warning",
                "title": f"Thin Developer Margin ({pm*100:.1f}%)",
                "description": (
                    f"Projected profit margin on cost of {pm*100:.1f}% is below the 15-20% "
                    f"margin-on-cost most ground-up NYC condo lenders underwrite to. "
                    f"Sensitivity to sellout slippage or cost overruns is elevated."
                ),
                "source": "Pro Forma — Condo Sellout Summary",
                "evidence": f"Profit margin on cost: {pm*100:.1f}%",
            })
        elif pm >= 0.18:
            findings.append({
                "category": "market",
                "severity": "positive",
                "title": f"Strong Projected Margin ({pm*100:.1f}%)",
                "description": (
                    f"Projected profit margin on cost of {pm*100:.1f}% provides meaningful "
                    f"cushion to sellout or cost volatility."
                ),
                "source": "Pro Forma — Condo Sellout Summary",
                "evidence": f"Profit margin on cost: {pm*100:.1f}%",
            })

    # Comparable basis check
    if per_sf_sellout and isinstance(comps, list) and comps:
        prices_per_sf = []
        for c in comps:
            if not isinstance(c, dict):
                continue
            ppsf = c.get("price_per_sf") or c.get("per_sf")
            if ppsf:
                try:
                    prices_per_sf.append(float(ppsf))
                except (TypeError, ValueError):
                    pass
        if prices_per_sf:
            comp_avg = sum(prices_per_sf) / len(prices_per_sf)
            try:
                target = float(per_sf_sellout)
            except (TypeError, ValueError):
                target = 0
            if target and target > comp_avg * 1.10:
                findings.append({
                    "category": "market",
                    "severity": "warning",
                    "title": f"Projected Sellout Above Comps by {(target/comp_avg - 1)*100:.1f}%",
                    "description": (
                        f"Projected sellout of ${target:,.0f}/SF exceeds the average of "
                        f"{len(prices_per_sf)} comparable transactions (${comp_avg:,.0f}/SF) "
                        f"by {(target/comp_avg - 1)*100:.1f}%. Confirm comparables are "
                        f"current and adjustments for condition and finish are documented."
                    ),
                    "source": "Comparable Sales Analysis",
                    "evidence": f"Target ${target:,.0f}/SF vs comp avg ${comp_avg:,.0f}/SF",
                })
            elif target and target <= comp_avg * 1.05:
                findings.append({
                    "category": "market",
                    "severity": "positive",
                    "title": "Sellout Supported by Comparables",
                    "description": (
                        f"Projected sellout of ${target:,.0f}/SF is consistent with the "
                        f"{len(prices_per_sf)}-comp average of ${comp_avg:,.0f}/SF."
                    ),
                    "source": "Comparable Sales Analysis",
                    "evidence": f"Target ${target:,.0f}/SF vs comp avg ${comp_avg:,.0f}/SF",
                })

    if absorption:
        findings.append({
            "category": "market",
            "severity": "info",
            "title": f"Submarket Absorption: {absorption}",
            "description": (
                f"Submarket absorption rate referenced in the deal package at {absorption}. "
                f"Confirm the sellout schedule assumes a pace consistent with (or slower "
                f"than) this rate."
            ),
            "source": "Market Study / Appraisal",
            "evidence": f"Absorption rate: {absorption}",
        })


def _check_title(findings: list, sponsor_field, mc: dict) -> None:
    """Title / ownership reconciliation against ACRIS."""
    if not isinstance(mc, dict):
        return
    history = mc.get("property_history") or {}
    if not isinstance(history, dict):
        return

    owner = history.get("current_owner") or ""
    sponsor = _first_sponsor(sponsor_field)
    sponsor_name = sponsor.get("name") or sponsor.get("sponsor_name") or ""

    if owner and sponsor_name:
        if (
            owner.lower() not in sponsor_name.lower()
            and sponsor_name.lower() not in owner.lower()
        ):
            findings.append({
                "category": "title",
                "severity": "warning",
                "title": "ACRIS Owner Does Not Match Sponsor",
                "description": (
                    f"ACRIS shows the current property owner as '{owner}', while the deal "
                    f"package names '{sponsor_name}' as sponsor. Confirm the title path "
                    f"(assignment, ground lease, or sale at closing) before committee review."
                ),
                "source": "NYC ACRIS — Deed Record",
                "evidence": f"ACRIS owner: {owner}; deal sponsor: {sponsor_name}",
            })
    elif not owner:
        findings.append({
            "category": "title",
            "severity": "info",
            "title": "ACRIS Ownership Not Verified",
            "description": (
                "Current ACRIS ownership record not available in the deal package. "
                "Title review should be run prior to committee."
            ),
            "source": "Deal Package",
            "evidence": "property_history.current_owner unavailable",
        })

    liens = history.get("liens") or []
    if isinstance(liens, list) and liens:
        findings.append({
            "category": "title",
            "severity": "warning",
            "title": f"{len(liens)} Existing Lien(s) on Record",
            "description": (
                f"ACRIS shows {len(liens)} existing lien(s) on the subject property. "
                f"Confirm satisfaction/payoff schedule before funding."
            ),
            "source": "NYC ACRIS — Lien Record",
            "evidence": f"Liens: {liens[:3]}",
        })


def _check_environmental(findings: list, mc: dict) -> None:
    """Environmental review status."""
    if not isinstance(mc, dict):
        return
    env = mc.get("environmental") or {}
    phase1 = env.get("phase_1_report") if isinstance(env, dict) else None
    cleanup = env.get("cleanup_required") if isinstance(env, dict) else None

    if not phase1:
        findings.append({
            "category": "environmental",
            "severity": "info",
            "title": "Phase I ESA Not in Deal Package",
            "description": (
                "A Phase I Environmental Site Assessment is not included in the submitted "
                "package. Lender will require a Phase I and, depending on findings, "
                "potentially a Phase II prior to closing."
            ),
            "source": "Deal Package",
            "evidence": "No phase_1_report referenced in environmental record",
        })
    elif cleanup:
        findings.append({
            "category": "environmental",
            "severity": "warning",
            "title": "Environmental Remediation Noted",
            "description": (
                f"Phase I references required remediation: {cleanup}. Confirm scope, "
                f"cost estimate, and timing are carried in the construction budget and "
                f"schedule."
            ),
            "source": "Phase I ESA — Deal Package",
            "evidence": f"Cleanup required: {cleanup}",
        })


_STALE_SCREENING_MARKERS = (
    "no loan amount", "loan amount not", "loan amount missing",
    "loan amount unclear", "no equity", "equity contribution not",
    "equity not specified", "incomplete capital stack", "tdc not",
    "total development cost not", "unit count not", "unit count missing",
)


def _screening_risk_is_stale(risk_text: str, fm: dict) -> bool:
    """Return True if a screening risk is contradicted by the extracted
    financial model. Screening runs before extraction; once extraction has
    populated the loan amount, equity, and unit count, any screening
    complaint about those fields is obsolete and must be dropped before the
    risk report reaches a credit committee."""
    if not fm:
        return False
    text = (risk_text or "").lower()
    if not any(marker in text for marker in _STALE_SCREENING_MARKERS):
        return False
    loan = fm.get("loan_amount") or fm.get("sources_uses", {}).get("loan_amount")
    tdc = fm.get("total_development_cost")
    equity = fm.get("equity") or fm.get("sources_uses", {}).get("equity")
    units = fm.get("total_units")
    # If extraction produced loan + tdc + (equity or derivable), the screening
    # complaint is superseded.
    if loan and tdc and (equity or units):
        return True
    return False


def _screening_title(risk_text: str) -> str:
    """Turn a free-text screening risk into a credit-memo-style title."""
    text = (risk_text or "").strip()
    if not text:
        return "Screening Concern"
    # Take the first clause/sentence, title-case it, cap at ~70 chars.
    first = text.split(".")[0].split(";")[0].strip()
    if len(first) > 80:
        first = first[:77].rstrip() + "..."
    return first[:1].upper() + first[1:] if first else "Screening Concern"


def _append_agent_findings(findings: list, agent_runs, fm: dict | None = None) -> dict:
    """Fold analytical findings from screening and underwriting agents into
    the client-facing report. (NOT extraction telemetry or cross-reference
    telemetry — those are internal QA, not for the credit committee.)

    Stale screening findings that the extracted financial_model has
    superseded are filtered out here so the credit committee never sees a
    finding that contradicts the rest of the same document.
    """
    screening_data: dict = {}
    fm = fm or {}
    for run in agent_runs:
        result = run.result or {}
        if run.agent_name == "deal_screening_agent":
            screening_data = result
            for risk in result.get("key_risks", []) or []:
                risk_text = str(risk)
                if _screening_risk_is_stale(risk_text, fm):
                    continue
                findings.append({
                    "category": "screening",
                    "severity": "warning",
                    "title": _screening_title(risk_text),
                    "description": risk_text,
                    "source": "Initial Deal Screening",
                    "evidence": f"Screening recommendation: {result.get('recommendation', 'n/a')}",
                })
            for strength in result.get("key_strengths", []) or []:
                strength_text = str(strength)
                findings.append({
                    "category": "screening",
                    "severity": "positive",
                    "title": _screening_title(strength_text),
                    "description": strength_text,
                    "source": "Initial Deal Screening",
                    "evidence": f"Screening recommendation: {result.get('recommendation', 'n/a')}",
                })
        elif run.agent_name == "underwriting_review_agent":
            flags = result.get("flags") or result.get("underwriting_flags") or []
            for flag in flags if isinstance(flags, list) else []:
                if isinstance(flag, dict):
                    sev_raw = flag.get("severity", "warning")
                    sev = "critical" if sev_raw == "high" else "warning" if sev_raw == "medium" else "info"
                    findings.append({
                        "category": "underwriting",
                        "severity": sev,
                        "title": flag.get("title") or flag.get("flag") or "Underwriting Flag",
                        "description": flag.get("description") or flag.get("detail") or str(flag),
                        "source": "Underwriting Review",
                        "evidence": flag.get("evidence") or flag.get("basis") or "Financial model analysis",
                    })
                elif isinstance(flag, str):
                    findings.append({
                        "category": "underwriting",
                        "severity": "warning",
                        "title": "Underwriting Concern",
                        "description": flag,
                        "source": "Underwriting Review",
                        "evidence": "Financial model analysis",
                    })
    return screening_data


class CompileRiskFindingsTool(PlumbTool):
    """Compile client-facing risk findings from deal facts.

    Findings are drawn from the pro forma, appraisal, regulatory record,
    sponsor bio, ACRIS, DOB, and comparable sales — with a specific source
    citation on every finding. This is a credit-committee document, not an
    internal pipeline QA report.
    """

    name = "compile_risk_findings"
    description = (
        "Compile client-facing risk findings for a lender/investor risk report. "
        "Draws from the deal's financial model, regulatory record, market comps, "
        "sponsor bio, and public records. Every finding cites its source document "
        "or record. Categories: capital_stack, construction, zoning, sponsor, "
        "market, title, environmental, screening, underwriting."
    )

    def get_input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "deal_id": {
                    "type": "string",
                    "description": "The deal ID to compile findings for.",
                },
            },
            "required": ["deal_id"],
        }

    async def execute(self, _ctx: ToolContext | None = None, **kwargs) -> ToolResult:
        deal_id_str = kwargs.get("deal_id") or (str(_ctx.deal_id) if _ctx and _ctx.deal_id else None)
        if not deal_id_str:
            return ToolResult(success=False, error="deal_id is required")

        deal_uuid = uuid.UUID(deal_id_str)
        db = _ctx.db if _ctx else None
        if not db:
            return ToolResult(success=False, error="Database session required")

        from app.models.deal import Deal
        deal_result = await db.execute(select(Deal).where(Deal.id == deal_uuid))
        deal = deal_result.scalar_one_or_none()
        if not deal:
            return ToolResult(success=False, error=f"Deal {deal_id_str} not found")

        fm = (deal.typed_extension or {}).get("financial_model") or {}
        mc = deal.market_context or {}
        reg = deal.regulatory or {}
        sponsor = _first_sponsor(deal.sponsor)

        findings: list[dict] = []

        # Deal-fact-based findings (the core of the client-facing report).
        _check_capital_stack(findings, fm)
        _check_construction(findings, fm)
        _check_zoning(findings, reg, mc)
        _check_sponsor(findings, sponsor, mc)
        _check_market(findings, fm, mc)
        _check_title(findings, deal.sponsor, mc)
        _check_environmental(findings, mc)

        # Analytical findings from screening and underwriting agents.
        from app.models.agent import AgentRun
        runs_result = await db.execute(
            select(AgentRun)
            .where(AgentRun.deal_id == deal_uuid)
            .order_by(AgentRun.completed_at.asc())
        )
        screening_data = _append_agent_findings(findings, runs_result.scalars().all(), fm)

        return ToolResult(
            success=True,
            data={
                "deal_id": deal_id_str,
                "property_name": deal.property_name or "",
                "property_address": _reconciled_address(deal),
                "screening": screening_data,
                "financial_model": fm,
                "findings": findings,
            },
        )


class GenerateRiskNarrativeTool(PlumbTool):
    """Generate the executive summary narrative for the risk report."""

    name = "generate_risk_narrative"
    description = (
        "Generate an executive risk summary narrative. Takes compiled findings and "
        "produces: overall_risk_rating, risk_summary text, and any additional context."
    )

    def get_input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "findings_summary": {
                    "type": "string",
                    "description": "JSON summary of compiled findings from compile_risk_findings.",
                },
                "overall_risk_rating": {
                    "type": "string",
                    "enum": ["high", "medium", "low"],
                    "description": "Your assessment of overall risk level.",
                },
                "risk_summary": {
                    "type": "string",
                    "description": "2-4 sentence executive summary of the risk assessment.",
                },
            },
            "required": ["overall_risk_rating", "risk_summary"],
        }

    async def execute(self, _ctx: ToolContext | None = None, **kwargs) -> ToolResult:
        # This tool is a pass-through: the agent reasons about findings and
        # provides the risk rating and summary as tool input. We just validate
        # and return it structured for the render step.
        rating = kwargs.get("overall_risk_rating", "medium")
        summary = kwargs.get("risk_summary", "")

        if rating not in ("high", "medium", "low"):
            rating = "medium"

        return ToolResult(
            success=True,
            data={
                "overall_risk_rating": rating,
                "risk_summary": summary,
            },
        )


class RenderRiskPDFTool(PlumbTool):
    """Render the Risk Assessment Report as a PDF."""

    name = "render_risk_pdf"
    description = (
        "Render the Risk Assessment Report PDF from compiled findings and narrative. "
        "Produces a portrait-format PDF with the same Plumb branding as the OM."
    )

    def get_input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "deal_id": {
                    "type": "string",
                    "description": "The deal ID.",
                },
                "overall_risk_rating": {
                    "type": "string",
                    "enum": ["high", "medium", "low"],
                    "description": "Overall risk rating.",
                },
                "risk_summary": {
                    "type": "string",
                    "description": "Executive summary narrative.",
                },
                "findings": {
                    "type": "array",
                    "description": "List of risk findings from compile_risk_findings.",
                    "items": {"type": "object"},
                },
                "screening": {
                    "type": "object",
                    "description": "Screening agent results (used for the credit recommendation block).",
                },
            },
            "required": ["deal_id", "overall_risk_rating", "risk_summary", "findings"],
        }

    async def execute(self, _ctx: ToolContext | None = None, **kwargs) -> ToolResult:
        deal_id_str = kwargs.get("deal_id") or (str(_ctx.deal_id) if _ctx and _ctx.deal_id else None)
        if not deal_id_str:
            return ToolResult(success=False, error="deal_id is required")

        deal_uuid = uuid.UUID(deal_id_str)
        db = _ctx.db if _ctx else None
        if not db:
            return ToolResult(success=False, error="Database session required")

        # Load deal for property info and financial model
        from app.models.deal import Deal
        deal_result = await db.execute(select(Deal).where(Deal.id == deal_uuid))
        deal = deal_result.scalar_one_or_none()
        if not deal:
            return ToolResult(success=False, error=f"Deal {deal_id_str} not found")

        fm = (deal.typed_extension or {}).get("financial_model", {})
        screening = kwargs.get("screening", {})
        raw_findings = kwargs.get("findings", [])

        # Safety net: if the agent forgot to pass findings, re-compile them.
        if not raw_findings:
            compile_tool = CompileRiskFindingsTool()
            compile_result = await compile_tool.execute(_ctx=_ctx, deal_id=deal_id_str)
            if compile_result.success and compile_result.data:
                raw_findings = compile_result.data.get("findings", [])
                if not screening:
                    screening = compile_result.data.get("screening", {})

        # Build RiskContext
        from app.risk.schemas import RiskContext, RiskFinding

        findings = []
        for f in raw_findings:
            if isinstance(f, dict):
                findings.append(RiskFinding(
                    category=f.get("category", "info"),
                    severity=f.get("severity", "info"),
                    title=f.get("title", ""),
                    description=f.get("description", ""),
                    source=f.get("source", ""),
                    evidence=f.get("evidence", ""),
                    recommendation=f.get("recommendation", ""),
                ))

        condo = fm.get("condo_sellout", {})
        ctx = RiskContext(
            deal_id=deal_id_str,
            property_name=deal.property_name or "",
            property_address=_reconciled_address(deal),
            deal_type_label="CONSTRUCTION FINANCING",
            overall_risk_rating=kwargs.get("overall_risk_rating", "medium"),
            risk_summary=kwargs.get("risk_summary", ""),
            screening_recommendation=screening.get("recommendation", ""),
            screening_confidence=screening.get("confidence", 0),
            screening_strengths=screening.get("key_strengths", []),
            screening_risks=screening.get("key_risks", []),
            screening_missing=screening.get("missing_information", []),
            loan_amount=fm.get("loan_amount", 0),
            total_development_cost=fm.get("total_development_cost", 0),
            ltc=fm.get("ltc", 0),
            equity=fm.get("sources_uses", {}).get("equity", fm.get("equity", 0)),
            total_units=fm.get("total_units", 0),
            gross_sellout=condo.get("projected_sellout", 0),
            profit_margin=condo.get("profit_margin_on_cost", 0),
            findings=findings,
        )

        # Render PDF
        try:
            from app.risk.builder import build_risk_report
            pdf_bytes, page_count, html_pages = await asyncio.to_thread(
                build_risk_report, ctx,
            )
        except Exception as e:
            logger.exception("Risk report rendering failed for deal %s", deal_id_str)
            return ToolResult(success=False, error=f"PDF rendering failed: {e}")

        # Upload to S3 — fail loud on errors so the agent can retry.
        from app.storage.s3 import upload_bytes
        from app.models.risk import RiskReport

        max_version_result = await db.execute(
            select(func.max(RiskReport.version_number)).where(
                RiskReport.deal_id == deal_uuid
            )
        )
        max_version = max_version_result.scalar() or 0
        version_number = max_version + 1

        pdf_key = f"deals/{deal_id_str}/risk/v{version_number}/risk_report.pdf"
        pages_key = f"deals/{deal_id_str}/risk/v{version_number}/pages.json"

        try:
            await asyncio.to_thread(
                upload_bytes, pdf_bytes, pdf_key, "application/pdf",
            )
            if html_pages:
                await asyncio.to_thread(
                    upload_bytes,
                    json.dumps(html_pages).encode(),
                    pages_key,
                    "application/json",
                )
        except Exception as e:
            logger.exception("Risk PDF upload failed for deal %s", deal_id_str)
            return ToolResult(
                success=False,
                error=f"Risk PDF upload failed: {e}",
            )

        # Mark previous versions as superseded and persist new version.
        from sqlalchemy import update as sa_update

        await db.execute(
            sa_update(RiskReport)
            .where(
                RiskReport.deal_id == deal_uuid,
                RiskReport.status == "ready",
            )
            .values(status="superseded")
        )

        report = RiskReport(
            deal_id=deal_uuid,
            version_number=version_number,
            s3_key=pdf_key,
            html_s3_key=pages_key if html_pages else None,
            page_count=page_count,
            file_size=len(pdf_bytes),
            overall_risk_rating=ctx.overall_risk_rating,
            risk_summary=ctx.risk_summary,
            findings_count=len(findings),
            findings_snapshot=[f.model_dump() for f in findings],
            status="ready",
        )
        db.add(report)
        await db.flush()

        return ToolResult(
            success=True,
            data={
                "deal_id": deal_id_str,
                "version_number": version_number,
                "page_count": page_count,
                "file_size_bytes": len(pdf_bytes),
                "s3_key": pdf_key,
                "overall_risk_rating": ctx.overall_risk_rating,
                "findings_count": len(findings),
            },
        )
