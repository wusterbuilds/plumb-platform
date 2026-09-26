"""Assemble unified market context from all market_data records for a deal."""

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.market import MarketData

logger = logging.getLogger(__name__)


def assemble_market_context(deal_id: uuid.UUID, db: Session) -> dict:
    """Read all market_data records for a deal and merge into a unified context.

    Handles graceful degradation: if a data source is missing, the section
    is null with a "status": "unavailable" marker.
    """
    records = (
        db.query(MarketData)
        .filter(MarketData.deal_id == deal_id)
        .order_by(MarketData.created_at.desc())
        .all()
    )

    by_type: dict[str, list[MarketData]] = {}
    for rec in records:
        by_type.setdefault(rec.data_type, []).append(rec)

    context = {
        "property_history": _build_section(by_type, "property_history"),
        "zoning": _build_section(by_type, "zoning"),
        "permits": _build_section(by_type, "permits"),
        "news": _build_section(by_type, "news", as_list=True),
        "offering_plan": _build_section(by_type, "offering_plan"),
        "comps": _build_section(by_type, "comps", as_list=True),
        "market_stats": _build_section(by_type, "market_stats"),
        "dcf": _build_section(by_type, "dcf"),
        "data_sources_used": _list_sources(records),
        "assembled_at": datetime.now(timezone.utc).isoformat(),
        "total_records": len(records),
    }

    return context


def _build_section(
    by_type: dict[str, list[MarketData]],
    data_type: str,
    as_list: bool = False,
) -> dict | list | None:
    """Build a section of the market context from matching records."""
    records = by_type.get(data_type, [])
    if not records:
        return {"status": "unavailable"} if not as_list else []

    if as_list:
        items = []
        for rec in records:
            item = rec.data or {}
            item["_source"] = rec.data_source
            item["_confidence"] = rec.confidence_score
            if isinstance(item.get("comparables"), list):
                for comp in item["comparables"]:
                    comp["_source"] = rec.data_source
                items.extend(item["comparables"])
            elif isinstance(item.get("articles"), list):
                for article in item["articles"]:
                    article["_source"] = rec.data_source
                items.extend(item["articles"])
            else:
                items.append(item)
        return items

    if len(records) == 1:
        result = records[0].data or {}
        result["_source"] = records[0].data_source
        result["_confidence"] = records[0].confidence_score
        return result

    merged = {}
    for rec in reversed(records):
        if rec.data:
            merged.update(rec.data)
            merged["_source"] = rec.data_source
            merged["_confidence"] = rec.confidence_score
    return merged


def _list_sources(records: list[MarketData]) -> list[dict]:
    """List all data sources used in the market context."""
    sources = {}
    for rec in records:
        key = f"{rec.data_source}:{rec.data_type}"
        if key not in sources:
            sources[key] = {
                "data_source": rec.data_source,
                "data_type": rec.data_type,
                "fetch_date": rec.fetch_date.isoformat() if rec.fetch_date else None,
                "confidence": rec.confidence_score,
                "source_url": rec.source_url,
            }
    return list(sources.values())
