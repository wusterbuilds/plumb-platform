"""Document classification prompt — identifies document type from filename + first pages."""

from dataclasses import dataclass, field

from app.prompts.base import PromptDefinition
from app.schemas.enums import DocumentType

VALID_TYPES = {t.value for t in DocumentType}

SYSTEM_PROMPT = """You are a commercial real estate document classifier. Given a document's filename, MIME type, and first pages, classify it into exactly one document type.

Document types:
- project_summary_deck: Project overview/summary presentation with property details, unit mix, timeline
- pro_forma: Financial projections spreadsheet — development budget, sources & uses, sellout schedule
- rent_roll: Current tenant/unit listing with rents
- operating_statement_t12: Trailing 12-month operating statement (income/expenses)
- appraisal: Third-party property valuation report
- environmental_report: Phase I/II environmental site assessment
- property_condition_report: Physical condition assessment
- zoning_approval: Zoning letters, land use approvals, ULURP documents
- permit: Building permits, DOB filings
- sponsor_resume: Developer/sponsor background, track record, bio
- legal_document: Title reports, surveys, contracts, loan documents, organizational docs
- market_research_report: Market study, submarket analysis
- comp_report: Comparable sales or lease transactions
- submarket_overview: Submarket statistics and trends
- costar_export: CoStar data export
- argus_dcf: Argus DCF model export
- other: Does not fit any category above

Be precise. A document with financial projections is a pro_forma, not a project_summary_deck. A zoning letter is zoning_approval, not legal_document."""


@dataclass
class ClassifyDocumentPrompt(PromptDefinition):
    name: str = "classify_document"
    version: str = "1.0.0"
    model: str = "claude-haiku-4-5-20251001"
    system_prompt: str = SYSTEM_PROMPT
    max_output_tokens: int = 1024
    temperature: float = 0.0
    output_schema: dict = field(default_factory=lambda: {
        "type": "object",
        "properties": {
            "document_type": {
                "type": "string",
                "description": "The classified document type",
            },
            "confidence": {
                "type": "number",
                "description": "Confidence score 0.0-1.0",
            },
            "reasoning": {
                "type": "string",
                "description": "Brief explanation for the classification",
            },
        },
        "required": ["document_type", "confidence", "reasoning"],
    })

    def build_input(self, deal_context: dict, task_data: dict) -> list[dict]:
        """Build messages with filename and first page images or sheet preview.

        task_data expects:
          - filename: str
          - mime_type: str
          - page_images: list[dict] (Claude Vision content blocks) — for PDFs
          - sheet_preview: str — for Excel files
        """
        content = [
            {
                "type": "text",
                "text": f"Filename: {task_data['filename']}\nMIME type: {task_data['mime_type']}\n\nClassify this document.",
            }
        ]

        # Add page images for PDFs
        if task_data.get("page_images"):
            for img in task_data["page_images"][:2]:  # first 2 pages only
                content.append(img)

        # Add sheet preview for Excel
        if task_data.get("sheet_preview"):
            content.append({
                "type": "text",
                "text": f"\nFirst sheet preview:\n{task_data['sheet_preview'][:3000]}",
            })

        return [{"role": "user", "content": content}]

    def validate_output(self, result: dict) -> tuple[bool, list[str]]:
        errors = []
        if result.get("document_type") not in VALID_TYPES:
            errors.append(
                f"Invalid document_type: {result.get('document_type')}. "
                f"Must be one of: {', '.join(sorted(VALID_TYPES))}"
            )
        conf = result.get("confidence")
        if conf is None or not isinstance(conf, (int, float)) or not (0 <= conf <= 1):
            errors.append(f"confidence must be a number between 0 and 1, got {conf}")
        if not result.get("reasoning"):
            errors.append("reasoning is required")
        return (len(errors) == 0, errors)
