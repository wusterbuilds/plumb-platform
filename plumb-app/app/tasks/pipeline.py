"""Celery task: orchestrate the full extraction pipeline for a deal."""

import json
import logging
import uuid

from app.db.events import log_event_sync
from app.db.session import sync_session_factory
from app.extraction.confidence import apply_corroboration, assign_flag, score_confidence
from app.extraction.cross_references import run_all_cross_references
from app.extraction.handlers import get_prompt_name, is_extractable, uses_excel_parsing
from app.models.deal import Deal
from app.models.document import Document
from app.models.extraction import ExtractedValue
from app.parsing.excel import extract_excel_content, format_sheets_for_llm
from app.parsing.pdf import chunk_pages, pdf_to_page_images
from app.prompts.client import PlumbLLMClient
from app.schemas.enums import DealStatus, DocumentStatus, EventType, ExtractionMethod
from app.storage.s3 import download_document
from app.worker import celery_app

logger = logging.getLogger(__name__)


def _transition_sync(db, deal_id: uuid.UUID, target_status: str) -> None:
    """Simple sync state transition for pipeline tasks (auto-gate only)."""
    deal = db.query(Deal).filter(Deal.id == deal_id).with_for_update().one()
    old_status = deal.status
    deal.status = target_status
    deal.version += 1
    log_event_sync(
        db=db,
        deal_id=deal_id,
        event_type=EventType.STATE_TRANSITION.value,
        payload={
            "from_status": old_status,
            "to_status": target_status,
            "transition_type": "forward",
            "actor": "pipeline",
        },
    )
    db.flush()


def _classify_doc(client: PlumbLLMClient, db, deal_id: uuid.UUID, doc: Document) -> dict:
    """Classify a single document. Called directly, not as a sub-task."""
    file_bytes = download_document(doc.s3_key)
    task_data = {"filename": doc.filename, "mime_type": doc.mime_type}

    is_excel = doc.mime_type in (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-excel",
    )

    if is_excel:
        content = extract_excel_content(file_bytes)
        task_data["sheet_preview"] = format_sheets_for_llm(content)
    else:
        pages = pdf_to_page_images(file_bytes, dpi=100)
        task_data["page_images"] = [p.to_claude_content() for p in pages[:2]]
        doc.page_count = len(pages)

    result = client.call_llm(
        "classify_document", {"deal_id": str(deal_id)}, task_data,
        db=db, deal_id=deal_id,
    )

    doc.document_type = result["document_type"]
    doc.classification_confidence = result["confidence"]
    doc.status = DocumentStatus.PARSED.value

    log_event_sync(
        db=db, deal_id=deal_id, event_type=EventType.DOC_CLASSIFIED.value,
        payload={
            "doc_id": str(doc.id), "document_type": result["document_type"],
            "confidence": result["confidence"], "reasoning": result["reasoning"],
        },
    )
    db.flush()

    logger.info("Classified %s as %s (%.2f)", doc.filename, result["document_type"], result["confidence"])
    return {
        "doc_id": str(doc.id),
        "document_type": result["document_type"],
        "confidence": result["confidence"],
        "extractable": is_extractable(result["document_type"]),
    }


def _extract_doc(client: PlumbLLMClient, db, deal_id: uuid.UUID, doc: Document) -> dict:
    """Extract structured data from a single document. Called directly."""
    prompt_name = get_prompt_name(doc.document_type)
    if not prompt_name:
        doc.status = DocumentStatus.EXTRACTED.value
        db.flush()
        return {"doc_id": str(doc.id), "fields_extracted": 0, "skipped": True}

    doc.status = DocumentStatus.EXTRACTING.value
    db.flush()

    file_bytes = download_document(doc.s3_key)
    is_excel = uses_excel_parsing(doc.document_type) and doc.mime_type in (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-excel",
    )

    # Clear previous extractions (idempotent)
    db.query(ExtractedValue).filter(
        ExtractedValue.deal_id == deal_id,
        ExtractedValue.source_doc_id == doc.id,
    ).delete()
    db.flush()

    all_fields = {}

    if is_excel:
        extraction_method = ExtractionMethod.OPENPYXL.value
        text = format_sheets_for_llm(extract_excel_content(file_bytes))
        result = client.call_llm(
            prompt_name, {"deal_id": str(deal_id)}, {"sheet_text": text},
            db=db, deal_id=deal_id,
        )
        all_fields = result.get("fields", {})
    else:
        extraction_method = ExtractionMethod.CLAUDE_VISION.value
        pages = pdf_to_page_images(file_bytes, dpi=150)
        if not doc.page_count:
            doc.page_count = len(pages)

        for chunk in chunk_pages(pages, max_pages=25, overlap=1):
            result = client.call_llm(
                prompt_name, {"deal_id": str(deal_id)},
                {"page_images": [p.to_claude_content() for p in chunk]},
                db=db, deal_id=deal_id,
            )
            for fname, fdata in result.get("fields", {}).items():
                if fname not in all_fields:
                    all_fields[fname] = fdata

    # Create ExtractedValue records
    count = 0
    for field_name, raw in all_fields.items():
        score, basis = score_confidence(raw)
        flag = assign_flag(score)
        value = raw.get("value")
        if isinstance(value, (dict, list)):
            value = json.dumps(value)

        db.add(ExtractedValue(
            deal_id=deal_id, field_name=field_name,
            value=str(value) if value is not None else None,
            source_doc_id=doc.id,
            source_page=raw.get("source_page"),
            source_text_snippet=raw.get("source_text_snippet"),
            confidence_score=score, confidence_basis=basis,
            extraction_method=extraction_method,
            prompt_version="1.0.0", flag=flag,
        ))
        count += 1

    doc.status = DocumentStatus.EXTRACTED.value
    log_event_sync(
        db=db, deal_id=deal_id, event_type=EventType.EXTRACTION_COMPLETED.value,
        payload={
            "doc_id": str(doc.id), "document_type": doc.document_type,
            "fields_extracted": count, "extraction_method": extraction_method,
        },
    )
    db.flush()

    logger.info("Extracted %d fields from %s (%s)", count, doc.filename, doc.document_type)
    return {"doc_id": str(doc.id), "document_type": doc.document_type, "fields_extracted": count}


@celery_app.task(bind=True, max_retries=0)
def run_deal_pipeline(self, deal_id: str, actor_id: str | None = None) -> dict:
    """Orchestrate the full extraction pipeline:

    1. Transition to CLASSIFYING → classify all docs
    2. Transition to EXTRACTING → extract all extractable docs
    3. Apply corroboration bonuses + run cross-references
    4. Transition to EXTRACTION_REVIEW
    """
    deal_uuid = uuid.UUID(deal_id)
    client = PlumbLLMClient()

    db = sync_session_factory()
    try:
        log_event_sync(
            db=db, deal_id=deal_uuid,
            event_type=EventType.EXTRACTION_STARTED.value,
            payload={"actor_id": actor_id},
        )

        # --- Classification ---
        _transition_sync(db, deal_uuid, DealStatus.CLASSIFYING.value)
        db.commit()

        db = sync_session_factory()
        docs = (
            db.query(Document)
            .filter(
                Document.deal_id == deal_uuid,
                Document.status.in_([DocumentStatus.UPLOADED.value, DocumentStatus.PARSED.value]),
            )
            .all()
        )

        if not docs:
            _transition_sync(db, deal_uuid, DealStatus.EXTRACTION_REVIEW.value)
            db.commit()
            return {"deal_id": deal_id, "status": "no_documents"}

        classification_results = []
        for doc in docs:
            try:
                result = _classify_doc(client, db, deal_uuid, doc)
                classification_results.append(result)
            except Exception:
                logger.exception("Classification failed for %s, marking as other", doc.filename)
                doc.document_type = "other"
                doc.classification_confidence = 0.0
                doc.status = DocumentStatus.PARSED.value
                classification_results.append({
                    "doc_id": str(doc.id), "document_type": "other",
                    "confidence": 0.0, "extractable": False,
                })
        db.commit()

        # --- Extraction ---
        db = sync_session_factory()
        _transition_sync(db, deal_uuid, DealStatus.EXTRACTING.value)
        db.commit()

        extractable_doc_ids = {r["doc_id"] for r in classification_results if r.get("extractable")}

        db = sync_session_factory()
        extraction_results = []
        for doc_id_str in extractable_doc_ids:
            doc = db.query(Document).filter(Document.id == uuid.UUID(doc_id_str)).one()
            try:
                result = _extract_doc(client, db, deal_uuid, doc)
                extraction_results.append(result)
                db.commit()
            except Exception:
                logger.exception("Extraction failed for %s", doc.filename)
                db.rollback()
                db = sync_session_factory()
                doc = db.query(Document).filter(Document.id == uuid.UUID(doc_id_str)).one()
                doc.status = DocumentStatus.FAILED.value
                log_event_sync(
                    db=db, deal_id=deal_uuid,
                    event_type=EventType.EXTRACTION_FAILED.value,
                    payload={"doc_id": doc_id_str, "error": "extraction failed"},
                )
                db.commit()
                db = sync_session_factory()

        # --- Corroboration ---
        db = sync_session_factory()
        all_values = db.query(ExtractedValue).filter(ExtractedValue.deal_id == deal_uuid).all()

        if all_values:
            vdicts = [
                {
                    "field_name": v.field_name,
                    "source_doc_id": str(v.source_doc_id) if v.source_doc_id else None,
                    "confidence_score": v.confidence_score or 0.0,
                    "confidence_basis": v.confidence_basis or {},
                    "flag": v.flag, "_id": v.id,
                }
                for v in all_values
            ]
            apply_corroboration(vdicts)
            for vd in vdicts:
                ev = db.query(ExtractedValue).filter(ExtractedValue.id == vd["_id"]).one()
                ev.confidence_score = vd["confidence_score"]
                ev.confidence_basis = vd["confidence_basis"]
                ev.flag = vd["flag"]
        db.commit()

        # --- Cross-references ---
        db = sync_session_factory()
        try:
            xrefs = run_all_cross_references(deal_uuid, db)
            xref_summary = {
                "total": len(xrefs),
                "matches": sum(1 for x in xrefs if x.result == "match"),
                "mismatches": sum(1 for x in xrefs if x.result == "mismatch"),
                "within_tolerance": sum(1 for x in xrefs if x.result == "within_tolerance"),
                "unable_to_check": sum(1 for x in xrefs if x.result == "unable_to_check"),
            }
            db.commit()
        except Exception:
            logger.exception("Cross-references failed for deal %s", deal_id)
            db.rollback()
            xref_summary = {"error": "failed"}

        # --- Done ---
        db = sync_session_factory()
        _transition_sync(db, deal_uuid, DealStatus.EXTRACTION_REVIEW.value)
        db.commit()

        total_fields = sum(r.get("fields_extracted", 0) for r in extraction_results)
        summary = {
            "deal_id": deal_id, "status": "completed",
            "documents_classified": len(classification_results),
            "documents_extracted": len(extraction_results),
            "total_fields_extracted": total_fields,
            "cross_references": xref_summary,
        }
        logger.info("Pipeline complete for deal %s: %s", deal_id, summary)
        return summary

    except Exception as exc:
        logger.exception("Pipeline failed for deal %s", deal_id)
        try:
            db = sync_session_factory()
            _transition_sync(db, deal_uuid, DealStatus.EXTRACTION_FAILED.value)
            log_event_sync(
                db=db, deal_id=deal_uuid,
                event_type=EventType.EXTRACTION_FAILED.value,
                payload={"error": str(exc)},
            )
            db.commit()
        except Exception:
            logger.exception("Failed to transition to EXTRACTION_FAILED")
        raise
    finally:
        db.close()
