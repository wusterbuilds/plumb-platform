"""Investment Highlights narrative prompt for the OM Executive Summary."""

from dataclasses import dataclass, field

from app.prompts.base import PromptDefinition

SYSTEM_PROMPT = (
    "You are a senior capital markets analyst writing the Investment Highlights "
    "section of a confidential financing memorandum for a commercial real estate "
    "construction loan.\n\n"
    "Produce 3-4 themed highlight sections. Each has a short uppercase header "
    "(max 8 words) and 1 tight paragraph of body text. Write in formal, "
    "third-person, factual style.\n\n"
    "HARD WORD BUDGET: Each highlight body MUST be 50-65 words. Total across "
    "4 highlights MUST be 200-260 words. Longer text is clipped by the page "
    "layout. Err shorter, never longer. Count your words before returning.\n\n"
    "CRITICAL RULES:\n"
    "- EVERY highlight body MUST contain specific numbers: dollar amounts, "
    "percentages, unit counts, square footages, project names. A highlight "
    "without at least 3 concrete data points is unacceptable.\n"
    "- NEVER use vague qualifiers like 'significant', 'substantial', 'considerable', "
    "'extensive', or 'strong' when a specific number is available. Write "
    "'The sponsor has developed 890 units across 5 projects totaling over $1B' "
    "not 'the sponsor has extensive experience in the market'.\n"
    "- For sponsor track record: cite specific project names, unit counts, "
    "dollar values, and years. Name the projects.\n"
    "- For condo/for-sale deals: emphasize sellout metrics (gross sellout, "
    "profit margin, per-unit sellout, per-SF sellout) over rental metrics.\n"
    "- For comparable sales: reference specific comp prices to support basis.\n"
    "- Do not invent or hallucinate any figures — use only what is provided.\n\n"
    "Select the 3-4 most relevant themes:\n"
    "- EXPERIENCED SPONSOR / DEVELOPER TRACK RECORD — cite specific completed "
    "projects by name, total units developed, total development value in dollars\n"
    "- ATTRACTIVE DEBT BASIS / FAVORABLE LOAN METRICS — LTC percentage, "
    "basis per unit vs. sellout per unit, cost per SF vs. comp sale prices\n"
    "- STRONG MARKET FUNDAMENTALS / DEMAND DRIVERS — submarket demand, "
    "population growth, supply constraints, transit access, comparable prices\n"
    "- TAX INCENTIVE / ABATEMENT BENEFITS — 421(a), IDA, or other tax benefits "
    "with estimated annual savings or abatement period\n"
    "- FAVORABLE ZONING / ENTITLEMENTS — as-of-right, rezoning details (from/to "
    "district), MIH overlay, ULURP approval dates\n"
    "- ATTRACTIVE SELLOUT / RETURN METRICS — gross sellout, profit margin on "
    "cost, return on equity, per-unit and per-SF sellout vs. comparables"
)

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "highlights": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "header": {"type": "string"},
                    "body": {"type": "string"},
                },
                "required": ["header", "body"],
            },
            "minItems": 3,
            "maxItems": 4,
        }
    },
    "required": ["highlights"],
}


def _fmt_currency(value) -> str:
    if value is None:
        return "N/A"
    try:
        return f"${float(value):,.0f}"
    except (TypeError, ValueError):
        return str(value)


def _fmt_pct(value) -> str:
    if value is None:
        return "N/A"
    try:
        return f"{float(value) * 100:.1f}%"
    except (TypeError, ValueError):
        return str(value)


@dataclass
class InvestmentHighlightsPrompt(PromptDefinition):
    name: str = "generate_investment_highlights"
    version: str = "2.0.0"
    model: str = "claude-sonnet-4-6"
    system_prompt: str = SYSTEM_PROMPT
    max_output_tokens: int = 4096
    temperature: float = 0.3
    output_schema: dict = field(default_factory=lambda: OUTPUT_SCHEMA)

    def build_input(self, deal_context: dict, task_data: dict) -> list[dict]:
        """Build user message with deal highlights data.

        deal_context is pre-built by _build_deal_context() with all relevant
        fields surfaced at the top level.
        """
        dc = deal_context
        fm = task_data.get("financial_model", {})
        valuation = fm.get("valuation", {}) if fm else {}
        mc = dc.get("market_context", {})

        loan_amount = dc.get("loan_amount")
        tdc = dc.get("total_development_cost")
        ltc = dc.get("ltc")
        units = dc.get("units")
        gsf = dc.get("gsf")

        has_condo_data = bool(dc.get("gross_sellout") or dc.get("per_unit_sellout") or fm.get("condo_sellout"))
        is_condo = dc.get("deal_type") == "condo_sellout" or has_condo_data

        # Cost per unit / per SF
        cost_per_unit = dc.get("per_unit_cost")
        if not cost_per_unit and tdc and units:
            try:
                cost_per_unit = float(tdc) / int(units)
            except (TypeError, ValueError, ZeroDivisionError):
                cost_per_unit = None

        cost_per_sf = dc.get("per_sf_cost")
        if not cost_per_sf and tdc and gsf:
            try:
                cost_per_sf = float(tdc) / float(gsf)
            except (TypeError, ValueError, ZeroDivisionError):
                cost_per_sf = None

        lines = [
            "Write Investment Highlights based on the following deal data.",
            "IMPORTANT: Every highlight must cite specific numbers. Never use vague language.",
            "",
            f"Property Name: {dc.get('property_name', 'N/A')}",
            f"Property Address: {dc.get('property_address', 'N/A')}",
            f"Borough / Neighborhood: {dc.get('borough', 'N/A')} / {dc.get('neighborhood', 'N/A')}",
            f"Deal Type: {'Condominium Construction' if is_condo else dc.get('deal_type', 'Construction')}",
        ]

        # --- Sponsor track record (detailed) ---
        lines.extend([
            "",
            "--- Sponsor Track Record ---",
            f"Sponsor(s): {dc.get('sponsor_names', 'N/A')}",
            f"Sponsor Entity: {dc.get('sponsor_entity', 'N/A')}",
        ])

        principals = dc.get("principal_names", [])
        if principals:
            if isinstance(principals, list):
                lines.append(f"Principal(s): {', '.join(str(p) for p in principals)}")
            else:
                lines.append(f"Principal(s): {principals}")

        lines.append(f"Years of Experience: {dc.get('sponsor_experience', 'N/A')}")
        lines.append(f"Total Units Developed: {dc.get('total_units_developed', 'N/A')}")
        lines.append(f"Total Development Value: {_fmt_currency(dc.get('total_development_value'))}")

        # Completed projects — list each with details
        completed = dc.get("completed_projects", [])
        if completed and isinstance(completed, list):
            lines.append("")
            lines.append("Completed Projects (use these specific names and figures):")
            for p in completed:
                if isinstance(p, dict):
                    name = p.get("name", p.get("project_name", "Unnamed"))
                    detail = f"  - {name}"
                    if p.get("location"):
                        detail += f", {p['location']}"
                    if p.get("units"):
                        detail += f", {p['units']} units"
                    if p.get("sf"):
                        sf = p["sf"]
                        detail += f", {sf:,} SF" if isinstance(sf, (int, float)) else f", {sf} SF"
                    if p.get("value"):
                        detail += f", {_fmt_currency(p['value'])}"
                    if p.get("year_completed"):
                        detail += f" ({p['year_completed']})"
                    lines.append(detail)
                else:
                    lines.append(f"  - {p}")

        # Current projects
        current = dc.get("current_projects", [])
        if current and isinstance(current, list):
            lines.append("")
            lines.append("Current Projects:")
            for p in current:
                if isinstance(p, dict):
                    name = p.get("name", p.get("project_name", "Unnamed"))
                    detail = f"  - {name}"
                    if p.get("units"):
                        detail += f", {p['units']} units"
                    if p.get("status"):
                        detail += f" [{p['status']}]"
                    lines.append(detail)
                else:
                    lines.append(f"  - {p}")

        # --- Loan & cost metrics ---
        lines.extend([
            "",
            "--- Loan & Cost Metrics ---",
            f"Loan Amount: {_fmt_currency(loan_amount)}",
            f"Total Development Cost: {_fmt_currency(tdc)}",
            f"Loan-to-Cost: {_fmt_pct(ltc)}",
            f"Equity Contribution: {_fmt_currency(dc.get('equity'))}",
            f"Cost per Unit: {_fmt_currency(cost_per_unit)}",
            f"Cost per GSF: {_fmt_currency(cost_per_sf)}",
        ])

        # --- Project details ---
        lines.extend([
            "",
            "--- Project ---",
            f"Total Units: {units or 'N/A'}",
            f"GSF: {gsf or 'N/A'}",
            f"Zoning: {dc.get('zoning', 'N/A')}",
        ])

        special = dc.get("special_district")
        if special:
            lines.append(f"Special District: {special}")

        # Zoning detail from market enrichment
        zoning_detail = dc.get("zoning_detail", {})
        if isinstance(zoning_detail, dict):
            for key in ("rezoning_info", "prior_zoning", "ulurp_number", "approval_date", "mih_option"):
                val = zoning_detail.get(key)
                if val:
                    lines.append(f"{key.replace('_', ' ').title()}: {val}")

        # Regulatory/zoning from deal.regulatory
        reg = dc.get("regulatory") or {}
        if isinstance(reg, dict):
            for key in ("mih_option", "affordable_percentage", "approved_far", "approval_date", "ulurp_numbers"):
                val = reg.get(key)
                if val:
                    lines.append(f"{key.replace('_', ' ').title()}: {val}")

        lines.append(f"Tax Abatement: {dc.get('abatement_program') or 'None'}")

        # --- Sellout / return metrics ---
        if is_condo:
            lines.extend([
                "",
                "--- Condo Sellout Metrics (PRIMARY — emphasize these over rental metrics) ---",
                f"Gross Sellout: {_fmt_currency(dc.get('gross_sellout'))}",
                f"Developer Profit: {_fmt_currency(dc.get('profit'))}",
                f"Profit Margin on Cost: {_fmt_pct(dc.get('profit_margin'))}",
                f"Per-Unit Sellout: {_fmt_currency(dc.get('per_unit_sellout'))}",
                f"Per-SF Sellout: {_fmt_currency(dc.get('per_sf_sellout'))}",
                f"Return on Equity: {_fmt_pct(dc.get('return_on_equity'))}",
                f"Appraised Value: {_fmt_currency(dc.get('appraised_value'))}",
                f"Loan-to-Value: {_fmt_pct(dc.get('ltv'))}",
            ])
        else:
            lines.extend([
                "",
                "--- Stabilized Returns ---",
                f"Stabilized Value: {_fmt_currency(dc.get('stabilized_value') or valuation.get('stabilized_value'))}",
                f"NOI: {_fmt_currency(dc.get('noi') or valuation.get('noi'))}",
                f"Cap Rate: {_fmt_pct(dc.get('cap_rate') or valuation.get('cap_rate'))}",
                f"DSCR: {dc.get('dscr') or valuation.get('dscr', 'N/A')}",
                f"Debt Yield: {_fmt_pct(dc.get('debt_yield') or valuation.get('debt_yield'))}",
            ])

        # --- Comparable sales ---
        comps = dc.get("comparable_sales", [])
        if comps and isinstance(comps, list):
            lines.append("")
            lines.append("--- Comparable Sales (reference these to support basis) ---")
            for i, comp in enumerate(comps[:8], 1):
                if isinstance(comp, dict):
                    addr = comp.get("address", comp.get("name", f"Comp {i}"))
                    price = comp.get("price", comp.get("sale_price", comp.get("price_per_sf")))
                    units_c = comp.get("units", "")
                    ppsf = comp.get("price_per_sf", comp.get("per_sf", ""))
                    date = comp.get("date", comp.get("sale_date", ""))
                    detail = f"  {i}. {addr}"
                    if price:
                        detail += f" — {_fmt_currency(price)}"
                    if units_c:
                        detail += f", {units_c} units"
                    if ppsf:
                        detail += f", ${float(ppsf):,.0f}/SF" if isinstance(ppsf, (int, float)) else f", {ppsf}/SF"
                    if date:
                        detail += f" ({date})"
                    lines.append(detail)
                else:
                    lines.append(f"  {i}. {comp}")

        # --- Market highlights ---
        market_highlights = mc.get("highlights")
        if market_highlights:
            lines.append("")
            lines.append("--- Market Context ---")
            if isinstance(market_highlights, list):
                for h in market_highlights:
                    lines.append(f"- {h}")
            else:
                lines.append(str(market_highlights))

        return [{"role": "user", "content": "\n".join(lines)}]

    def validate_output(self, result: dict) -> tuple[bool, list[str]]:
        errors: list[str] = []
        highlights = result.get("highlights")
        if highlights is None:
            errors.append("Missing 'highlights' in output")
            return (False, errors)
        if isinstance(highlights, dict):
            highlights = [highlights]
            result["highlights"] = highlights
        if not isinstance(highlights, list):
            errors.append("'highlights' must be a list")
            return (False, errors)
        if len(highlights) < 3 or len(highlights) > 4:
            errors.append(f"Expected 3-4 highlights, got {len(highlights)}")
        total_body_words = 0
        for i, h in enumerate(highlights):
            if not isinstance(h, dict):
                errors.append(f"Highlight {i + 1} must be a dict")
                continue
            if not h.get("header"):
                errors.append(f"Highlight {i + 1} missing 'header'")
            body = h.get("body") or ""
            if not body:
                errors.append(f"Highlight {i + 1} missing 'body'")
                continue
            wc = len(body.split())
            total_body_words += wc
            if wc > 75:
                errors.append(
                    f"Highlight {i + 1} body is {wc} words, exceeds 65-word hard limit (would overflow page). Rewrite shorter."
                )
        if total_body_words > 280:
            errors.append(
                f"Total highlight body length {total_body_words} words exceeds 260-word page budget. Rewrite shorter."
            )
        return (len(errors) == 0, errors)
