"""Celery task: run cross-reference checks on extracted values."""

import logging
import uuid

from app.db.events import log_event_sync
from app.db.session import sync_session_factory
from app.extraction.cross_references import run_all_cross_references
from app.schemas.enums import EventType
from app.worker import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=1, default_retry_delay=30)
def run_cross_references(self, deal_id: str) -> dict:
    """Run all cross-reference rules for a deal.

    Should be called after all document extractions are complete.
    """
    deal_uuid = uuid.UUID(deal_id)

    db = sync_session_factory()
    try:
        xrefs = run_all_cross_references(deal_uuid, db)

        summary = {
            "total_rules": len(xrefs),
            "matches": sum(1 for x in xrefs if x.result == "match"),
            "mismatches": sum(1 for x in xrefs if x.result == "mismatch"),
            "within_tolerance": sum(1 for x in xrefs if x.result == "within_tolerance"),
            "unable_to_check": sum(1 for x in xrefs if x.result == "unable_to_check"),
        }

        log_event_sync(
            db=db,
            deal_id=deal_uuid,
            event_type=EventType.EXTRACTION_COMPLETED.value,
            payload={"cross_reference_summary": summary},
        )

        db.commit()
        logger.info("Cross-references for deal %s: %s", deal_id, summary)
        return summary

    except Exception as exc:
        db.rollback()
        logger.exception("Cross-reference check failed for deal %s", deal_id)
        raise self.retry(exc=exc)
    finally:
        db.close()
