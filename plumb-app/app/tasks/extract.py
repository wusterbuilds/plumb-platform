"""Celery task: extract structured data from a single document."""

import json
import logging
import uuid

from app.db.events import log_event_sync
from app.db.session import sync_session_factory
from app.extraction.confidence import assign_flag, score_confidence
from app.extraction.handlers import get_prompt_name, uses_excel_parsing
from app.models.document import Document
from app.models.extraction import ExtractedValue
from app.parsing.excel import extract_excel_content, format_sheets_for_llm
from app.parsing.pdf import chunk_pages, pdf_to_page_images
from app.prompts.client import PlumbLLMClient
from app.schemas.enums import DocumentStatus, EventType, ExtractionMethod
from app.storage.s3 import download_document
from app.worker import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=2, default_retry_delay=60)
def extract_document(self, deal_id: str, doc_id: str) -> dict:
    """Extract structured data from a classified document.

    Returns summary of extracted fields.
    """
    deal_uuid = uuid.UUID(deal_id)
    doc_uuid = uuid.UUID(doc_id)

    db = sync_session_factory()
    try:
        doc = db.query(Document).filter(Document.id == doc_uuid).one()

        prompt_name = get_prompt_name(doc.document_type)
        if not prompt_name:
            logger.info("No extraction prompt for doc type %s, skipping", doc.document_type)
            doc.status = DocumentStatus.EXTRACTED.value
            db.commit()
            return {"doc_id": doc_id, "fields_extracted": 0, "skipped": True}

        # Mark as extracting
        doc.status = DocumentStatus.EXTRACTING.value
        db.flush()

        # Download and parse
        file_bytes = download_document(doc.s3_key)
        is_excel = uses_excel_parsing(doc.document_type) and (
            doc.mime_type in (
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "application/vnd.ms-excel",
                "application/octet-stream",
            )
            or (doc.filename and doc.filename.lower().endswith((".xlsx", ".xls")))
        )

        # Clear previous extractions for this doc (idempotent re-run)
        db.query(ExtractedValue).filter(
            ExtractedValue.deal_id == deal_uuid,
            ExtractedValue.source_doc_id == doc_uuid,
        ).delete()
        db.flush()

        all_fields = {}

        if is_excel:
            extraction_method = ExtractionMethod.OPENPYXL.value
            excel_content = extract_excel_content(file_bytes)
            sheet_text = format_sheets_for_llm(excel_content)

            task_data = {"sheet_text": sheet_text}
            client = PlumbLLMClient()
            result = client.call_llm(
                prompt_name=prompt_name,
                deal_context={"deal_id": deal_id},
                task_data=task_data,
                db=db,
                deal_id=deal_uuid,
            )
            all_fields = result.get("fields", {})

        else:
            extraction_method = ExtractionMethod.CLAUDE_VISION.value
            pages = pdf_to_page_images(file_bytes, dpi=150)
            if not doc.page_count:
                doc.page_count = len(pages)

            chunks = chunk_pages(pages, max_pages=25, overlap=1)

            client = PlumbLLMClient()
            for chunk in chunks:
                task_data = {
                    "page_images": [p.to_claude_content() for p in chunk],
                }
                result = client.call_llm(
                    prompt_name=prompt_name,
                    deal_context={"deal_id": deal_id},
                    task_data=task_data,
                    db=db,
                    deal_id=deal_uuid,
                )
                # Merge fields — later chunks don't overwrite earlier extractions
                for fname, fdata in result.get("fields", {}).items():
                    if fname not in all_fields:
                        all_fields[fname] = fdata

        # Create ExtractedValue records
        prompt_version = "1.0.0"
        created_count = 0

        for field_name, raw_field in all_fields.items():
            confidence_score, confidence_basis = score_confidence(raw_field)
            flag = assign_flag(confidence_score)

            # Serialize complex values to JSON string
            value = raw_field.get("value")
            if isinstance(value, (dict, list)):
                value = json.dumps(value)

            ev = ExtractedValue(
                deal_id=deal_uuid,
                field_name=field_name,
                value=str(value) if value is not None else None,
                source_doc_id=doc_uuid,
                source_page=raw_field.get("source_page"),
                source_text_snippet=raw_field.get("source_text_snippet"),
                confidence_score=confidence_score,
                confidence_basis=confidence_basis,
                extraction_method=extraction_method,
                prompt_version=prompt_version,
                flag=flag,
            )
            db.add(ev)
            created_count += 1

        # Mark doc as extracted
        doc.status = DocumentStatus.EXTRACTED.value

        log_event_sync(
            db=db,
            deal_id=deal_uuid,
            event_type=EventType.EXTRACTION_COMPLETED.value,
            payload={
                "doc_id": doc_id,
                "document_type": doc.document_type,
                "fields_extracted": created_count,
                "extraction_method": extraction_method,
            },
        )

        db.commit()
        logger.info(
            "Extracted %d fields from doc %s (%s)",
            created_count,
            doc_id,
            doc.document_type,
        )

        return {
            "doc_id": doc_id,
            "document_type": doc.document_type,
            "fields_extracted": created_count,
        }

    except Exception as exc:
        db.rollback()
        logger.exception("Extraction failed for doc %s", doc_id)
        try:
            doc = db.query(Document).filter(Document.id == doc_uuid).one()
            doc.status = DocumentStatus.FAILED.value
            log_event_sync(
                db=db,
                deal_id=deal_uuid,
                event_type=EventType.EXTRACTION_FAILED.value,
                payload={"doc_id": doc_id, "error": f"{type(exc).__name__}: {exc}"},
            )
            db.commit()
        except Exception:
            db.rollback()
        raise self.retry(exc=exc)
    finally:
        db.close()
