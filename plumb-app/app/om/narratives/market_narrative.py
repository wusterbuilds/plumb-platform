"""Market Narrative prompt for the OM Market Overview section."""

from dataclasses import dataclass, field

from app.prompts.base import PromptDefinition

SYSTEM_PROMPT = (
    "You are a senior capital markets analyst writing the Market Overview "
    "section of a confidential financing memorandum for a commercial real "
    "estate construction loan.\n\n"
    "Produce 2 subsections about the submarket. Each subsection has a short "
    "header (max 6 words, title case) and a tight body of 100-120 words. "
    "Write in formal, third-person, factual style.\n\n"
    "HARD WORD BUDGET: Each subsection body MUST be 100-120 words. Total "
    "across both subsections MUST be 200-240 words. Longer text is clipped "
    "by the page layout. Err shorter, never longer. Count your words before "
    "returning.\n\n"
    "CRITICAL RULES:\n"
    "- Use SPECIFIC data points: name the neighborhood and borough, cite "
    "specific comparable sale prices, reference specific transit lines, "
    "name specific zoning districts and rezoning actions.\n"
    "- NEVER use vague qualifiers like 'significant', 'substantial', "
    "'growing', or 'robust' without a supporting number or specific fact.\n"
    "- For condo/for-sale deals, reference comparable condo sale prices "
    "(per-unit and per-SF) rather than rental comps.\n"
    "- When market conditions or appraiser assessments are provided, "
    "incorporate their specific language and conclusions.\n"
    "- Do not invent or hallucinate statistics — use only what is provided.\n"
    "- LOCATION FACTS: The only geographic names you may use are the ones in "
    "the Borough, Neighborhood, Zoning District, Special District, and "
    "Transit Access fields below, plus any names that appear inside comp "
    "addresses or the appraiser market assessment text. Do NOT infer the "
    "city, state, county, or submarket from the property name — the property "
    "name is a marketing label, not an address. Never write 'Union County', "
    "'New Jersey', 'NJ Transit', etc. unless those exact strings are in the "
    "data below. If Borough disagrees with Property Address, trust Borough.\n\n"
    "Focus on:\n"
    "- Growth drivers: population trends, employment hubs, major employers, "
    "university proximity — with specific names and numbers\n"
    "- Location advantages: transit access (name specific subway lines, "
    "stations, distances), highway connectivity, landmarks\n"
    "- Zoning and entitlements: specific zoning district (e.g., R7A), "
    "rezoning history (from what to what), MIH overlay details, ULURP "
    "approval dates\n"
    "- Comparable market evidence: specific comparable sales with addresses, "
    "prices, and per-SF metrics that support project pricing\n"
    "- Supply and demand dynamics: vacancy rates, absorption rates, "
    "pipeline projects, barriers to entry\n\n"
    "Each subsection body should be a single string with paragraphs separated "
    "naturally. Keep the tone confident but measured — this is a debt pitch, "
    "not equity marketing."
)

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "sections": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "header": {"type": "string"},
                    "body": {"type": "string"},
                },
                "required": ["header", "body"],
            },
            "minItems": 2,
            "maxItems": 2,
        }
    },
    "required": ["sections"],
}


@dataclass
class MarketNarrativePrompt(PromptDefinition):
    name: str = "generate_market_narrative"
    version: str = "2.0.0"
    model: str = "claude-sonnet-4-6"
    system_prompt: str = SYSTEM_PROMPT
    max_output_tokens: int = 4096
    temperature: float = 0.3
    output_schema: dict = field(default_factory=lambda: OUTPUT_SCHEMA)

    def build_input(self, deal_context: dict, task_data: dict) -> list[dict]:
        """Build user message with market context data.

        deal_context is pre-built by _build_deal_context() and carries
        market_context, zoning, comparable_sales, and neighborhood data
        at the top level.  task_data carries the raw market_context dict.
        """
        dc = deal_context
        # Use market_context from deal_context (preferred) or task_data fallback
        mc = dc.get("market_context", {}) or task_data.get("market_context", {})

        fm = task_data.get("financial_model", {})
        has_condo_data = bool(dc.get("gross_sellout") or dc.get("per_unit_sellout") or fm.get("condo_sellout"))
        is_condo = dc.get("deal_type") == "condo_sellout" or has_condo_data

        lines = [
            "Write a Market Overview based on the following submarket data.",
            "IMPORTANT: Reference specific names, numbers, and addresses. "
            "Never use vague qualifiers without supporting data.",
            "",
            f"Property Name: {dc.get('property_name', 'N/A')}",
            f"Property Address: {dc.get('property_address', 'N/A')}",
            f"Borough: {dc.get('borough', 'N/A')}",
            f"Neighborhood: {dc.get('neighborhood') or mc.get('neighborhood', 'N/A')}",
            f"Deal Type: {'Condominium Development' if is_condo else dc.get('deal_type', 'Construction')}",
            f"Total Units: {dc.get('units', 'N/A')}",
            "",
            "--- Zoning & Entitlements ---",
            f"Zoning District: {dc.get('zoning') or mc.get('zoning_district', 'N/A')}",
        ]

        # Special district
        special = dc.get("special_district")
        if special:
            lines.append(f"Special District: {special}")

        # Zoning detail from market enrichment
        zoning_detail = dc.get("zoning_detail", {})
        if isinstance(zoning_detail, dict):
            for key in ("rezoning_info", "prior_zoning", "ulurp_number", "approval_date",
                        "mih_option", "community_board", "environmental_review"):
                val = zoning_detail.get(key)
                if val:
                    lines.append(f"{key.replace('_', ' ').title()}: {val}")

        # Regulatory data from deal.regulatory
        reg = dc.get("regulatory") or {}
        if isinstance(reg, dict):
            for key in ("mih_option", "affordable_percentage", "approved_far",
                        "approval_date", "ulurp_numbers", "conditions", "variance_granted"):
                val = reg.get(key)
                if val:
                    lines.append(f"{key.replace('_', ' ').title()}: {val}")

        # Fallback to mc for zoning fields
        for key in ("rezoning_info", "opportunity_zone"):
            val = mc.get(key)
            if val and val != "N/A":
                lines.append(f"{key.replace('_', ' ').title()}: {val}")

        lines.append(f"Tax Abatement: {dc.get('abatement_program') or 'None'}")

        # Transit access
        transit = mc.get("transit_access")
        if transit:
            lines.append("")
            lines.append("--- Transit Access ---")
            if isinstance(transit, list):
                for t in transit:
                    if isinstance(t, dict):
                        lines.append(f"- {t.get('type', '')}: {t.get('name', '')} ({t.get('distance', '')})")
                    else:
                        lines.append(f"- {t}")
            elif isinstance(transit, str):
                lines.append(transit)

        # Development pipeline
        pipeline = mc.get("development_pipeline")
        if pipeline:
            lines.append("")
            lines.append("--- Development Pipeline ---")
            if isinstance(pipeline, list):
                for p in pipeline:
                    if isinstance(p, dict):
                        lines.append(f"- {p.get('project', '')}: {p.get('units', 'N/A')} units, {p.get('status', 'N/A')}")
                    else:
                        lines.append(f"- {p}")
            elif isinstance(pipeline, str):
                lines.append(pipeline)

        # Market stats
        lines.append("")
        lines.append("--- Market Statistics ---")
        lines.append(f"Vacancy Rate: {mc.get('vacancy_rate', 'N/A')}")
        lines.append(f"Median Rent: {mc.get('median_rent', 'N/A')}")
        lines.append(f"Population Growth: {mc.get('population_growth', 'N/A')}")

        # Market conditions (from appraiser)
        market_conditions = mc.get("market_conditions")
        if market_conditions:
            lines.append("")
            lines.append("--- Appraiser Market Assessment ---")
            lines.append(str(market_conditions))

        # Absorption rate
        absorption = mc.get("absorption_rate")
        if absorption:
            lines.append(f"Absorption Rate: {absorption}")

        # Major employers
        employers = mc.get("major_employers")
        if employers:
            lines.append(f"Major Employers: {', '.join(employers) if isinstance(employers, list) else employers}")

        # Additional highlights
        highlights = mc.get("highlights")
        if highlights:
            lines.append("")
            lines.append("--- Additional Highlights ---")
            if isinstance(highlights, list):
                for h in highlights:
                    lines.append(f"- {h}")
            else:
                lines.append(str(highlights))

        # --- Comparable sales (for condo deals, this is primary evidence) ---
        comps = dc.get("comparable_sales", [])
        if comps and isinstance(comps, list):
            lines.append("")
            label = "Comparable Condo Sales" if is_condo else "Comparable Sales"
            lines.append(f"--- {label} (cite these specific transactions) ---")
            for i, comp in enumerate(comps[:10], 1):
                if isinstance(comp, dict):
                    addr = comp.get("address", comp.get("name", f"Comp {i}"))
                    price = comp.get("price", comp.get("sale_price"))
                    units_c = comp.get("units", "")
                    ppsf = comp.get("price_per_sf", comp.get("per_sf", ""))
                    date = comp.get("date", comp.get("sale_date", ""))
                    detail = f"  {i}. {addr}"
                    if price:
                        try:
                            detail += f" — ${float(price):,.0f}"
                        except (TypeError, ValueError):
                            detail += f" — {price}"
                    if units_c:
                        detail += f", {units_c} units"
                    if ppsf:
                        try:
                            detail += f", ${float(ppsf):,.0f}/SF"
                        except (TypeError, ValueError):
                            detail += f", {ppsf}/SF"
                    if date:
                        detail += f" ({date})"
                    lines.append(detail)
                else:
                    lines.append(f"  {i}. {comp}")

        # Rental comp data (for rental deals)
        if not is_condo:
            rent_comps = mc.get("comps", [])
            if rent_comps and isinstance(rent_comps, list):
                lines.append("")
                lines.append("--- Rental Comp Summary ---")
                lines.append(f"Number of comps: {len(rent_comps)}")
                avg_rents = []
                for c in rent_comps:
                    rents = c.get("rents", [])
                    for r in rents:
                        rent_val = r.get("rent")
                        if rent_val:
                            try:
                                avg_rents.append(float(str(rent_val).replace("$", "").replace(",", "")))
                            except ValueError:
                                pass
                if avg_rents:
                    lines.append(f"Average comp rent: ${sum(avg_rents) / len(avg_rents):,.0f}")

        return [{"role": "user", "content": "\n".join(lines)}]

    def validate_output(self, result: dict) -> tuple[bool, list[str]]:
        errors: list[str] = []
        sections = result.get("sections")
        if sections is None:
            errors.append("Missing 'sections' in output")
            return (False, errors)
        if isinstance(sections, dict):
            sections = [sections]
            result["sections"] = sections
        if not isinstance(sections, list):
            errors.append("'sections' must be a list")
            return (False, errors)
        if len(sections) != 2:
            errors.append(f"Expected 2 sections, got {len(sections)}")
        total_body_words = 0
        for i, s in enumerate(sections):
            if not isinstance(s, dict):
                errors.append(f"Section {i + 1} must be a dict")
                continue
            if not s.get("header"):
                errors.append(f"Section {i + 1} missing 'header'")
            body = s.get("body") or ""
            if not body:
                errors.append(f"Section {i + 1} missing 'body'")
                continue
            wc = len(body.split())
            total_body_words += wc
            if wc > 135:
                errors.append(
                    f"Section {i + 1} body is {wc} words, exceeds 120-word hard limit (would overflow page). Rewrite shorter."
                )
        if total_body_words > 260:
            errors.append(
                f"Total market narrative body {total_body_words} words exceeds 240-word page budget. Rewrite shorter."
            )
        return (len(errors) == 0, errors)
