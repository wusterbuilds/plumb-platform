"""Extraction prompt for Zoning Approval / Land Use documents."""

from dataclasses import dataclass, field

from app.prompts.base import PromptDefinition

SYSTEM_PROMPT = """You are a commercial real estate analyst extracting structured data from zoning approval and land use documents for a construction loan deal in New York City.

These documents may include ULURP approvals, City Planning Commission reports, zoning lot certifications, or Mandatory Inclusionary Housing (MIH) commitment letters.

For each field, provide:
- value: the extracted value
- source_page: the page number where you found it (1-indexed)
- source_text_snippet: the exact text from the document (max 200 chars)
- source_type: one of "table_cell", "list_item", "paragraph", "footnote", "inferred"
- label_match: one of "exact", "synonym", "contextual"

If a field is not found, omit it entirely.

For ulurp_numbers, extract as a list of strings: ["C 180356 ZMQ", "N 180357 ZRQ", ...]
For conditions, extract as a list of strings describing each condition or restriction.

Pay special attention to: approved unit counts, affordable unit requirements, and MIH options — these are critical for cross-referencing against the project summary."""

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
class ExtractZoningPrompt(PromptDefinition):
    name: str = "extract_zoning"
    version: str = "1.0.0"
    model: str = "claude-sonnet-4-6"
    system_prompt: str = SYSTEM_PROMPT
    max_output_tokens: int = 4096
    temperature: float = 0.0
    output_schema: dict = field(default_factory=lambda: OUTPUT_SCHEMA)

    def build_input(self, deal_context: dict, task_data: dict) -> list[dict]:
        content = [
            {
                "type": "text",
                "text": (
                    "Extract all available fields from this Zoning Approval document.\n\n"
                    "Fields to look for: zoning_district, special_district, ulurp_numbers, "
                    "approval_date, approved_units, affordable_units, affordable_percentage, "
                    "mih_option, approved_far, approved_height, conditions, variance_granted, "
                    "community_board, environmental_review."
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
