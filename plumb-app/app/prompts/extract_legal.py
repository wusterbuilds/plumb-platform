"""Extraction prompt for Legal Documents (Title Reports, Contracts, etc.)."""

from dataclasses import dataclass, field

from app.prompts.base import PromptDefinition

SYSTEM_PROMPT = """You are a commercial real estate analyst extracting structured data from legal documents for a construction loan deal.

These documents may include title reports, title commitments, surveys, purchase agreements, or organizational documents. Title reports are the most common and most important.

For each field, provide:
- value: the extracted value
- source_page: the page number where you found it (1-indexed)
- source_text_snippet: the exact text from the document (max 200 chars)
- source_type: one of "table_cell", "list_item", "paragraph", "footnote", "inferred"
- label_match: one of "exact", "synonym", "contextual"

If a field is not found, omit it entirely.

For mortgages, extract as: [{"lender": "...", "amount": ..., "date": "...", "maturity": "..."}, ...]
For liens, extract as: [{"type": "...", "amount": ..., "holder": "...", "date": "..."}, ...]
For lis_pendens, extract as: [{"index_number": "...", "plaintiff": "...", "date": "...", "description": "..."}, ...]
For easements, extract as: [{"type": "...", "beneficiary": "...", "description": "..."}, ...]
For title_exceptions, extract as: [{"number": ..., "description": "..."}, ...]

Dollar amounts should be raw numbers without $ or commas.
Be thorough with liens and encumbrances — these are critical for underwriting."""

EXTRACTED_FIELD_SCHEMA = {
    "type": "object",
    "properties": {
        "value": {"type": "string"},
        "source_page": {"type": "integer"},
        "source_text_snippet": {"type": "string"},
        "source_type": {"type": "string", "enum": ["table_cell", "list_item", "paragraph", "footnote", "inferred"]},
        "label_match": {"type": "string", "enum": ["exact", "synonym", "contextual"]},
    },
    "required": ["value", "source_page", "source_text_snippet", "source_type", "label_match"],
}

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "fields": {
            "type": "object",
            "additionalProperties": EXTRACTED_FIELD_SCHEMA,
        },
    },
    "required": ["fields"],
}


@dataclass
class ExtractLegalPrompt(PromptDefinition):
    name: str = "extract_legal"
    version: str = "1.0.0"
    model: str = "claude-sonnet-4-6"
    system_prompt: str = SYSTEM_PROMPT
    max_output_tokens: int = 8192
    temperature: float = 0.0
    output_schema: dict = field(default_factory=lambda: OUTPUT_SCHEMA)

    def build_input(self, deal_context: dict, task_data: dict) -> list[dict]:
        content = [
            {
                "type": "text",
                "text": (
                    "Extract all available fields from this Legal Document.\n\n"
                    "Fields to look for: property_owner, buyer_entity, deed_type, "
                    "deed_date, purchase_price, mortgages, liens, lis_pendens, "
                    "easements, title_exceptions, title_policy_amount, title_company, "
                    "survey_notes, tax_lot_info."
                ),
            }
        ]
        for img in task_data.get("page_images", []):
            content.append(img)

        return [{"role": "user", "content": content}]

    def validate_output(self, result: dict) -> tuple[bool, list[str]]:
        errors = []
        if "fields" not in result:
            errors.append("Missing 'fields' in output")
            return (False, errors)
        if not isinstance(result["fields"], dict):
            errors.append("'fields' must be a dict")
        return (len(errors) == 0, errors)
