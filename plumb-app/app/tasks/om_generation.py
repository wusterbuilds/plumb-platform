"""Celery task: generate an Offering Memorandum PDF."""

import json
import logging
import uuid
from collections import OrderedDict

from sqlalchemy import func

from app.db.events import log_event_sync
from app.db.session import sync_session_factory
from app.models.deal import Deal
from app.models.image import DealImage
from app.models.om import OMVersion
from app.schemas.enums import EventType
from app.storage.s3 import get_presigned_url
from app.worker import celery_app

import app.om.narratives  # noqa: F401 — registers narrative prompts

logger = logging.getLogger(__name__)


def _fmt_stat(val) -> str:
    """Format a numeric value for property stats display."""
    if val is None:
        return ""
    try:
        num = float(val)
        if num == 0:
            return "0"
        return f"{int(num):,}" if num == int(num) else f"{num:,.0f}"
    except (TypeError, ValueError):
        return str(val)


_NYC_BOROUGHS = {
    "manhattan", "brooklyn", "queens", "bronx", "staten island",
    "new york", "new york county", "kings", "kings county",
    "queens county", "bronx county", "richmond", "richmond county",
}

_NON_NYC_STATE_TOKENS = (
    ", nj", " new jersey", ", ct", " connecticut", ", pa", " pennsylvania",
    ", ma", " massachusetts",
)


def _reconcile_property_address(deal: "Deal", fm: dict) -> str:
    """Return the best display address for the property.

    The stored ``deal.property_address`` is set at deal creation (often to a
    placeholder or marketing name) and is NOT re-extracted from documents.
    The extraction pipeline does capture borough and zoning into the
    financial-model inputs and market_context — those are the authoritative
    signals for geography. If the stored address contradicts an extracted NYC
    borough (e.g. borough=Queens but address contains ', NJ'), prefer a
    composed display address built from the extracted components so that
    downstream narrative prompts are not fed a false premise.
    """
    stored = (deal.property_address or "").strip()
    mc = deal.market_context or {}
    inputs = (fm or {}).get("inputs", {}) or {}

    borough = (mc.get("borough") or inputs.get("borough") or "").strip()
    neighborhood = (mc.get("neighborhood") or inputs.get("neighborhood") or "").strip()

    if not borough:
        return stored

    stored_lower = stored.lower()
    stored_conflicts = any(tok in stored_lower for tok in _NON_NYC_STATE_TOKENS)

    if stored_conflicts or not stored or stored.lower() == borough.lower():
        parts = [p for p in (neighborhood, borough, "NY") if p]
        composed = ", ".join(parts)
        if stored_conflicts:
            logger.warning(
                "property_address %r contradicts extracted borough %r — using composed address %r",
                stored, borough, composed,
            )
        return composed

    return stored


def _build_formatted_property_stats(deal: Deal, fm: dict) -> dict:
    """Build property stats dict with human-readable labels and formatted values."""
    # Pull from financial model top-level fields and deal's typed_extension
    ext = deal.typed_extension or {}
    stats = OrderedDict()

    stats["Address"] = _reconcile_property_address(deal, fm)

    # Try to get zoning/borough from market_context or extracted values
    mc = deal.market_context or {}
    borough = mc.get("borough", "")
    zoning = mc.get("zoning_district", "")

    if borough:
        stats["Borough"] = borough
    if zoning:
        stats["Zoning"] = zoning

    # Area metrics — pull from financial model top-level
    zfa = fm.get("zfa") if fm else None
    gsf = fm.get("total_gsf") if fm else None
    total_units = fm.get("total_units") if fm else None
    nra = fm.get("nra") if fm else None

    if zfa:
        stats["ZFA"] = _fmt_stat(zfa)
    if gsf:
        stats["GSF"] = _fmt_stat(gsf)
    if total_units:
        stats["Total Units"] = _fmt_stat(total_units)
    if nra and nra != gsf:
        stats["Net Rentable Area"] = _fmt_stat(nra)

    # Financial summary stats
    tdc = fm.get("total_development_cost") if fm else None
    loan = fm.get("loan_amount") if fm else None
    ltc = fm.get("ltc") if fm else None
    condo = fm.get("condo_sellout") if fm else None

    if tdc:
        stats["Total Dev. Cost"] = f"${tdc:,.0f}"
    if loan:
        stats["Loan Amount"] = f"${loan:,.0f}"
    if ltc:
        stats["LTC"] = f"{ltc * 100:.1f}%"
    if condo and condo.get("projected_sellout"):
        stats["Gross Sellout"] = f"${condo['projected_sellout']:,.0f}"

    # Remove entries with empty/null values
    return OrderedDict((k, v) for k, v in stats.items() if v not in (None, ""))


def _build_deal_context(deal: Deal, fm: dict) -> dict:
    """Build deal_context dict for narrative prompts.

    This assembles a rich context from the deal record and financial model so
    that every narrative prompt has access to specific numbers.  The prompts
    should never have to dig into nested dicts — everything important is
    surfaced at the top level.
    """
    inputs = fm.get("inputs", {}) if fm else {}
    valuation = fm.get("valuation", {}) if fm else {}
    sources_uses = fm.get("sources_uses", {}) if fm else {}
    condo = fm.get("condo_sellout") if fm else None

    # Sponsor — deal.sponsor is stored as a list of sponsor dicts
    sponsors = deal.sponsor if isinstance(deal.sponsor, list) else (
        [deal.sponsor] if deal.sponsor else []
    )
    primary_sponsor = sponsors[0] if sponsors and isinstance(sponsors[0], dict) else {}
    sponsor_names = ", ".join(
        s.get("name", s.get("sponsor_name", "")) for s in sponsors if isinstance(s, dict)
    ) or "N/A"

    mc = deal.market_context or {}

    reconciled_address = _reconcile_property_address(deal, fm)

    ctx = {
        # Core deal info
        "deal_type": deal.deal_type,
        "property_name": deal.property_name,
        "property_address": reconciled_address,
        "borough": mc.get("borough") or inputs.get("borough", ""),
        "neighborhood": inputs.get("neighborhood") or mc.get("neighborhood", ""),

        # Sponsor — flat fields for easy access
        "sponsor_names": sponsor_names,
        "sponsor_entity": primary_sponsor.get("sponsor_entity", ""),
        "sponsor_experience": primary_sponsor.get("years_experience"),
        "completed_projects": primary_sponsor.get("completed_projects", []),
        "current_projects": primary_sponsor.get("current_projects", []),
        "total_units_developed": primary_sponsor.get("total_units_developed"),
        "total_sf_developed": primary_sponsor.get("total_sf_developed"),
        "total_development_value": primary_sponsor.get("total_development_value"),
        "principal_names": primary_sponsor.get("principal_names", []),

        # Full sponsor list (for sponsor bio iteration)
        "sponsor": deal.sponsor,

        # Loan & cost metrics
        "loan_amount": fm.get("loan_amount") if fm else None,
        "total_development_cost": fm.get("total_development_cost") if fm else None,
        "ltc": fm.get("ltc") if fm else None,
        "equity": fm.get("equity") if fm else None,
        "units": fm.get("total_units") if fm else None,
        "gsf": fm.get("total_gsf") if fm else None,
        "zfa": fm.get("zfa") if fm else None,
        "nra": fm.get("nra") if fm else None,
        "interest_rate": valuation.get("interest_rate"),

        # Zoning & regulatory — cascade through multiple sources
        "zoning": (
            inputs.get("zoning_district")
            or mc.get("zoning_district")
            or (mc.get("zoning", {}).get("zoning_district") if isinstance(mc.get("zoning"), dict) else "")
            or (deal.regulatory or {}).get("zoning_district", "")
            or ""
        ),
        "special_district": inputs.get("special_district") or mc.get("special_district", ""),
        "abatement_program": inputs.get("abatement_program") or mc.get("abatement_program", ""),
        "commercial_sf": inputs.get("commercial_sf", 0),
        "parking_spaces": inputs.get("parking_spaces", 0),

        # Stabilized return metrics (rental deals)
        "stabilized_value": valuation.get("stabilized_value"),
        "noi": valuation.get("noi"),
        "cap_rate": valuation.get("cap_rate"),
        "dscr": valuation.get("dscr"),
        "debt_yield": valuation.get("debt_yield"),

        # Full nested objects (prompts can dig in if needed)
        "regulatory": deal.regulatory,
        "market_context": mc,
        "financial_model": fm,
    }

    # Condo sellout metrics — surface at top level when available
    if condo:
        ctx.update({
            "gross_sellout": condo.get("projected_sellout"),
            "profit": condo.get("profit"),
            "profit_margin": condo.get("profit_margin_on_cost"),
            "per_unit_sellout": condo.get("per_unit_sellout"),
            "per_sf_sellout": condo.get("per_sf_sellout"),
            "per_unit_cost": condo.get("per_unit_cost"),
            "per_sf_cost": condo.get("per_sf_cost"),
            "return_on_equity": condo.get("return_on_equity"),
            "appraised_value": condo.get("appraised_value"),
            "ltv": condo.get("ltv"),
        })

    # Market comparable sales (from appraisal extraction or market research)
    comps = mc.get("comps", [])
    sales_comps = mc.get("sales_comps", [])
    comparable_sales = mc.get("comparable_sales", [])
    ctx["comparable_sales"] = comparable_sales or sales_comps or comps

    # Zoning detail from market_context (fetched from public data)
    zoning_mc = mc.get("zoning", {})
    if isinstance(zoning_mc, dict) and zoning_mc.get("status") != "unavailable":
        ctx["zoning_detail"] = zoning_mc

    return ctx


def _build_om_context(deal: Deal, fm: dict, images: list[DealImage], narratives: dict) -> dict:
    """Build OMContext-compatible dict from deal data, financial model, images, and narratives."""
    from app.om.schemas import OMContext

    # Organize images by type
    hero_image_url = None
    rendering_images = []
    lot_map_url = None
    market_images = []
    sponsor_images: dict[str, list[str]] = {}

    for img in images:
        try:
            url = get_presigned_url(img.s3_key)
        except Exception:
            continue

        if img.image_type == "hero_rendering" and hero_image_url is None:
            hero_image_url = url
        elif img.image_type in ("exterior_rendering", "interior_rendering", "aerial_rendering"):
            rendering_images.append({"url": url, "caption": img.caption or ""})
        elif img.image_type == "lot_map" and lot_map_url is None:
            lot_map_url = url
        elif img.image_type == "market_map":
            market_images.append({"url": url, "caption": img.caption or ""})
        elif img.image_type in ("sponsor_logo", "sponsor_photo"):
            entity = img.associated_entity or "unknown"
            sponsor_images.setdefault(entity, []).append(url)

    # Build sponsor data
    sponsor_data = []
    sponsors = deal.sponsor if isinstance(deal.sponsor, list) else ([deal.sponsor] if deal.sponsor else [])
    for sponsor in sponsors:
        if not isinstance(sponsor, dict):
            continue
        name = sponsor.get("name", sponsor.get("sponsor_name", ""))
        if name:
            sponsor_data.append({
                "name": name,
                "narrative": narratives.get("sponsor_bios", {}).get(name, []),
                "logos": sponsor_images.get(name, []),
                "projects": sponsor.get("projects", []),
            })

    # Build property stats with human-readable labels
    property_stats = _build_formatted_property_stats(deal, fm)

    # Extract comps from market context
    mc = deal.market_context or {}
    rent_comps = mc.get("rent_comps", [])
    sales_comps = mc.get("sales_comps", mc.get("comparable_sales", []))
    lease_comps = mc.get("lease_comps", [])

    reconciled_address = _reconcile_property_address(deal, fm)

    return OMContext(
        deal_id=str(deal.id),
        property_name=deal.property_name or reconciled_address or "",
        property_address=reconciled_address,
        deal_type_label="CONSTRUCTION FINANCING",
        financial_model=fm,
        market_context=mc,
        transaction_overview=narratives.get("transaction_overview", []),
        investment_highlights=narratives.get("investment_highlights", []),
        market_narrative=narratives.get("market_narrative", []),
        sponsor_bios=narratives.get("sponsor_bios", {}),
        hero_image_url=hero_image_url,
        rendering_images=rendering_images,
        lot_map_url=lot_map_url,
        market_images=market_images,
        sponsor_data=sponsor_data,
        rent_comps=rent_comps,
        sales_comps=sales_comps,
        lease_comps=lease_comps,
        property_stats=property_stats,
        sponsors=sponsors if isinstance(sponsors, list) else [],
    ).model_dump()


def _render_om_pages(om_context_dict: dict) -> tuple[bytes, int, list[str]]:
    """Render OM pages to PDF via the OM builder module."""
    from app.om.builder import build_om
    from app.om.schemas import OMContext

    ctx = OMContext(**om_context_dict)
    return build_om(ctx)


@celery_app.task(bind=True, max_retries=0)
def run_om_generation(
    self, deal_id: str, actor_id: str | None = None, regenerate_narratives: bool = True
) -> dict:
    """Generate an Offering Memorandum PDF."""
    deal_uuid = uuid.UUID(deal_id)
    db = sync_session_factory()

    try:
        deal = db.query(Deal).filter(Deal.id == deal_uuid).one()

        # 1. Get financial model
        fm = (deal.typed_extension or {}).get("financial_model")
        if not fm:
            raise ValueError("Financial model not calculated. Run model building first.")

        # 2. Get images
        images = db.query(DealImage).filter(DealImage.deal_id == deal_uuid).order_by(DealImage.sort_order).all()

        # 3. Generate narratives (or reuse existing)
        narratives: dict = {}
        applied_lessons: list[str] = []
        if regenerate_narratives:
            from app.prompts.client import PlumbLLMClient
            from app.services.redline_service import (
                compute_archetype,
                fetch_relevant_lessons_sync,
            )

            client = PlumbLLMClient()
            deal_context = _build_deal_context(deal, fm)
            # Pull archetype-relevant correction lessons and surface them in
            # deal_context. PlumbLLMClient.call_llm appends them to the system
            # prompt so every narrative prompt benefits without per-prompt
            # changes.
            applied_lessons = fetch_relevant_lessons_sync(db, deal=deal, limit=10)
            if applied_lessons:
                deal_context["past_corrections"] = applied_lessons
                logger.info(
                    "OM regeneration applying %d expert correction(s) for deal %s archetype %s",
                    len(applied_lessons), deal_id, compute_archetype(deal),
                )

            # Transaction overview
            try:
                result = client.call_llm(
                    "generate_transaction_overview", deal_context,
                    {"financial_model": fm}, db=db, deal_id=deal_uuid,
                )
                narratives["transaction_overview"] = result.get("paragraphs", [])
            except Exception as exc:
                logger.warning("Transaction overview generation failed: %s", exc)
                narratives["transaction_overview"] = []

            # Investment highlights
            try:
                result = client.call_llm(
                    "generate_investment_highlights", deal_context,
                    {"financial_model": fm}, db=db, deal_id=deal_uuid,
                )
                narratives["investment_highlights"] = result.get("highlights", [])
            except Exception as exc:
                logger.warning("Investment highlights generation failed: %s", exc)
                narratives["investment_highlights"] = []

            # Market narrative
            try:
                result = client.call_llm(
                    "generate_market_narrative", deal_context,
                    {"market_context": deal.market_context or {}}, db=db, deal_id=deal_uuid,
                )
                narratives["market_narrative"] = result.get("sections", [])
            except Exception as exc:
                logger.warning("Market narrative generation failed: %s", exc)
                narratives["market_narrative"] = []

            # Sponsor bios
            sponsor_bios: dict[str, list[str]] = {}
            sponsors = deal.sponsor if isinstance(deal.sponsor, list) else (
                [deal.sponsor] if deal.sponsor else []
            )
            for sponsor in sponsors:
                if not isinstance(sponsor, dict):
                    continue
                name = sponsor.get("name", sponsor.get("sponsor_name", ""))
                if name:
                    try:
                        result = client.call_llm(
                            "generate_sponsor_bio", deal_context,
                            {"sponsor": sponsor}, db=db, deal_id=deal_uuid,
                        )
                        sponsor_bios[name] = result.get("paragraphs", [])
                    except Exception as exc:
                        logger.warning("Sponsor bio generation failed for %s: %s", name, exc)
                        sponsor_bios[name] = []
            narratives["sponsor_bios"] = sponsor_bios
        else:
            # Reuse existing narratives from latest OM version
            latest = (
                db.query(OMVersion)
                .filter(OMVersion.deal_id == deal_uuid, OMVersion.status == "ready")
                .order_by(OMVersion.version_number.desc())
                .first()
            )
            if latest and latest.narrative_snapshot:
                narratives = latest.narrative_snapshot

        # 4. Build OM context
        om_context_dict = _build_om_context(deal, fm, images, narratives)

        # 5. Render OM pages to PDF
        pdf_bytes, page_count, html_pages = _render_om_pages(om_context_dict)

        # 6. Upload to S3
        from app.config import settings
        from app.storage.s3 import _get_client

        s3_client = _get_client()

        # Get next version number
        max_version = (
            db.query(func.max(OMVersion.version_number))
            .filter(OMVersion.deal_id == deal_uuid)
            .scalar()
        ) or 0
        version_number = max_version + 1

        pdf_key = f"deals/{deal_id}/om/v{version_number}/om.pdf"
        s3_client.put_object(
            Bucket=settings.S3_BUCKET_NAME,
            Key=pdf_key,
            Body=pdf_bytes,
            ContentType="application/pdf",
        )

        # Store HTML for preview
        html_key = f"deals/{deal_id}/om/v{version_number}/pages.json"
        s3_client.put_object(
            Bucket=settings.S3_BUCKET_NAME,
            Key=html_key,
            Body=json.dumps(html_pages).encode(),
            ContentType="application/json",
        )

        # 7. Create OMVersion record
        # Mark previous versions as superseded
        db.query(OMVersion).filter(
            OMVersion.deal_id == deal_uuid,
            OMVersion.status == "ready",
        ).update({"status": "superseded"})

        # Compute archetype once so the new version is taggable for both
        # exemplar retrieval and downstream metrics.
        try:
            from app.services.redline_service import compute_archetype as _compute_arch
            archetype_signature = _compute_arch(deal)
        except Exception:
            archetype_signature = None

        om_version = OMVersion(
            deal_id=deal_uuid,
            version_number=version_number,
            s3_key=pdf_key,
            html_s3_key=html_key,
            page_count=page_count,
            file_size=len(pdf_bytes),
            generated_by=uuid.UUID(actor_id) if actor_id else None,
            financial_model_snapshot=fm,
            narrative_snapshot=narratives,
            status="ready",
            archetype_signature=archetype_signature,
            applied_episodes=applied_lessons or None,
        )
        db.add(om_version)

        log_event_sync(
            db=db,
            deal_id=deal_uuid,
            event_type=EventType.OM_GENERATED.value,
            actor_id=uuid.UUID(actor_id) if actor_id else None,
            payload={
                "version_number": version_number,
                "page_count": page_count,
                "file_size": len(pdf_bytes),
            },
        )

        # Auto-transition to OM_REVIEW
        deal.status = "om_review"
        deal.version += 1
        log_event_sync(
            db=db,
            deal_id=deal_uuid,
            event_type=EventType.STATE_TRANSITION.value,
            actor_id=uuid.UUID(actor_id) if actor_id else None,
            payload={
                "from_status": "om_drafting",
                "to_status": "om_review",
                "transition_type": "forward",
            },
        )

        db.commit()

        return {
            "deal_id": deal_id,
            "version_number": version_number,
            "page_count": page_count,
            "status": "ready",
        }

    except Exception as exc:
        logger.exception("OM generation failed for deal %s", deal_id)
        db.rollback()
        raise
    finally:
        db.close()
