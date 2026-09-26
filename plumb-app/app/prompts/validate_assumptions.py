"""Borrower assumption validation prompt — compares deal values against market data."""

from dataclasses import dataclass, field

from app.prompts.base import PromptDefinition

SYSTEM_PROMPT = """You are a commercial real estate underwriting analyst validating a borrower's assumptions against independently collected market data for a construction loan condo sellout deal.

You will receive:
1. Extracted deal values (from the borrower's documents)
2. Assembled market context (from public records, broker research, and structured imports)

Compare the borrower's claims against market reality and produce validation flags for any discrepancies. Focus on:

- Rent assumptions vs. market rents (from CoStar/broker research)
- Vacancy assumptions vs. market vacancy rates
- Sellout price assumptions vs. comparable transactions (CoStar/MarketProof)
- Zoning claims vs. ZoLa/PLUTO data (zoning district, FAR, allowed uses)
- Construction timeline vs. DOB permit history (are permits actually filed?)
- Offering plan status vs. AG REFB records (is the plan actually accepted?)
- Sponsor portfolio claims vs. verified projects (ACRIS + DOB + AG cross-reference)

For each flag, specify:
- field: the borrower assumption field
- borrower_value: what the borrower claims
- market_value: what the market data shows
- severity: "info" (minor difference), "warning" (material but explainable), "critical" (deal risk)
- explanation: clear statement of the discrepancy and its implications"""

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "validation_flags": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "field": {"type": "string"},
                    "borrower_value": {"type": "string"},
                    "market_value": {"type": "string"},
                    "severity": {
                        "type": "string",
                        "enum": ["info", "warning", "critical"],
                    },
                    "explanation": {"type": "string"},
                },
                "required": ["field", "severity", "explanation"],
            },
        },
        "overall_assessment": {
            "type": "string",
            "enum": ["consistent", "minor_discrepancies", "material_concerns", "significant_red_flags"],
        },
        "summary": {"type": "string"},
    },
    "required": ["validation_flags", "overall_assessment", "summary"],
}


@dataclass
class BorrowerAssumptionValidationPrompt(PromptDefinition):
    name: str = "validate_assumptions"
    version: str = "1.0.0"
    model: str = "claude-sonnet-4-6"
    system_prompt: str = SYSTEM_PROMPT
    max_output_tokens: int = 8192
    temperature: float = 0.0
    output_schema: dict = field(default_factory=lambda: OUTPUT_SCHEMA)

    def build_input(self, deal_context: dict, task_data: dict) -> list[dict]:
        return [
            {
                "role": "user",
                "content": (
                    "Compare the borrower's deal assumptions against the independently "
                    "collected market data and flag any discrepancies.\n\n"
                    f"Deal Extracted Values:\n{task_data.get('extracted_values', '{}')}\n\n"
                    f"Market Context:\n{task_data.get('market_context', '{}')}\n\n"
                    f"Sponsor Portfolio:\n{task_data.get('sponsor_portfolio', '{}')}"
                ),
            }
        ]

    def validate_output(self, result: dict) -> tuple[bool, list[str]]:
        errors = []
        if "validation_flags" not in result:
            errors.append("Missing 'validation_flags' in output")
        if "overall_assessment" not in result:
            errors.append("Missing 'overall_assessment' in output")
        if "summary" not in result:
            errors.append("Missing 'summary' in output")
        return (len(errors) == 0, errors)
