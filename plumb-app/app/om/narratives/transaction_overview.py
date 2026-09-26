"""Transaction Overview narrative prompt for the OM Executive Summary."""

from dataclasses import dataclass, field

from app.prompts.base import PromptDefinition

SYSTEM_PROMPT = (
    "You are a senior capital markets analyst writing the Transaction Overview "
    "section of a confidential financing memorandum for a commercial real estate "
    "construction loan. Write in formal, third-person, factual style.\n\n"
    "HARD WORD BUDGET: Each paragraph MUST be 95-115 words. The total across "
    "all 3 paragraphs MUST be between 285 and 340 words. This is a physical "
    "layout constraint — longer text is clipped by the page. Err shorter, "
    "never longer. Count your words before returning.\n\n"
    "CRITICAL RULES:\n"
    "- Use SPECIFIC numbers from the data provided: dollar amounts, percentages, "
    "unit counts, square footages. Every paragraph must contain at least 2-3 "
    "concrete figures.\n"
    "- NEVER use vague qualifiers like 'significant', 'substantial', 'considerable', "
    "'extensive', 'attractive', or 'strong' when a number is available. Write "
    "'$180,000,000' not 'a significant loan amount'.\n"
    "- Do not invent or hallucinate any figures — use only what is provided.\n"
    "- LOCATION FACTS: Use ONLY the Property Address, Borough, and Neighborhood "
    "fields provided below. Do NOT infer city, state, county, or submarket from "
    "the property name. The property name is a marketing label (e.g., 'Linden "
    "Villa', 'Hudson Commons') and tells you nothing about where the building "
    "physically sits. Never write phrases like 'Union County, New Jersey' or "
    "'served by NJ Transit' unless they appear verbatim in the fields below. "
    "If Borough and Property Address disagree, trust the Borough field and "
    "refer to the project as 'the subject property in [Borough]' without "
    "naming a county or state you had to guess.\n"
    "- For condo/for-sale deals, emphasize sellout metrics (gross sellout, profit "
    "margin, per-unit sellout) NOT rental metrics (NOI, cap rate, DSCR).\n"
    "- Be concise. Use active voice and short sentences. Do not pad.\n\n"
    "Output exactly 3 paragraphs, each 95-115 words:\n\n"
    "Paragraph 1: Name the sponsor/borrower entity and principal(s). State the "
    "exact loan amount, loan-to-cost ratio, and property address. Describe the "
    "purpose (e.g., 'construction financing for a 415-unit condominium development').\n\n"
    "Paragraph 2: Describe the project with numbers — exact unit count, gross "
    "square footage, zoning district, and key development parameters. Mention "
    "tax abatements, affordable housing components, commercial space, or "
    "parking with specific counts/areas.\n\n"
    "Paragraph 3: Summarize the financial structure with exact figures — total "
    "development cost, equity contribution, and (for condo deals) gross sellout, "
    "developer profit, and profit margin on cost. For rental deals, reference "
    "stabilized value, NOI, cap rate, and DSCR."
)

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "paragraphs": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 3,
            "maxItems": 3,
        }
    },
    "required": ["paragraphs"],
}


def _fmt_currency(value) -> str:
    """Format a number as $X,XXX,XXX for prompt text."""
    if value is None:
        return "N/A"
    try:
        return f"${float(value):,.0f}"
    except (TypeError, ValueError):
        return str(value)


def _fmt_pct(value) -> str:
    """Format a decimal (0.65) as 65.0% for prompt text."""
    if value is None:
        return "N/A"
    try:
        return f"{float(value) * 100:.1f}%"
    except (TypeError, ValueError):
        return str(value)


@dataclass
class TransactionOverviewPrompt(PromptDefinition):
    name: str = "generate_transaction_overview"
    version: str = "2.0.0"
    model: str = "claude-sonnet-4-6"
    system_prompt: str = SYSTEM_PROMPT
    max_output_tokens: int = 4096
    temperature: float = 0.3
    output_schema: dict = field(default_factory=lambda: OUTPUT_SCHEMA)

    def build_input(self, deal_context: dict, task_data: dict) -> list[dict]:
        """Build user message with all deal metrics for the LLM.

        deal_context is pre-built by _build_deal_context() with all relevant
        fields surfaced at the top level.  task_data carries the full
        financial_model dict for any additional lookups.
        """
        dc = deal_context
        fm = task_data.get("financial_model", {})
        inputs = fm.get("inputs", {})
        valuation = fm.get("valuation", {})

        # Merge: prefer deal_context, fall back to financial model
        loan_amount = dc.get("loan_amount") or valuation.get("loan_amount")
        tdc = dc.get("total_development_cost") or fm.get("total_development_cost")
        ltc = dc.get("ltc") or valuation.get("ltc")
        equity = dc.get("equity") or valuation.get("equity")
        units = dc.get("units") or fm.get("total_units")
        gsf = dc.get("gsf") or fm.get("total_gsf")
        zfa = dc.get("zfa") or fm.get("zfa")

        # Treat as condo deal if condo sellout data exists OR deal_type indicates it.
        # A construction loan for a condo development still has sellout metrics.
        has_condo_data = bool(dc.get("gross_sellout") or dc.get("per_unit_sellout") or fm.get("condo_sellout"))
        is_condo = dc.get("deal_type") == "condo_sellout" or has_condo_data

        lines = [
            "Write a Transaction Overview based on the following deal data:",
            "",
            f"Property Name: {dc.get('property_name', 'N/A')}",
            f"Property Address: {dc.get('property_address', 'N/A')}",
            f"Borough: {dc.get('borough', 'N/A')}",
            f"Neighborhood: {dc.get('neighborhood', 'N/A')}",
            f"Deal Type: {'Condominium Construction Financing' if is_condo else dc.get('deal_type', 'Construction Financing')}",
            "",
            "--- Sponsor / Borrower ---",
            f"Sponsor(s): {dc.get('sponsor_names', 'N/A')}",
            f"Sponsor Entity: {dc.get('sponsor_entity', 'N/A')}",
        ]

        # Add principal names if available
        principals = dc.get("principal_names", [])
        if principals:
            if isinstance(principals, list):
                lines.append(f"Principal(s): {', '.join(str(p) for p in principals)}")
            else:
                lines.append(f"Principal(s): {principals}")

        lines.extend([
            f"Years of Experience: {dc.get('sponsor_experience', 'N/A')}",
            "",
            "--- Loan Request ---",
            f"Loan Amount: {_fmt_currency(loan_amount)}",
            f"Interest Rate: {_fmt_pct(dc.get('interest_rate') or valuation.get('interest_rate'))}",
            f"Loan-to-Cost: {_fmt_pct(ltc)}",
            "",
            "--- Project Details ---",
            f"Total Residential Units: {units or 'N/A'}",
            f"Gross Square Footage: {gsf or 'N/A'}",
            f"Zoning Floor Area: {zfa or 'N/A'}",
            f"Zoning District: {dc.get('zoning', 'N/A')}",
        ])

        # Special district / rezoning if available
        special = dc.get("special_district")
        if special:
            lines.append(f"Special District: {special}")

        lines.extend([
            f"Commercial Sq. Ft.: {dc.get('commercial_sf', 0)}",
            f"Parking Spaces: {dc.get('parking_spaces', 0)}",
            f"Tax Abatement Program: {dc.get('abatement_program') or 'None'}",
            "",
            "--- Financial Summary ---",
            f"Total Development Cost: {_fmt_currency(tdc)}",
            f"Equity Contribution: {_fmt_currency(equity)}",
        ])

        # Condo sellout metrics — primary for for-sale deals
        if is_condo:
            lines.extend([
                "",
                "--- Condo Sellout Metrics (PRIMARY — emphasize these) ---",
                f"Gross Sellout: {_fmt_currency(dc.get('gross_sellout'))}",
                f"Developer Profit: {_fmt_currency(dc.get('profit'))}",
                f"Profit Margin on Cost: {_fmt_pct(dc.get('profit_margin'))}",
                f"Per-Unit Sellout: {_fmt_currency(dc.get('per_unit_sellout'))}",
                f"Per-SF Sellout: {_fmt_currency(dc.get('per_sf_sellout'))}",
                f"Per-Unit Cost: {_fmt_currency(dc.get('per_unit_cost'))}",
                f"Per-SF Cost: {_fmt_currency(dc.get('per_sf_cost'))}",
                f"Return on Equity: {_fmt_pct(dc.get('return_on_equity'))}",
                f"Appraised Value: {_fmt_currency(dc.get('appraised_value'))}",
                f"Loan-to-Value: {_fmt_pct(dc.get('ltv'))}",
            ])
        else:
            # Rental metrics
            lines.extend([
                f"Stabilized Value: {_fmt_currency(dc.get('stabilized_value') or valuation.get('stabilized_value'))}",
                f"DSCR: {dc.get('dscr') or valuation.get('dscr', 'N/A')}",
                f"Debt Yield: {_fmt_pct(dc.get('debt_yield') or valuation.get('debt_yield'))}",
                f"Exit Cap Rate: {_fmt_pct(dc.get('cap_rate') or valuation.get('cap_rate'))}",
            ])

        return [{"role": "user", "content": "\n".join(lines)}]

    def validate_output(self, result: dict) -> tuple[bool, list[str]]:
        errors: list[str] = []
        paragraphs = result.get("paragraphs")
        if paragraphs is None:
            errors.append("Missing 'paragraphs' in output")
            return (False, errors)
        if isinstance(paragraphs, str):
            paragraphs = [paragraphs]
            result["paragraphs"] = paragraphs
        if not isinstance(paragraphs, list):
            errors.append("'paragraphs' must be a list")
            return (False, errors)
        if len(paragraphs) != 3:
            errors.append(f"Expected 3 paragraphs, got {len(paragraphs)}")
        total_words = 0
        for i, p in enumerate(paragraphs):
            if not isinstance(p, str) or not p.strip():
                errors.append(f"Paragraph {i + 1} must be a non-empty string")
                continue
            wc = len(p.split())
            total_words += wc
            if wc > 125:
                errors.append(
                    f"Paragraph {i + 1} is {wc} words, exceeds 115-word hard limit (would overflow page). Rewrite shorter."
                )
        if total_words > 360:
            errors.append(
                f"Total length {total_words} words exceeds 340-word page budget. Rewrite shorter."
            )
        return (len(errors) == 0, errors)
