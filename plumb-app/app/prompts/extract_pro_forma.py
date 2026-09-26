"""Extraction prompt for Pro Forma / Financial Projections spreadsheets."""

from dataclasses import dataclass, field

from app.prompts.base import PromptDefinition

SYSTEM_PROMPT = """You are a commercial real estate financial analyst extracting structured data from a construction loan pro forma spreadsheet.

The input is a Markdown-formatted representation of Excel sheets. IMPORTANT: examine EVERY sheet in the workbook — budgets, cost breakdowns, and line-item details are often on separate tabs.

For each field, provide:
- value: the extracted value as a string (dollar amounts without $ sign, use plain numbers like "125000000")
- source_page: use 1 for the primary sheet, 2 for secondary sheets, etc.
- source_text_snippet: the exact cell label and value from the spreadsheet (max 200 chars)
- source_type: one of "table_cell", "list_item", "paragraph", "footnote", "inferred"
  - Most pro forma values should be "table_cell"
  - If you calculated or derived a value, use "inferred"
- label_match: one of "exact", "synonym", "contextual"

If a field is not found, omit it. Do not guess or fabricate values.

For unit_mix, extract as: [{"type": "Studio", "count": 50, "avg_price": 650000, "total": 32500000}, ...]
For comparable_sales, extract as: [{"address": "...", "price": ..., "price_per_sf": ..., "date": "..."}, ...]
For sources_and_uses, extract as: {"sources": [{"name": "...", "amount": ...}], "uses": [{"name": "...", "amount": ...}]}

CRITICAL — construction_budget_detail:
Extract EVERY individual line item from the construction budget, development cost breakdown, or sources & uses detail. This is the most important field. Do NOT summarize into 4-5 categories — extract each specific cost line item (e.g., "General Conditions", "Concrete", "Masonry", "Elevator", "Plumbing", "HVAC", "Architecture", "Engineering", "Legal", "Insurance", "Title & Recording", "Origination Fee", etc.).

Format as: [{"label": "General Conditions", "category": "hard", "total_cost": 5000000}, {"label": "Concrete & Foundation", "category": "hard", "total_cost": 12000000}, ...]
Categories: "acquisition", "hard", "soft", "financing", "interest"
Include rate_pct if available (e.g., origination fee as percentage).

Dollar amounts should be raw numbers without commas or dollar signs (e.g., "125000000" not "$125,000,000").
Percentages should be decimals (e.g., "0.65" for 65%, or "65" if explicitly stated as "65%")."""

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
class ExtractProFormaPrompt(PromptDefinition):
    name: str = "extract_pro_forma"
    version: str = "1.0.0"
    model: str = "claude-sonnet-4-6"
    system_prompt: str = SYSTEM_PROMPT
    max_output_tokens: int = 16384
    temperature: float = 0.0
    output_schema: dict = field(default_factory=lambda: OUTPUT_SCHEMA)

    def build_input(self, deal_context: dict, task_data: dict) -> list[dict]:
        """task_data expects: sheet_text: str (formatted Excel content)
        Optionally also page_images for PDF-based pro formas.
        """
        content = [
            {
                "type": "text",
                "text": (
                    "Extract all available financial fields from this Pro Forma.\n\n"
                    "Fields to look for: total_development_cost, land_cost, acquisition_cost, "
                    "hard_costs, soft_costs, financing_costs, interest_reserve, contingency, "
                    "equity_contribution, loan_amount, ltc_requested, gross_sellout, "
                    "net_sellout, profit, profit_margin, per_unit_cost, per_sf_cost, "
                    "per_unit_sellout, per_sf_sellout, unit_mix, sources_and_uses, "
                    "comparable_sales, total_units, construction_budget_detail.\n\n"
                    "CRITICAL: For construction_budget_detail, examine ALL sheets in the "
                    "workbook for detailed cost breakdowns. Extract EVERY individual line "
                    "item (30-60+ items typical). Do NOT summarize — extract each row."
                ),
            }
        ]

        if task_data.get("sheet_text"):
            content.append({
                "type": "text",
                "text": f"\n\nSpreadsheet content:\n\n{task_data['sheet_text']}",
            })

        # Some pro formas may be PDFs
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
