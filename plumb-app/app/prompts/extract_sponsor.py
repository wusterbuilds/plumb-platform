"""Extraction prompt for Sponsor Resume / Developer Background documents."""

from dataclasses import dataclass, field

from app.prompts.base import PromptDefinition

SYSTEM_PROMPT = """You are a commercial real estate analyst extracting structured data from a sponsor resume or developer background document for a construction loan deal.

Extract the developer's track record, experience, and credentials. This data feeds into the Sponsor Background section of the Offering Memorandum.

For each field, provide:
- value: the extracted value (use JSON strings for lists/objects)
- source_page: the page number where you found it (1-indexed)
- source_text_snippet: the exact text from the document (max 200 chars)
- source_type: one of "table_cell", "list_item", "paragraph", "footnote", "inferred"
- label_match: one of "exact", "synonym", "contextual"

If a field is not found, omit it entirely.

For completed_projects, extract as: [{"name": "...", "location": "...", "units": ..., "sf": ..., "value": ..., "year_completed": ...}, ...]
For current_projects, extract as: [{"name": "...", "location": "...", "units": ..., "status": "...", "expected_completion": "..."}, ...]
For credentials and notable_achievements, extract as simple string lists.
For principal_names, extract as a list of name strings."""

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
class ExtractSponsorPrompt(PromptDefinition):
    name: str = "extract_sponsor"
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
                    "Extract all available fields from this Sponsor Resume / Developer Background.\n\n"
                    "Fields to look for: sponsor_name, sponsor_entity, principal_names, "
                    "years_experience, completed_projects, current_projects, "
                    "total_units_developed, total_sf_developed, total_development_value, "
                    "credentials, notable_achievements."
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
