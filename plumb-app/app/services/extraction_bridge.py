"""Bridge: map extracted values and agent results onto Deal model columns.

After the extraction and research agents finish, the orchestrator calls these
functions so that downstream consumers (financial engine, OM renderer, Excel
builder) find the data they expect on the Deal row.
"""

import asyncio
import json
import logging
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.deal import Deal
from app.models.extraction import ExtractedValue

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Sponsor field mapping
# ---------------------------------------------------------------------------

SPONSOR_FIELD_NAMES = [
    "sponsor_name", "sponsor_entity", "principal_names",
    "years_experience", "completed_projects", "current_projects",
    "total_units_developed", "total_sf_developed", "total_development_value",
    "credentials", "notable_achievements", "background",
]

SPONSOR_JSON_FIELDS = {
    "principal_names", "completed_projects", "current_projects",
    "credentials", "notable_achievements",
}


async def _resolve_extracted_sponsor(
    db: AsyncSession, deal_id: uuid.UUID,
) -> dict | None:
    """Query extracted_values for sponsor fields and return a sponsor dict
    compatible with what _build_om_context expects on deal.sponsor."""
    result = await db.execute(
        select(ExtractedValue)
        .where(
            ExtractedValue.deal_id == deal_id,
            ExtractedValue.field_name.in_(SPONSOR_FIELD_NAMES),
        )
        .order_by(ExtractedValue.confidence_score.desc())
    )
    rows = result.scalars().all()
    if not rows:
        return None

    seen: set[str] = set()
    flat: dict = {}
    for row in rows:
        if row.field_name in seen:
            continue
        seen.add(row.field_name)
        raw = row.override_value or row.value
        if not raw or raw.strip().upper() in ("<UNKNOWN>", "UNKNOWN", "N/A", "NONE"):
            continue
        if row.field_name in SPONSOR_JSON_FIELDS:
            try:
                flat[row.field_name] = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                flat[row.field_name] = raw
        else:
            flat[row.field_name] = raw

    if not flat:
        return None

    # Build a sponsor dict with "name" key (required by _build_om_context)
    return {
        "name": flat.get("sponsor_name", flat.get("sponsor_entity", "")),
        "sponsor_name": flat.get("sponsor_name", ""),
        "sponsor_entity": flat.get("sponsor_entity", ""),
        "principal_names": flat.get("principal_names", []),
        "years_experience": flat.get("years_experience"),
        "completed_projects": flat.get("completed_projects", []),
        "current_projects": flat.get("current_projects", []),
        "total_units_developed": flat.get("total_units_developed"),
        "total_sf_developed": flat.get("total_sf_developed"),
        "total_development_value": flat.get("total_development_value"),
        "credentials": flat.get("credentials", []),
        "notable_achievements": flat.get("notable_achievements", []),
        "background": flat.get("background"),
    }


# ---------------------------------------------------------------------------
# Financial model bridge
# ---------------------------------------------------------------------------

def _build_and_store_model_sync(deal_id: uuid.UUID) -> dict:
    """Run the deterministic financial engine (sync) and return model dict."""
    from app.db.session import sync_session_factory
    from app.financial.engine import build_financial_model

    db = sync_session_factory()
    try:
        model = build_financial_model(deal_id, db)
        return model.model_dump()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def bridge_extraction_to_deal(
    db: AsyncSession, deal_id: uuid.UUID,
) -> dict:
    """After extraction completes, populate deal.typed_extension and deal.sponsor
    from extracted values so downstream agents/tools find the data they need.

    Returns a summary dict of what was bridged.
    """
    result = await db.execute(select(Deal).where(Deal.id == deal_id))
    deal = result.scalar_one_or_none()
    if not deal:
        raise ValueError(f"Deal {deal_id} not found")

    bridged = {}

    # 1. Build financial model from extracted values → deal.typed_extension
    try:
        model_dict = await asyncio.to_thread(_build_and_store_model_sync, deal_id)
        deal.typed_extension = {
            **(deal.typed_extension or {}),
            "financial_model": model_dict,
        }
        bridged["financial_model"] = True
        logger.info("Bridged financial model for deal %s", deal_id)
    except Exception as e:
        logger.warning("Financial model bridge failed for deal %s: %s", deal_id, e)
        bridged["financial_model"] = False
        bridged["financial_model_error"] = str(e)

    # 2. Map sponsor fields → deal.sponsor
    sponsor = await _resolve_extracted_sponsor(db, deal_id)
    if sponsor:
        deal.sponsor = [sponsor]
        bridged["sponsor"] = True
        logger.info("Bridged sponsor data for deal %s", deal_id)
    else:
        bridged["sponsor"] = False

    deal.version += 1
    await db.flush()
    return bridged


async def bridge_research_to_deal(
    db: AsyncSession, deal_id: uuid.UUID, research_data: dict | None,
) -> dict:
    """After research completes, persist market intelligence to deal.market_context.

    Handles two shapes of research_data:
    - Structured dict with known keys (property_history, zoning, comps, etc.)
      → merge directly into market_context.
    - Flat ``{"text": "...markdown..."}`` from the research agent
      → store under a ``research_summary`` key so it doesn't pollute the
        namespace that OM templates expect.
    """
    if not research_data:
        return {"market_context": False}

    result = await db.execute(select(Deal).where(Deal.id == deal_id))
    deal = result.scalar_one_or_none()
    if not deal:
        raise ValueError(f"Deal {deal_id} not found")

    # Detect shape: if the only meaningful key is "text", treat as summary.
    _STRUCTURED_KEYS = {
        "property_history", "zoning", "permits", "news", "offering_plan",
        "comps", "market_stats", "dcf", "sales_comps", "rent_comps",
        "lease_comps", "submarket_name", "neighborhood", "borough",
        "zoning_district", "comparable_sales", "market_conditions",
    }
    if set(research_data.keys()) & _STRUCTURED_KEYS:
        # Already structured – merge as-is
        merged = research_data
    elif "text" in research_data:
        # Raw markdown report from the research agent
        merged = {"research_summary": research_data["text"]}
    else:
        # Unknown shape – merge as-is but log a warning
        logger.warning(
            "Research data for deal %s has unexpected keys: %s",
            deal_id, list(research_data.keys()),
        )
        merged = research_data

    # Safe merge: don't let empty research values (e.g. empty comp list,
    # empty string) clobber data already written by the extraction market
    # bridge. An empty value is a "no info" signal, not a correction.
    existing = deal.market_context or {}
    new_ctx = dict(existing)
    for k, v in merged.items():
        if v is None or v == "" or v == [] or v == {}:
            continue
        new_ctx[k] = v
    deal.market_context = new_ctx
    deal.version += 1
    await db.flush()

    logger.info("Bridged research/market context for deal %s", deal_id)
    return {"market_context": True}


# ---------------------------------------------------------------------------
# Market-context from extracted values
# ---------------------------------------------------------------------------

MARKET_FIELD_NAMES = [
    "comparable_sales", "market_conditions", "neighborhood",
    "zoning_district", "far", "lot_area", "borough",
    "mih_option", "special_district", "absorption_rate",
    "transit_access", "major_employers", "vacancy_rate",
    "median_rent", "population_growth",
]

MARKET_JSON_FIELDS = {"comparable_sales", "transit_access", "major_employers"}


def _parse_json_maybe(raw: Any) -> Any:
    """Try to JSON-decode a string; return as-is on failure."""
    if not isinstance(raw, str):
        return raw
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError, ValueError):
        return raw


def _comp_key(comp: Any) -> str:
    """Produce a dedup key for a comp record based on address + price."""
    if not isinstance(comp, dict):
        return str(comp)
    addr = str(comp.get("address", comp.get("name", ""))).strip().lower()
    price = str(comp.get("price", comp.get("sale_price", ""))).strip()
    return f"{addr}|{price}"


async def _resolve_market_context_from_extractions(
    db: AsyncSession, deal_id: uuid.UUID,
) -> dict | None:
    """Query extracted_values for market-relevant fields and return a
    structured dict suitable for merging into deal.market_context.

    Scalar fields use the highest-confidence row.  ``comparable_sales`` is
    special: we merge comp lists from all source documents (deduped by
    address+price) so comps from both the appraisal and the pro forma end up
    in the OM.
    """
    result = await db.execute(
        select(ExtractedValue)
        .where(
            ExtractedValue.deal_id == deal_id,
            ExtractedValue.field_name.in_(MARKET_FIELD_NAMES),
        )
        .order_by(ExtractedValue.confidence_score.desc().nullslast())
    )
    rows = result.scalars().all()
    if not rows:
        return None

    # Collect scalar fields with first-seen-wins (already ordered by conf desc).
    scalar_seen: set[str] = set()
    flat: dict = {}

    # Merge list fields (comparable_sales, transit_access, major_employers)
    # across multiple source documents, deduplicated by _comp_key.
    merged_comps: list = []
    comp_keys: set[str] = set()
    merged_transit: list = []
    merged_employers: list = []

    for row in rows:
        raw = row.override_value or row.value
        if not raw or raw.strip().upper() in ("<UNKNOWN>", "UNKNOWN", "N/A", "NONE"):
            continue

        if row.field_name == "comparable_sales":
            parsed = _parse_json_maybe(raw)
            if isinstance(parsed, list):
                for comp in parsed:
                    key = _comp_key(comp)
                    if key not in comp_keys:
                        comp_keys.add(key)
                        merged_comps.append(comp)
            elif isinstance(parsed, dict):
                key = _comp_key(parsed)
                if key not in comp_keys:
                    comp_keys.add(key)
                    merged_comps.append(parsed)
            continue

        if row.field_name == "transit_access":
            parsed = _parse_json_maybe(raw)
            if isinstance(parsed, list):
                merged_transit.extend(parsed)
            elif parsed:
                merged_transit.append(parsed)
            continue

        if row.field_name == "major_employers":
            parsed = _parse_json_maybe(raw)
            if isinstance(parsed, list):
                for e in parsed:
                    if e not in merged_employers:
                        merged_employers.append(e)
            elif parsed and parsed not in merged_employers:
                merged_employers.append(parsed)
            continue

        # Scalar field — first seen wins (sorted by confidence desc)
        if row.field_name in scalar_seen:
            continue
        scalar_seen.add(row.field_name)
        flat[row.field_name] = raw

    # Build structured market dict that OM templates expect
    ctx: dict = {}
    if "neighborhood" in flat:
        ctx["submarket_name"] = flat["neighborhood"]
        ctx["neighborhood"] = flat["neighborhood"]
    if "borough" in flat:
        ctx["borough"] = flat["borough"]
    if "zoning_district" in flat:
        ctx["zoning_district"] = flat["zoning_district"]
    if "far" in flat:
        ctx["far"] = flat["far"]
    if "lot_area" in flat:
        ctx["lot_area"] = flat["lot_area"]
    if "mih_option" in flat:
        ctx["mih_option"] = flat["mih_option"]
    if "special_district" in flat:
        ctx["special_district"] = flat["special_district"]
    if "market_conditions" in flat:
        ctx["market_conditions"] = flat["market_conditions"]
    if "absorption_rate" in flat:
        ctx["absorption_rate"] = flat["absorption_rate"]
    if "vacancy_rate" in flat:
        ctx["vacancy_rate"] = flat["vacancy_rate"]
    if "median_rent" in flat:
        ctx["median_rent"] = flat["median_rent"]
    if "population_growth" in flat:
        ctx["population_growth"] = flat["population_growth"]

    if merged_comps:
        # Expose under both keys so either OM template path finds them.
        ctx["sales_comps"] = merged_comps
        ctx["comparable_sales"] = merged_comps
    if merged_transit:
        ctx["transit_access"] = merged_transit
    if merged_employers:
        ctx["major_employers"] = merged_employers

    return ctx or None


async def bridge_extraction_market_context(
    db: AsyncSession, deal_id: uuid.UUID,
) -> dict:
    """Populate deal.market_context from extracted_values.

    Designed to be called standalone (e.g. backfill) or from the orchestrator
    after extraction completes. Merges into existing market_context so it
    doesn't overwrite research-agent data.
    """
    result = await db.execute(select(Deal).where(Deal.id == deal_id))
    deal = result.scalar_one_or_none()
    if not deal:
        raise ValueError(f"Deal {deal_id} not found")

    market = await _resolve_market_context_from_extractions(db, deal_id)
    if not market:
        logger.info("No market extraction fields found for deal %s", deal_id)
        return {"market_context": False, "fields": []}

    deal.market_context = {
        **(deal.market_context or {}),
        **market,
    }
    deal.version += 1
    await db.flush()

    logger.info(
        "Bridged extraction market context for deal %s – keys: %s",
        deal_id, list(market.keys()),
    )
    return {"market_context": True, "fields": list(market.keys())}
