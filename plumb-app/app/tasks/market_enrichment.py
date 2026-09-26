"""Celery task: orchestrate the full market enrichment pipeline for a deal."""

import asyncio
import json
import logging
import uuid

import httpx

from app.db.events import log_event_sync
from app.db.session import sync_session_factory
from app.extraction.market_handler import extract_market_doc, is_market_doc
from app.fetchers.nyc.geoclient import geocode_address
from app.fetchers.registry import detect_geography, get_fetchers
from app.importers.registry import detect_importer
from app.market.context import assemble_market_context
from app.market.sponsor_portfolio import assemble_sponsor_portfolio
from app.models.deal import Deal
from app.models.document import Document
from app.models.market import MarketData
from app.prompts.client import PlumbLLMClient
from app.schemas.enums import DealStatus, EventType
from app.storage.s3 import download_document
from app.worker import celery_app

logger = logging.getLogger(__name__)


def _transition_sync(db, deal_id: uuid.UUID, target_status: str) -> None:
    """Simple sync state transition (auto-gate only)."""
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


async def _run_fetchers(
    deal_id: uuid.UUID,
    property_address: str,
    sponsor_name: str | None,
    project_name: str | None,
    geography: str,
    db_factory,
) -> dict[str, dict]:
    """Run all public data fetchers concurrently via asyncio."""
    fetchers = get_fetchers(geography)
    if not fetchers:
        return {}

    results = {}
    async with httpx.AsyncClient(timeout=30.0) as client:
        geo = None
        if geography == "nyc":
            geo = await geocode_address(property_address, client)
            if geo is None:
                logger.warning("GeoSearch failed for '%s', skipping property-specific fetchers", property_address)

        tasks = []
        fetcher_names = []

        for name, fetcher in fetchers.items():
            db = db_factory()
            cache_key = f"{fetcher.data_source}:{property_address}"

            kwargs = {"client": client}
            if name in ("zoning", "property_records", "permits") and geo:
                kwargs["geo"] = geo
            elif name in ("zoning", "property_records", "permits") and not geo:
                results[name] = {"error": "GeoSearch failed, cannot query without BBL/BIN"}
                continue

            if name == "permits":
                kwargs["sponsor_name"] = sponsor_name
            if name == "news":
                kwargs["property_address"] = property_address
                kwargs["developer_name"] = sponsor_name
                kwargs["project_name"] = project_name
            if name == "offering_plan":
                kwargs["property_address"] = property_address
                kwargs["sponsor_name"] = sponsor_name

            tasks.append(fetcher.fetch_with_cache(cache_key, db, **kwargs))
            fetcher_names.append((name, fetcher, db))

        if tasks:
            fetcher_results = await asyncio.gather(*tasks, return_exceptions=True)
            for (name, fetcher, db), result in zip(fetcher_names, fetcher_results):
                if isinstance(result, Exception):
                    logger.error("Fetcher %s raised: %s", name, result)
                    results[name] = {"error": str(result)}
                    db.close()
                    continue

                try:
                    interpreted = fetcher.interpret(result.raw_data, {"deal_id": str(deal_id)})
                    result.interpreted_data = interpreted
                    fetcher.save_market_data(db, deal_id, result)
                    db.commit()
                    results[name] = {
                        "status": "success",
                        "from_cache": result.from_cache,
                        "data_type": result.data_type,
                    }
                except Exception as exc:
                    logger.error("Fetcher %s interpret/save failed: %s", name, exc)
                    db.rollback()
                    results[name] = {"error": str(exc)}
                finally:
                    db.close()

    return results


@celery_app.task(bind=True, max_retries=0)
def run_market_enrichment(self, deal_id: str, actor_id: str | None = None) -> dict:
    """Orchestrate the full market enrichment pipeline:

    1. Transition to MARKET_ENRICHMENT
    2. Detect geography from property_address
    3. Run all public data fetchers (parallel via asyncio)
    4. Extract from any market research PDFs uploaded
    5. Import any structured data files uploaded
    6. Assemble sponsor portfolio
    7. Assemble unified market_context
    8. Run borrower assumption validation
    9. Store market_context on deal
    10. Transition to OM_DRAFTING
    """
    deal_uuid = uuid.UUID(deal_id)
    client = PlumbLLMClient()

    db = sync_session_factory()
    try:
        _transition_sync(db, deal_uuid, DealStatus.MARKET_ENRICHMENT.value)
        db.commit()

        db = sync_session_factory()
        deal = db.query(Deal).filter(Deal.id == deal_uuid).one()
        property_address = deal.property_address or ""
        sponsor_name = None
        if deal.sponsor and isinstance(deal.sponsor, dict):
            sponsor_name = deal.sponsor.get("name")
        project_name = deal.property_name

        geography = detect_geography(property_address)

        log_event_sync(
            db=db,
            deal_id=deal_uuid,
            event_type=EventType.PUBLIC_DATA_FETCHED.value,
            payload={"geography": geography, "address": property_address, "status": "started"},
        )
        db.commit()

        # --- 3. Run fetchers ---
        fetcher_results = {}
        if geography:
            fetcher_results = asyncio.run(
                _run_fetchers(
                    deal_uuid, property_address, sponsor_name,
                    project_name, geography, sync_session_factory,
                )
            )

        db = sync_session_factory()
        log_event_sync(
            db=db,
            deal_id=deal_uuid,
            event_type=EventType.PUBLIC_DATA_FETCHED.value,
            payload={"geography": geography, "fetcher_results": fetcher_results, "status": "completed"},
        )
        db.commit()

        # --- 4. Extract market research PDFs ---
        db = sync_session_factory()
        market_docs = (
            db.query(Document)
            .filter(
                Document.deal_id == deal_uuid,
                Document.document_type.in_(["market_research_report", "comp_report", "submarket_overview"]),
            )
            .all()
        )

        pdf_results = []
        for doc in market_docs:
            if is_market_doc(doc.document_type):
                try:
                    record = extract_market_doc(client, db, deal_uuid, doc)
                    if record:
                        pdf_results.append({"doc_id": str(doc.id), "status": "extracted"})
                        db.commit()
                    else:
                        pdf_results.append({"doc_id": str(doc.id), "status": "skipped"})
                except Exception as exc:
                    logger.error("Market PDF extraction failed for %s: %s", doc.filename, exc)
                    pdf_results.append({"doc_id": str(doc.id), "status": "failed", "error": str(exc)})
                    db.rollback()
                    db = sync_session_factory()

        # --- 5. Import structured data files ---
        db = sync_session_factory()
        import_docs = (
            db.query(Document)
            .filter(
                Document.deal_id == deal_uuid,
                Document.document_type.in_(["costar_export", "argus_dcf"]),
            )
            .all()
        )

        import_results = []
        for doc in import_docs:
            try:
                file_bytes = download_document(doc.s3_key)
                importer = detect_importer(file_bytes, doc.filename)
                if importer:
                    result = importer.run(file_bytes, doc.filename)
                    md = MarketData(
                        deal_id=deal_uuid,
                        data_source=result.data_source,
                        data_type=result.data_type,
                        data={"records": result.records, "warnings": result.warnings},
                        source_doc_id=doc.id,
                        confidence_score=0.9,
                    )
                    db.add(md)
                    import_results.append({
                        "doc_id": str(doc.id),
                        "importer": importer.data_source,
                        "records": len(result.records),
                        "warnings": result.warnings,
                    })
                    db.commit()
            except Exception as exc:
                logger.error("Structured import failed for %s: %s", doc.filename, exc)
                import_results.append({"doc_id": str(doc.id), "error": str(exc)})
                db.rollback()
                db = sync_session_factory()

        # --- 6. Assemble sponsor portfolio ---
        db = sync_session_factory()
        try:
            sponsor_portfolio = assemble_sponsor_portfolio(deal_uuid, db)
            db.commit()
        except Exception as exc:
            logger.error("Sponsor portfolio assembly failed: %s", exc)
            sponsor_portfolio = {"error": str(exc)}
            db.rollback()

        # --- 7. Assemble unified market_context ---
        db = sync_session_factory()
        market_context = assemble_market_context(deal_uuid, db)
        market_context["sponsor_portfolio"] = sponsor_portfolio
        db.close()

        # --- 8. Run borrower assumption validation ---
        db = sync_session_factory()
        try:
            from app.models.extraction import ExtractedValue
            extracted = (
                db.query(ExtractedValue)
                .filter(ExtractedValue.deal_id == deal_uuid)
                .all()
            )
            ev_dict = {}
            for ev in extracted:
                val = ev.override_value if ev.override_value else ev.value
                ev_dict[ev.field_name] = val

            validation = client.call_llm(
                "validate_assumptions",
                {"deal_id": str(deal_uuid)},
                {
                    "extracted_values": json.dumps(ev_dict),
                    "market_context": json.dumps(market_context, default=str),
                    "sponsor_portfolio": json.dumps(sponsor_portfolio, default=str),
                },
                db=db,
                deal_id=deal_uuid,
            )
            market_context["validation_flags"] = validation.get("validation_flags", [])
            market_context["overall_assessment"] = validation.get("overall_assessment")
            market_context["validation_summary"] = validation.get("summary")
            db.commit()
        except Exception as exc:
            logger.error("Assumption validation failed: %s", exc)
            market_context["validation_flags"] = []
            market_context["validation_error"] = str(exc)

        # --- 9. Store market_context on deal ---
        db = sync_session_factory()
        deal = db.query(Deal).filter(Deal.id == deal_uuid).with_for_update().one()
        deal.market_context = market_context
        db.commit()

        # --- 10. Transition to MODEL_BUILDING and chain ---
        db = sync_session_factory()
        _transition_sync(db, deal_uuid, DealStatus.MODEL_BUILDING.value)
        db.commit()

        summary = {
            "deal_id": deal_id,
            "status": "completed",
            "geography": geography,
            "fetcher_results": fetcher_results,
            "market_pdfs_processed": len(pdf_results),
            "structured_imports": len(import_results),
            "validation_flags": len(market_context.get("validation_flags", [])),
        }
        logger.info("Market enrichment complete for deal %s: %s", deal_id, summary)

        # Chain to model building
        from app.tasks.model_building import run_model_building

        run_model_building.delay(deal_id, actor_id)

        return summary

    except Exception as exc:
        logger.exception("Market enrichment failed for deal %s", deal_id)
        try:
            db = sync_session_factory()
            deal = db.query(Deal).filter(Deal.id == deal_uuid).with_for_update().one()
            deal.status = DealStatus.MODEL_BUILDING.value
            deal.version += 1
            log_event_sync(
                db=db,
                deal_id=deal_uuid,
                event_type=EventType.STATE_TRANSITION.value,
                payload={"error": str(exc), "rollback": "market_enrichment_failed"},
            )
            db.commit()
        except Exception:
            logger.exception("Failed to rollback from MARKET_ENRICHMENT")
        raise
    finally:
        db.close()
