"""Extraction prompt for market research reports (broker PDFs)."""

from dataclasses import dataclass, field

from app.prompts.base import PromptDefinition

SYSTEM_PROMPT = """You are a commercial real estate analyst extracting structured market data from a broker market research report for a construction loan deal.

These reports typically contain submarket-level data including vacancy rates, rental rates, absorption, supply pipeline, and demand drivers.

For each field, provide:
- value: the extracted value
- source_page: the page number where you found it (1-indexed)
- source_text_snippet: the exact text from the document (max 200 chars)

If a field is not found, omit it entirely. Extract the most recent data available.

For numeric ranges (e.g. asking rent $45-$55/SF), extract as a string preserving the range.
For percentages, include the % sign.
For supply_pipeline and demand_drivers, extract as arrays of strings."""

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "fields": {
            "type": "object",
            "properties": {
                "submarket": {"type": "object"},
                "vacancy_rate": {"type": "object"},
                "asking_rent": {"type": "object"},
                "effective_rent": {"type": "object"},
                "absorption_sf": {"type": "object"},
                "absorption_units": {"type": "object"},
                "supply_pipeline": {"type": "object"},
                "demand_drivers": {"type": "object"},
                "cap_rate_range": {"type": "object"},
                "market_trend": {"type": "object"},
                "report_date": {"type": "object"},
                "report_source": {"type": "object"},
            },
            "additionalProperties": True,
        },
    },
    "required": ["fields"],
}


@dataclass
class MarketResearchExtractionPrompt(PromptDefinition):
    name: str = "extract_market_research"
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
                    "Extract market research data from this report.\n\n"
                    "Fields to look for: submarket, vacancy_rate, asking_rent, "
                    "effective_rent, absorption_sf, absorption_units, supply_pipeline, "
                    "demand_drivers, cap_rate_range, market_trend, report_date, report_source."
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
