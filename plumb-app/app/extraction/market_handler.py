"""Market-specific extraction handler.

Writes to market_data table instead of extracted_values. Uses the same
PDF chunking/vision logic as the Phase 1 extraction pipeline.
"""

import json
import logging
import uuid

from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.market import MarketData
from app.parsing.pdf import chunk_pages, pdf_to_page_images
from app.prompts.client import PlumbLLMClient
from app.schemas.enums import DocumentStatus, EventType
from app.storage.s3 import download_document
from app.db.events import log_event_sync

logger = logging.getLogger(__name__)

MARKET_DOC_TO_PROMPT = {
    "market_research_report": "extract_market_research",
    "comp_report": "extract_comp_report",
    "submarket_overview": "extract_submarket_overview",
}

MARKET_DOC_TO_DATA_TYPE = {
    "market_research_report": "market_stats",
    "comp_report": "comps",
    "submarket_overview": "market_stats",
}


def is_market_doc(document_type: str) -> bool:
    return document_type in MARKET_DOC_TO_PROMPT


def extract_market_doc(
    client: PlumbLLMClient,
    db: Session,
    deal_id: uuid.UUID,
    doc: Document,
) -> MarketData | None:
    """Extract structured data from a market research PDF.

    Returns a MarketData record written to the database, or None if
    the document type is not a market doc.
    """
    prompt_name = MARKET_DOC_TO_PROMPT.get(doc.document_type)
    if not prompt_name:
        return None

    data_type = MARKET_DOC_TO_DATA_TYPE.get(doc.document_type, "market_stats")

    doc.status = DocumentStatus.EXTRACTING.value
    db.flush()

    file_bytes = download_document(doc.s3_key)
    pages = pdf_to_page_images(file_bytes, dpi=150)
    if not doc.page_count:
        doc.page_count = len(pages)

    all_fields: dict = {}
    for chunk in chunk_pages(pages, max_pages=25, overlap=1):
        result = client.call_llm(
            prompt_name,
            {"deal_id": str(deal_id)},
            {"page_images": [p.to_claude_content() for p in chunk]},
            db=db,
            deal_id=deal_id,
        )
        if "fields" in result:
            for fname, fdata in result["fields"].items():
                if fname not in all_fields:
                    all_fields[fname] = fdata
        elif "comparables" in result:
            existing = all_fields.get("comparables", [])
            existing.extend(result["comparables"])
            all_fields["comparables"] = existing
            for key in ("report_date", "report_source", "geography"):
                if key in result and key not in all_fields:
                    all_fields[key] = result[key]

    record = MarketData(
        deal_id=deal_id,
        data_source="broker_research",
        data_type=data_type,
        data=all_fields,
        source_doc_id=doc.id,
        confidence_score=0.85,
    )
    db.add(record)

    doc.status = DocumentStatus.EXTRACTED.value
    log_event_sync(
        db=db,
        deal_id=deal_id,
        event_type=EventType.MARKET_DATA_IMPORTED.value,
        payload={
            "doc_id": str(doc.id),
            "document_type": doc.document_type,
            "data_type": data_type,
            "fields_extracted": len(all_fields),
        },
    )
    db.flush()

    logger.info(
        "Extracted %d market fields from %s (%s)",
        len(all_fields), doc.filename, doc.document_type,
    )
    return record
