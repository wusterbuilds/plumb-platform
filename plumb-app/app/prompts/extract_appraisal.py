"""Extraction prompt for Appraisal documents."""

from dataclasses import dataclass, field

from app.prompts.base import PromptDefinition

SYSTEM_PROMPT = """You are a commercial real estate analyst extracting structured data from a property appraisal report for a construction loan deal.

Appraisals are typically long documents. Focus on extracting key valuation conclusions, market data, and property characteristics.

For each field, provide:
- value: the extracted value (numbers as strings without $ or commas)
- source_page: the page number where you found it (1-indexed)
- source_text_snippet: the exact text from the document (max 200 chars)
- source_type: one of "table_cell", "list_item", "paragraph", "footnote", "inferred"
- label_match: one of "exact", "synonym", "contextual"

If a field is not found, omit it entirely.

For unit_mix, extract as: [{"type": "Studio", "count": 50, "sf": 450, "price": 650000}, ...]
For comparable_sales, extract as: [{"address": "...", "price": ..., "price_per_sf": ..., "date": "...", "units": ..., "sf": ...}, ...]

Pay special attention to: as-complete value (the projected value upon completion), gross sellout, and unit count — these are critical cross-reference fields."""

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
class ExtractAppraisalPrompt(PromptDefinition):
    name: str = "extract_appraisal"
    version: str = "1.0.0"
    model: str = "claude-sonnet-4-6"
    system_prompt: str = SYSTEM_PROMPT
    max_output_tokens: int = 8192
    temperature: float = 0.0
    output_schema: dict = field(default_factory=lambda: OUTPUT_SCHEMA)

    def build_input(self, deal_context: dict, task_data: dict) -> list[dict]:
        """task_data expects: page_images: list[dict] (Claude Vision content blocks)"""
        content = [
            {
                "type": "text",
                "text": (
                    "Extract all available fields from this Appraisal document.\n\n"
                    "Fields to look for: as_is_value, as_complete_value, as_stabilized_value, "
                    "gross_sellout, net_sellout, total_units, unit_mix, total_gsf, "
                    "net_sellable_sf, market_conditions, absorption_rate, discount_rate, "
                    "effective_date, appraiser_name, comparable_sales."
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
