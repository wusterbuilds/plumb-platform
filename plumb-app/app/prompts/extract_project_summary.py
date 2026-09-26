"""Extraction prompt for Project Summary / Investment Deck documents."""

from dataclasses import dataclass, field

from app.prompts.base import PromptDefinition

SYSTEM_PROMPT = """You are a commercial real estate analyst extracting structured data from a project summary or investment deck for a construction loan deal.

Extract every field you can find. For each field, provide:
- value: the extracted value (numbers as strings, lists as JSON arrays)
- source_page: the page number where you found it (1-indexed)
- source_text_snippet: the exact text from the document containing the value (max 200 chars)
- source_type: one of "table_cell", "list_item", "paragraph", "footnote", "inferred"
- label_match: one of "exact" (label matches field name), "synonym" (label is a synonym), "contextual" (value inferred from context)

If a field is not found in the document, omit it entirely — do not guess or fabricate values.

For unit_mix, extract as a list of objects: [{"type": "Studio", "count": 50, "sf": 450}, ...]
For amenities, extract as a simple list of strings.

Be precise with numbers. Extract them exactly as stated in the document."""

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
            "description": "Map of field_name to extraction result. Only include fields found in the document.",
            "additionalProperties": EXTRACTED_FIELD_SCHEMA,
        },
    },
    "required": ["fields"],
}


@dataclass
class ExtractProjectSummaryPrompt(PromptDefinition):
    name: str = "extract_project_summary"
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
                    "Extract all available fields from this Project Summary document.\n\n"
                    "Fields to look for: property_address, project_name, total_units, "
                    "market_rate_units, affordable_units, total_gsf, residential_sf, "
                    "commercial_sf, community_facility_sf, parking_spaces, floors, "
                    "zoning_district, far, lot_area, building_class, construction_type, "
                    "unit_mix, amenities, completion_date, construction_start_date, "
                    "project_timeline, total_development_cost, borough, neighborhood, "
                    "block, lot."
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
