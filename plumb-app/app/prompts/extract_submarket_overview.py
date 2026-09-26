"""Extraction prompt for submarket overview documents (broker PDFs)."""

from dataclasses import dataclass, field

from app.prompts.base import PromptDefinition

SYSTEM_PROMPT = """You are a commercial real estate analyst extracting structured submarket data from a submarket overview document for a construction loan deal.

These documents describe the economic and demographic characteristics of a neighborhood or submarket, typically including population, employment, transportation access, development activity, and major employers.

For each field, provide:
- value: the extracted value
- source_page: the page number where you found it (1-indexed)
- source_text_snippet: the exact text from the document (max 200 chars)

If a field is not found, omit it entirely.

For demographics, extract population, median household income, population growth rate.
For economic_drivers and development_pipeline, extract as arrays of strings.
For transportation, list major transit lines and access points."""

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "fields": {
            "type": "object",
            "properties": {
                "submarket_name": {"type": "object"},
                "population": {"type": "object"},
                "median_household_income": {"type": "object"},
                "population_growth_rate": {"type": "object"},
                "unemployment_rate": {"type": "object"},
                "economic_drivers": {"type": "object"},
                "major_employers": {"type": "object"},
                "transportation": {"type": "object"},
                "development_pipeline": {"type": "object"},
                "planned_infrastructure": {"type": "object"},
                "walkability_score": {"type": "object"},
                "school_district_rating": {"type": "object"},
            },
            "additionalProperties": True,
        },
    },
    "required": ["fields"],
}


@dataclass
class SubmarketOverviewExtractionPrompt(PromptDefinition):
    name: str = "extract_submarket_overview"
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
                    "Extract submarket overview data from this document.\n\n"
                    "Fields to look for: submarket_name, population, "
                    "median_household_income, population_growth_rate, "
                    "unemployment_rate, economic_drivers, major_employers, "
                    "transportation, development_pipeline, planned_infrastructure."
                ),
            }
        ]
        for img in task_data.get("page_images", []):
            content.append(img)
        if "sheet_text" in task_data:
            content.append({"type": "text", "text": f"\nSpreadsheet content:\n{task_data['sheet_text']}"})

        return [{"role": "user", "content": content}]

    def validate_output(self, result: dict) -> tuple[bool, list[str]]:
        errors = []
        if "fields" not in result:
            errors.append("Missing 'fields' in output")
            return (False, errors)
        if not isinstance(result["fields"], dict):
            errors.append("'fields' must be a dict")
        return (len(errors) == 0, errors)
