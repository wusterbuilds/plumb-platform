"""Maps document types to extraction prompts and coordinates extraction logic."""

from app.extraction.field_specs import get_extractable_doc_types, get_field_specs

# Document type → prompt name mapping
DOC_TYPE_TO_PROMPT = {
    "project_summary_deck": "extract_project_summary",
    "pro_forma": "extract_pro_forma",
    "appraisal": "extract_appraisal",
    "sponsor_resume": "extract_sponsor",
    "zoning_approval": "extract_zoning",
    "legal_document": "extract_legal",
}

# Document types that use Excel parsing instead of PDF Vision
EXCEL_DOC_TYPES = {"pro_forma"}


def get_prompt_name(document_type: str) -> str | None:
    """Get the extraction prompt name for a document type."""
    return DOC_TYPE_TO_PROMPT.get(document_type)


def is_extractable(document_type: str) -> bool:
    """Check if we have an extraction prompt for this document type."""
    return document_type in DOC_TYPE_TO_PROMPT


def uses_excel_parsing(document_type: str) -> bool:
    """Check if this document type should be parsed as Excel."""
    return document_type in EXCEL_DOC_TYPES
