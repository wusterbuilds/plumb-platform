"""Interpretation prompt for NYC DOB permit and violation records."""

from dataclasses import dataclass, field

from app.prompts.base import PromptDefinition

SYSTEM_PROMPT = """You are a commercial real estate underwriting analyst interpreting NYC Department of Buildings (DOB) records for a construction loan deal.

You will receive raw DOB data containing:
- job_filings: permit applications and job filings for the property (by BIN)
- violations: ECB violations including descriptions, penalties, hearing status
- approved_permits: approved construction permits
- sponsor_violations: violations across other properties by the same developer/sponsor

Extract underwriting-relevant facts and flag material issues:
1. Active permits and their status (approved, in progress, disapproved)
2. Open violations — especially stop-work orders, Class 1 (immediately hazardous), or significant penalties
3. Complaints and their resolution status
4. Certificate of occupancy status
5. Sponsor's violation history across portfolio — patterns of non-compliance

Material flags (these affect deal risk):
- Any open stop-work order
- Class 1 violations (immediate hazard)
- Pattern of repeated violations at subject property
- High aggregate penalties or unpaid balances
- Developer with above-average violation rates across portfolio"""

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "active_permits": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "job_number": {"type": "string"},
                    "permit_type": {"type": "string"},
                    "status": {"type": "string"},
                    "filing_date": {"type": "string"},
                    "description": {"type": "string"},
                },
            },
        },
        "open_violations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "violation_number": {"type": "string"},
                    "severity": {"type": "string"},
                    "type": {"type": "string"},
                    "description": {"type": "string"},
                    "penalty": {"type": "string"},
                    "balance_due": {"type": "string"},
                    "status": {"type": "string"},
                },
            },
        },
        "stop_work_orders": {"type": "array", "items": {"type": "string"}},
        "co_status": {"type": "string"},
        "sponsor_portfolio_violations": {
            "type": "object",
            "properties": {
                "total_violations": {"type": "integer"},
                "open_violations": {"type": "integer"},
                "total_penalties": {"type": "string"},
                "properties_with_violations": {"type": "integer"},
            },
        },
        "material_flags": {"type": "array", "items": {"type": "string"}},
        "summary": {"type": "string"},
    },
    "required": ["summary", "material_flags"],
}


@dataclass
class DOBInterpretationPrompt(PromptDefinition):
    name: str = "interpret_dob"
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
                    "Interpret the following DOB records and flag any material issues "
                    "for underwriting.\n\n"
                    f"DOB Records:\n{task_data.get('dob_records', '{}')}"
                ),
            }
        ]

    def validate_output(self, result: dict) -> tuple[bool, list[str]]:
        errors = []
        if "summary" not in result:
            errors.append("Missing 'summary' in output")
        if "material_flags" not in result:
            errors.append("Missing 'material_flags' in output")
        return (len(errors) == 0, errors)
