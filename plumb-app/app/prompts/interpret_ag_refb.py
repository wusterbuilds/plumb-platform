"""Interpretation prompt for NY AG Real Estate Finance Bureau records."""

from dataclasses import dataclass, field

from app.prompts.base import PromptDefinition

SYSTEM_PROMPT = """You are a commercial real estate underwriting analyst reviewing NY Attorney General Real Estate Finance Bureau records for a construction loan condo sellout deal.

The AG REFB maintains the authoritative database of condo/co-op offering plans in New York State. You will receive search results that may include:
- Offering plans filed by the sponsor (address search results)
- Other offering plans filed by the same sponsor (sponsor name search results)

Extract underwriting-relevant facts:
1. Offering plan status for the subject property (filed, accepted, effective, abandoned)
2. Filing date and acceptance date
3. Number and type of units in the plan
4. Sponsor entity name and principals
5. Other offering plans by the same sponsor (portfolio history)
6. Any enforcement actions, complaints, or amendments

Material flags:
- Offering plan not yet accepted (can't close units)
- Multiple amendments (plan instability)
- Enforcement actions against the sponsor
- Sponsor has abandoned plans on other projects
- Discrepancy between claimed filing status and actual AG records"""

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "offering_plans": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "plan_id": {"type": "string"},
                    "plan_name": {"type": "string"},
                    "status": {"type": "string"},
                    "filing_date": {"type": "string"},
                    "acceptance_date": {"type": "string"},
                    "sponsor_entity": {"type": "string"},
                    "units": {"type": "string"},
                    "address": {"type": "string"},
                },
            },
        },
        "enforcement_actions": {
            "type": "array",
            "items": {"type": "string"},
        },
        "sponsor_other_filings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "plan_name": {"type": "string"},
                    "status": {"type": "string"},
                    "address": {"type": "string"},
                },
            },
        },
        "material_flags": {"type": "array", "items": {"type": "string"}},
        "summary": {"type": "string"},
    },
    "required": ["summary"],
}


@dataclass
class AGREFBInterpretationPrompt(PromptDefinition):
    name: str = "interpret_ag_refb"
    version: str = "1.0.0"
    model: str = "claude-sonnet-4-6"
    system_prompt: str = SYSTEM_PROMPT
    max_output_tokens: int = 4096
    temperature: float = 0.0
    output_schema: dict = field(default_factory=lambda: OUTPUT_SCHEMA)

    def build_input(self, deal_context: dict, task_data: dict) -> list[dict]:
        return [
            {
                "role": "user",
                "content": (
                    "Interpret the following NY AG Real Estate Finance Bureau records "
                    "for underwriting relevance.\n\n"
                    f"AG REFB Data:\n{task_data.get('ag_refb_data', '{}')}"
                ),
            }
        ]

    def validate_output(self, result: dict) -> tuple[bool, list[str]]:
        errors = []
        if "summary" not in result:
            errors.append("Missing 'summary' in output")
        return (len(errors) == 0, errors)
