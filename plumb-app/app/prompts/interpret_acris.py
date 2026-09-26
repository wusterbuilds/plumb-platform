"""Interpretation prompt for ACRIS property transaction records."""

from dataclasses import dataclass, field

from app.prompts.base import PromptDefinition

SYSTEM_PROMPT = """You are a commercial real estate underwriting analyst interpreting NYC ACRIS (Automated City Register Information System) property records for a construction loan deal.

You will receive raw ACRIS data containing three joined tables:
- legals: property-level records linking documents to BBL (Borough-Block-Lot)
- masters: document details (type, amount, dates)
- parties: buyer/seller/borrower/lender names per document

Extract underwriting-relevant facts:
1. Current ownership chain (most recent deed transfers)
2. Purchase price and date from the most recent deed
3. Existing mortgages (lender, amount, date)
4. Liens, UCC filings, or satisfactions
5. Any assignments or modifications of existing debt

Focus on the most recent 5-10 years of activity. Flag anything unusual:
- Rapid ownership changes (potential flipping)
- Multiple liens or unsatisfied mortgages
- Related-party transactions
- Unusually low or high transaction amounts"""

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "current_owner": {"type": "string"},
        "purchase_price": {"type": "string"},
        "purchase_date": {"type": "string"},
        "existing_mortgages": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "lender": {"type": "string"},
                    "amount": {"type": "string"},
                    "date": {"type": "string"},
                    "status": {"type": "string"},
                },
            },
        },
        "lien_history": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "type": {"type": "string"},
                    "amount": {"type": "string"},
                    "date": {"type": "string"},
                    "status": {"type": "string"},
                },
            },
        },
        "ownership_chain": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "grantor": {"type": "string"},
                    "grantee": {"type": "string"},
                    "date": {"type": "string"},
                    "amount": {"type": "string"},
                },
            },
        },
        "flags": {
            "type": "array",
            "items": {"type": "string"},
        },
        "summary": {"type": "string"},
    },
    "required": ["summary"],
}


@dataclass
class ACRISInterpretationPrompt(PromptDefinition):
    name: str = "interpret_acris"
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
                    "Interpret the following ACRIS property records and extract "
                    "underwriting-relevant facts.\n\n"
                    f"ACRIS Records:\n{task_data.get('acris_records', '{}')}"
                ),
            }
        ]

    def validate_output(self, result: dict) -> tuple[bool, list[str]]:
        errors = []
        if "summary" not in result:
            errors.append("Missing 'summary' in output")
        return (len(errors) == 0, errors)
