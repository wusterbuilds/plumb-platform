"""Celery task: MODEL_BUILDING — runs the financial model engine and starts OM drafting."""

import logging
import uuid

from app.db.events import log_event_sync
from app.db.session import sync_session_factory
from app.models.deal import Deal
from app.schemas.enums import DealStatus, EventType
from app.worker import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=0)
def run_model_building(self, deal_id: str, actor_id: str | None = None) -> dict:
    """Build the financial model for a deal and transition to OM drafting.

    1. Transition to MODEL_BUILDING
    2. Run the financial model engine
    3. Store results in deal.typed_extension
    4. Log MODEL_CALCULATED event
    5. Chain to OM generation
    """
    deal_uuid = uuid.UUID(deal_id)
    db = sync_session_factory()

    try:
        deal = db.query(Deal).filter(Deal.id == deal_uuid).with_for_update().one()
        old_status = deal.status
        deal.status = DealStatus.MODEL_BUILDING.value
        deal.version += 1

        log_event_sync(
            db=db,
            deal_id=deal_uuid,
            event_type=EventType.STATE_TRANSITION.value,
            actor_id=uuid.UUID(actor_id) if actor_id else None,
            payload={
                "from_status": old_status,
                "to_status": DealStatus.MODEL_BUILDING.value,
                "transition_type": "forward",
                "actor": "pipeline",
            },
        )
        db.commit()

        # Run the financial model engine
        from app.financial.engine import build_financial_model

        db = sync_session_factory()
        model = build_financial_model(deal_uuid, db)
        model_dict = model.model_dump()

        # Store results in typed_extension
        deal = db.query(Deal).filter(Deal.id == deal_uuid).with_for_update().one()
        deal.typed_extension = {**(deal.typed_extension or {}), "financial_model": model_dict}
        deal.version += 1

        log_event_sync(
            db=db,
            deal_id=deal_uuid,
            event_type=EventType.MODEL_CALCULATED.value,
            actor_id=uuid.UUID(actor_id) if actor_id else None,
            payload={
                "ltc": model.ltc,
                "noi": model.proforma.noi.total if model.proforma else None,
                "tdc": model.total_development_cost,
                "loan": model.loan_amount,
                "total_units": model.total_units,
                "errors": model.errors,
            },
        )

        db.commit()
        # Transition to OM_DRAFTING
        deal = db.query(Deal).filter(Deal.id == deal_uuid).with_for_update().one()
        deal.status = DealStatus.OM_DRAFTING.value
        deal.version += 1
        log_event_sync(
            db=db,
            deal_id=deal_uuid,
            event_type=EventType.STATE_TRANSITION.value,
            actor_id=uuid.UUID(actor_id) if actor_id else None,
            payload={
                "from_status": DealStatus.MODEL_BUILDING.value,
                "to_status": DealStatus.OM_DRAFTING.value,
                "transition_type": "forward",
                "actor": "pipeline",
            },
        )
        db.commit()

        logger.info(
            "Model building complete for deal %s (LTC=%.2f, TDC=%.0f), chaining to OM generation",
            deal_id, model.ltc, model.total_development_cost,
        )

        # Chain to OM generation
        from app.tasks.om_generation import run_om_generation

        run_om_generation.delay(deal_id, actor_id, True)

        return {"deal_id": deal_id, "status": "complete", "ltc": model.ltc}

    except Exception as exc:
        logger.exception("Model building failed for deal %s", deal_id)
        try:
            db.rollback()
            db = sync_session_factory()
            deal = db.query(Deal).filter(Deal.id == deal_uuid).with_for_update().one()
            deal.status = DealStatus.MODEL_ERROR.value
            deal.version += 1
            log_event_sync(
                db=db,
                deal_id=deal_uuid,
                event_type=EventType.MODEL_FAILED.value,
                payload={"error": str(exc)},
            )
            db.commit()
        except Exception:
            logger.exception("Failed to transition to MODEL_ERROR")
        raise
    finally:
        db.close()
