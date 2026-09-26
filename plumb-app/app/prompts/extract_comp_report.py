"""Extraction prompt for comparable transaction reports (broker PDFs)."""

from dataclasses import dataclass, field

from app.prompts.base import PromptDefinition

SYSTEM_PROMPT = """You are a commercial real estate analyst extracting comparable transaction data from a comp report for a construction loan condo sellout deal.

These reports contain recent property sales, typically presented in tables with property details, transaction amounts, and per-unit/per-SF metrics.

Extract each comparable transaction as a structured record with:
- address: property address
- price: total transaction price
- price_per_unit: price per residential unit
- price_per_sf: price per square foot
- cap_rate: capitalization rate (if available)
- date: transaction/closing date
- buyer: acquiring entity
- seller: disposing entity
- property_type: residential, condo, multifamily, mixed-use, etc.
- units: number of units
- square_footage: total SF
- notes: any relevant details

For each field provide source_page and source_text_snippet for provenance.
Extract ALL comparable transactions found in the document."""

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "comparables": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "address": {"type": "string"},
                    "price": {"type": "string"},
                    "price_per_unit": {"type": "string"},
                    "price_per_sf": {"type": "string"},
                    "cap_rate": {"type": "string"},
                    "date": {"type": "string"},
                    "buyer": {"type": "string"},
                    "seller": {"type": "string"},
                    "property_type": {"type": "string"},
                    "units": {"type": "string"},
                    "square_footage": {"type": "string"},
                    "notes": {"type": "string"},
                    "source_page": {"type": "integer"},
                },
            },
        },
        "report_date": {"type": "string"},
        "report_source": {"type": "string"},
        "geography": {"type": "string"},
    },
    "required": ["comparables"],
}


@dataclass
class CompReportExtractionPrompt(PromptDefinition):
    name: str = "extract_comp_report"
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
                    "Extract all comparable transactions from this report. "
                    "Include address, price, price_per_unit, price_per_sf, "
                    "cap_rate, date, buyer, seller, property_type, units, "
                    "square_footage for each comp."
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
        if "comparables" not in result:
            errors.append("Missing 'comparables' in output")
            return (False, errors)
        if not isinstance(result["comparables"], list):
            errors.append("'comparables' must be a list")
        return (len(errors) == 0, errors)
