"""Celery task: classify a single document."""

import logging
import uuid

from app.db.events import log_event_sync
from app.db.session import sync_session_factory
from app.extraction.handlers import is_extractable
from app.models.document import Document
from app.parsing.excel import extract_excel_content, format_sheets_for_llm
from app.parsing.pdf import pdf_to_page_images
from app.prompts.client import PlumbLLMClient
from app.schemas.enums import DocumentStatus, EventType
from app.storage.s3 import download_document
from app.worker import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def classify_document(self, deal_id: str, doc_id: str) -> dict:
    """Classify a single document using the classification prompt.

    Returns the classification result dict.
    """
    deal_uuid = uuid.UUID(deal_id)
    doc_uuid = uuid.UUID(doc_id)

    db = sync_session_factory()
    try:
        doc = db.query(Document).filter(Document.id == doc_uuid).one()

        # Download from S3
        file_bytes = download_document(doc.s3_key)

        # Prepare input based on file type
        task_data = {
            "filename": doc.filename,
            "mime_type": doc.mime_type,
        }

        is_excel = doc.mime_type in (
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "application/vnd.ms-excel",
        )

        if is_excel:
            excel_content = extract_excel_content(file_bytes)
            task_data["sheet_preview"] = format_sheets_for_llm(excel_content)
        else:
            # PDF — render first 2 pages
            pages = pdf_to_page_images(file_bytes, dpi=150)
            task_data["page_images"] = [p.to_claude_content() for p in pages[:2]]

            # Store page count
            doc.page_count = len(pages)

        # Call classification LLM
        client = PlumbLLMClient()
        result = client.call_llm(
            prompt_name="classify_document",
            deal_context={"deal_id": deal_id},
            task_data=task_data,
            db=db,
            deal_id=deal_uuid,
        )

        # Update document
        doc.document_type = result["document_type"]
        doc.classification_confidence = result["confidence"]
        doc.status = DocumentStatus.PARSED.value

        log_event_sync(
            db=db,
            deal_id=deal_uuid,
            event_type=EventType.DOC_CLASSIFIED.value,
            payload={
                "doc_id": doc_id,
                "document_type": result["document_type"],
                "confidence": result["confidence"],
                "reasoning": result["reasoning"],
            },
        )

        db.commit()
        logger.info(
            "Classified doc %s as %s (confidence: %.2f)",
            doc_id,
            result["document_type"],
            result["confidence"],
        )

        return {
            "doc_id": doc_id,
            "document_type": result["document_type"],
            "confidence": result["confidence"],
            "extractable": is_extractable(result["document_type"]),
        }

    except Exception as exc:
        db.rollback()
        logger.exception("Classification failed for doc %s", doc_id)
        try:
            doc = db.query(Document).filter(Document.id == doc_uuid).one()
            doc.status = DocumentStatus.FAILED.value
            db.commit()
        except Exception:
            db.rollback()
        raise self.retry(exc=exc)
    finally:
        db.close()
