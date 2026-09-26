"""OM tools — real implementations for agent-driven OM generation."""

import asyncio
import json
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.tools.base import PlumbTool, ToolContext, ToolPermission, ToolResult

logger = logging.getLogger(__name__)

# Fields extracted by ExtractSponsorPrompt that SponsorBioPrompt.build_input expects
SPONSOR_FIELD_NAMES = [
    "sponsor_name", "sponsor_entity", "principal_names",
    "years_experience", "completed_projects", "current_projects",
    "total_units_developed", "total_sf_developed", "total_development_value",
    "credentials", "notable_achievements", "background",
]

# Fields whose values are JSON-encoded lists/objects in ExtractedValue.value
SPONSOR_JSON_FIELDS = {
    "principal_names", "completed_projects", "current_projects",
    "credentials", "notable_achievements",
}


async def _build_sponsor_from_extractions(
    db: AsyncSession, deal_id: uuid.UUID,
) -> dict:
    """Query ExtractedValue records for sponsor fields and return a flat dict
    matching the keys that SponsorBioPrompt.build_input expects."""
    from app.models.extraction import ExtractedValue

    result = await db.execute(
        select(ExtractedValue)
        .where(
            ExtractedValue.deal_id == deal_id,
            ExtractedValue.field_name.in_(SPONSOR_FIELD_NAMES),
        )
        .order_by(ExtractedValue.confidence_score.desc())
    )
    rows = result.scalars().all()

    sponsor_data: dict = {}
    for row in rows:
        field = row.field_name
        # First (highest confidence) value wins per field
        if field in sponsor_data:
            continue
        raw = row.override_value if row.override_value else row.value
        if not raw or raw.strip().upper() in ("<UNKNOWN>", "UNKNOWN", "N/A", "NONE"):
            continue
        # Parse JSON-encoded list/object fields
        if field in SPONSOR_JSON_FIELDS:
            try:
                sponsor_data[field] = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                sponsor_data[field] = raw
        else:
            sponsor_data[field] = raw

    return sponsor_data


def _unwrap_section_outputs(raw_sections: dict) -> dict:
    """Transform agent generate_section outputs into the format _build_om_context expects.

    The agent collects generate_section results keyed by section name, where each
    value is the raw LLM output (e.g., {"paragraphs": [...]} for transaction_overview).
    _build_om_context expects the inner arrays directly:
      - transaction_overview → list[str]  (from "paragraphs")
      - investment_highlights → list[dict] (from "highlights")
      - market_narrative → list[dict]     (from "sections")
      - sponsor_bios → dict[str, list[str]] (from "paragraphs" per sponsor)
    """
    narratives: dict = {}
    for key, value in raw_sections.items():
        # Agent may wrap section output in {"content": {...}} or {"section_name": ..., "content": {...}}
        if isinstance(value, dict) and "content" in value and "section_name" in value:
            value = value["content"]
        elif isinstance(value, dict) and "content" in value and len(value) <= 2:
            value = value["content"]

        if key == "transaction_overview":
            if isinstance(value, dict):
                narratives[key] = value.get("paragraphs", value.get("content", []))
            elif isinstance(value, list):
                narratives[key] = value
            else:
                narratives[key] = []
        elif key == "investment_highlights":
            if isinstance(value, dict):
                narratives[key] = value.get("highlights", value.get("content", []))
            elif isinstance(value, list):
                narratives[key] = value
            else:
                narratives[key] = []
        elif key == "market_narrative":
            if isinstance(value, dict):
                narratives[key] = value.get("sections", value.get("content", []))
            elif isinstance(value, list):
                narratives[key] = value
            else:
                narratives[key] = []
        elif key in ("sponsor_bio", "sponsor_bios"):
            if isinstance(value, dict) and "paragraphs" in value:
                # Single sponsor result — use sponsor name from context or default
                narratives["sponsor_bios"] = {"Sponsor": value["paragraphs"]}
            elif isinstance(value, dict):
                # Already in name→paragraphs format, or nested sponsor results
                # Unwrap any inner {"paragraphs": [...]} values
                unwrapped = {}
                for name, bio in value.items():
                    if isinstance(bio, dict) and "paragraphs" in bio:
                        unwrapped[name] = bio["paragraphs"]
                    elif isinstance(bio, list):
                        unwrapped[name] = bio
                    else:
                        unwrapped[name] = [str(bio)] if bio else []
                narratives["sponsor_bios"] = unwrapped
            else:
                narratives["sponsor_bios"] = {}
        else:
            narratives[key] = value
    return narratives


def _load_persisted_sections_sync(deal_id: uuid.UUID) -> dict:
    """Load previously generated sections from S3 (sync, runs in thread)."""
    from app.config import settings
    from app.storage.s3 import _get_client

    section_names = [
        "transaction_overview", "investment_highlights",
        "market_narrative", "sponsor_bio",
    ]
    loaded: dict = {}
    try:
        s3_client = _get_client()
        for name in section_names:
            s3_key = f"deals/{deal_id}/om/sections/{name}.json"
            try:
                obj = s3_client.get_object(
                    Bucket=settings.S3_BUCKET_NAME, Key=s3_key,
                )
                loaded[name] = json.loads(obj["Body"].read().decode())
            except s3_client.exceptions.ClientError as e:
                if e.response["Error"].get("Code") in ("NoSuchKey", "404"):
                    continue
                logger.debug("Failed to load section %s from S3: %s", name, e)
            except Exception:
                logger.debug("Failed to load section %s from S3", name, exc_info=True)
    except Exception:
        logger.warning("Failed to connect to S3 for section loading", exc_info=True)
    return loaded


async def _load_persisted_sections(deal_id: uuid.UUID) -> dict:
    """Load previously generated sections from S3 as a fallback."""
    return await asyncio.to_thread(_load_persisted_sections_sync, deal_id)


def _generate_missing_narratives_sync(
    deal, fm: dict, narratives: dict, missing: list[str],
) -> dict:
    """Generate missing narratives using the sync LLM client (same as Celery path).

    This is a defensive fallback — the agent should have generated these via
    generate_section, but if it didn't, we fill them in so the OM is complete.
    """
    from app.prompts.client import PlumbLLMClient
    from app.tasks.om_generation import _build_deal_context

    client = PlumbLLMClient()
    deal_context = _build_deal_context(deal, fm)

    if "transaction_overview" in missing:
        try:
            result = client.call_llm(
                "generate_transaction_overview", deal_context,
                {"financial_model": fm},
            )
            narratives["transaction_overview"] = result.get("paragraphs", [])
        except Exception as exc:
            logger.warning("Fallback transaction_overview generation failed: %s", exc)

    if "investment_highlights" in missing:
        try:
            result = client.call_llm(
                "generate_investment_highlights", deal_context,
                {"financial_model": fm},
            )
            narratives["investment_highlights"] = result.get("highlights", [])
        except Exception as exc:
            logger.warning("Fallback investment_highlights generation failed: %s", exc)

    if "market_narrative" in missing:
        try:
            result = client.call_llm(
                "generate_market_narrative", deal_context,
                {"market_context": deal.market_context or {}},
            )
            narratives["market_narrative"] = result.get("sections", [])
        except Exception as exc:
            logger.warning("Fallback market_narrative generation failed: %s", exc)

    if "sponsor_bios" in missing:
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
                        {"sponsor": sponsor},
                    )
                    sponsor_bios[name] = result.get("paragraphs", [])
                except Exception as exc:
                    logger.warning("Fallback sponsor bio failed for %s: %s", name, exc)
        if sponsor_bios:
            narratives["sponsor_bios"] = sponsor_bios

    return narratives


class PositionDealTool(PlumbTool):
    name = "position_deal"
    description = "Identify the deal story, key selling points, risk mitigants, and recommended positioning."
    permission = ToolPermission.AUTO

    def get_input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "deal_context": {"type": "object", "description": "Full deal context (L1+L2+L3)"},
                "target_lenders": {"type": "array", "items": {"type": "object"}, "description": "Target lender profiles"},
            },
            "required": ["deal_context"],
        }

    async def execute(self, _ctx: ToolContext | None = None, deal_context: dict | None = None, target_lenders: list | None = None, **kwargs) -> ToolResult:
        if not _ctx or not _ctx.llm_client or not _ctx.db:
            return ToolResult(success=False, error="ToolContext with llm_client and db required")

        task_data = {
            "deal_context": deal_context or {},
            "target_lenders": target_lenders or [],
        }

        result = await _ctx.llm_client.execute(
            "position_deal", deal_context or {}, task_data,
            db=_ctx.db, deal_id=_ctx.deal_id,
        )

        return ToolResult(data=result)


class GenerateSectionTool(PlumbTool):
    name = "generate_section"
    description = "Generate one section of the OM with deal positioning context."
    permission = ToolPermission.AUTO

    def get_input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "section_name": {
                    "type": "string",
                    "description": "OM section: transaction_overview, investment_highlights, market_narrative, or sponsor_bio",
                },
                "deal_context": {"type": "object"},
                "positioning": {"type": "object", "description": "Deal positioning from position_deal tool"},
            },
            "required": ["section_name", "deal_context"],
        }

    async def execute(self, _ctx: ToolContext | None = None, section_name: str = "", deal_context: dict | None = None, positioning: dict | None = None, **kwargs) -> ToolResult:
        if not _ctx or not _ctx.llm_client or not _ctx.db:
            return ToolResult(success=False, error="ToolContext with llm_client and db required")

        # Map section names to registered narrative prompt names
        prompt_map = {
            "transaction_overview": "generate_transaction_overview",
            "investment_highlights": "generate_investment_highlights",
            "market_narrative": "generate_market_narrative",
            "sponsor_bio": "generate_sponsor_bio",
        }

        prompt_name = prompt_map.get(section_name)
        if not prompt_name:
            return ToolResult(success=False, error=f"Unknown section: {section_name}. Valid: {list(prompt_map.keys())}")

        # Build a FLAT deal context from the DB deal record.
        # The agent passes L1/L2/L3 layered context, but narrative prompts
        # expect a flat context with fields like loan_amount, sponsor_names,
        # etc. at the top level.  We rebuild it from the Deal row.
        from sqlalchemy import select as sa_select
        from app.models.deal import Deal

        deal_result = await _ctx.db.execute(
            sa_select(Deal).where(Deal.id == _ctx.deal_id)
        )
        deal = deal_result.scalar_one_or_none()
        if not deal:
            return ToolResult(success=False, error=f"Deal {_ctx.deal_id} not found")

        fm = (deal.typed_extension or {}).get("financial_model", {})

        # Use the same flat context builder as the Celery OM generation path
        from app.tasks.om_generation import _build_deal_context
        flat_dc = _build_deal_context(deal, fm)

        task_data = {
            "financial_model": fm,
            "market_context": deal.market_context or {},
            "positioning": positioning or {},
        }

        # Add sponsor data for sponsor_bio — pull from extracted values in DB
        if section_name == "sponsor_bio":
            sponsor_data = await _build_sponsor_from_extractions(_ctx.db, _ctx.deal_id)
            # Fall back to deal.sponsor if extraction produced nothing
            if not sponsor_data:
                sponsors = deal.sponsor if isinstance(deal.sponsor, list) else (
                    [deal.sponsor] if deal.sponsor else []
                )
                if sponsors and isinstance(sponsors[0], dict):
                    sponsor_data = sponsors[0]
            # Merge flat sponsor keys into task_data (build_input expects top-level keys)
            task_data.update(sponsor_data)

        result = await _ctx.llm_client.execute(
            prompt_name, flat_dc, task_data,
            db=_ctx.db, deal_id=_ctx.deal_id,
        )

        # Persist section to S3 so render_om_pdf can load it even if the agent
        # doesn't pass sections correctly in the tool call.
        try:
            from app.config import settings
            from app.storage.s3 import _get_client

            s3_client = _get_client()
            s3_key = f"deals/{_ctx.deal_id}/om/sections/{section_name}.json"
            s3_client.put_object(
                Bucket=settings.S3_BUCKET_NAME,
                Key=s3_key,
                Body=json.dumps(result).encode(),
                ContentType="application/json",
            )
        except Exception:
            logger.warning("Failed to persist section %s to S3", section_name, exc_info=True)

        return ToolResult(data={
            "section_name": section_name,
            "content": result,
        })


class RenderOMPDFTool(PlumbTool):
    name = "render_om_pdf"
    description = "Render the complete OM as a PDF from generated sections."
    permission = ToolPermission.AUTO

    def get_input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "deal_id": {"type": "string"},
                "sections": {"type": "object", "description": "Generated OM sections (transaction_overview, investment_highlights, etc.)"},
            },
            "required": ["deal_id", "sections"],
        }

    async def execute(self, _ctx: ToolContext | None = None, deal_id: str = "", sections: dict | None = None, **kwargs) -> ToolResult:
        if not _ctx or not _ctx.db:
            return ToolResult(success=False, error="ToolContext with db required")

        from sqlalchemy import func, select

        from app.config import settings
        from app.models.deal import Deal
        from app.models.image import DealImage
        from app.models.om import OMVersion
        from app.storage.s3 import _get_client
        from app.tasks.om_generation import _build_om_context, _render_om_pages

        deal_uuid = uuid.UUID(deal_id) if deal_id else _ctx.deal_id
        if not deal_uuid:
            return ToolResult(success=False, error="deal_id required")

        db = _ctx.db

        result = await db.execute(select(Deal).where(Deal.id == deal_uuid))
        deal = result.scalar_one_or_none()
        if not deal:
            return ToolResult(success=False, error=f"Deal {deal_id} not found")

        fm = (deal.typed_extension or {}).get("financial_model", {})
        images_result = await db.execute(
            select(DealImage).where(DealImage.deal_id == deal_uuid).order_by(DealImage.sort_order)
        )
        images = list(images_result.scalars().all())

        # Transform agent section outputs into the format _build_om_context expects.
        # generate_section returns {"section_name": "X", "content": {"paragraphs": [...]}}
        # but _build_om_context expects {"transaction_overview": [...], ...} — unwrapped.
        raw_sections = sections or {}

        # Fallback: if agent didn't pass sections, load them from S3 where
        # generate_section persisted them.
        if not raw_sections:
            raw_sections = await _load_persisted_sections(deal_uuid)

        narratives = _unwrap_section_outputs(raw_sections)

        # Fix sponsor_bios key mapping: _unwrap_section_outputs may use default
        # "Sponsor" key but build_om_context looks up by actual sponsor name.
        # Remap to match the first sponsor's name if we only have the default key.
        if "sponsor_bios" in narratives:
            bios = narratives["sponsor_bios"]
            if "Sponsor" in bios and len(bios) == 1:
                sponsors = deal.sponsor if isinstance(deal.sponsor, list) else (
                    [deal.sponsor] if deal.sponsor else []
                )
                if sponsors and isinstance(sponsors[0], dict):
                    actual_name = sponsors[0].get("name", sponsors[0].get("sponsor_name", ""))
                    if actual_name and actual_name != "Sponsor":
                        narratives["sponsor_bios"][actual_name] = bios.pop("Sponsor")

        # Defensive fallback: if key narratives are still missing, generate them
        # synchronously via the LLM client (same path the Celery task uses).
        required_narratives = ["transaction_overview", "investment_highlights", "market_narrative", "sponsor_bios"]
        missing = [k for k in required_narratives if not narratives.get(k)]
        if missing:
            logger.warning("render_om_pdf: narratives missing after agent generation: %s — generating via fallback", missing)
            try:
                narratives = await asyncio.to_thread(
                    _generate_missing_narratives_sync, deal, fm, narratives, missing,
                )
                # Check if fallback actually produced content
                still_missing = [k for k in required_narratives if not narratives.get(k)]
                if still_missing:
                    logger.error("render_om_pdf: narratives STILL missing after fallback: %s", still_missing)
            except Exception:
                logger.error("Fallback narrative generation failed — OM will be missing narrative sections", exc_info=True)

        # Build and render OM (sync operations — run in thread)
        def _render():
            om_context_dict = _build_om_context(deal, fm, images, narratives)
            return _render_om_pages(om_context_dict)

        pdf_bytes, page_count, html_pages = await asyncio.to_thread(_render)

        # Upload to S3
        s3_client = _get_client()
        max_version_result = await db.execute(
            select(func.max(OMVersion.version_number)).where(OMVersion.deal_id == deal_uuid)
        )
        max_version = max_version_result.scalar() or 0
        version_number = max_version + 1

        pdf_key = f"deals/{deal_uuid}/om/v{version_number}/om.pdf"
        html_key = f"deals/{deal_uuid}/om/v{version_number}/pages.json"

        def _upload():
            s3_client.put_object(
                Bucket=settings.S3_BUCKET_NAME, Key=pdf_key,
                Body=pdf_bytes, ContentType="application/pdf",
            )
            s3_client.put_object(
                Bucket=settings.S3_BUCKET_NAME, Key=html_key,
                Body=json.dumps(html_pages).encode(), ContentType="application/json",
            )

        await asyncio.to_thread(_upload)

        # Mark previous versions as superseded
        from sqlalchemy import update
        await db.execute(
            update(OMVersion)
            .where(OMVersion.deal_id == deal_uuid, OMVersion.status == "ready")
            .values(status="superseded")
        )

        om_version = OMVersion(
            deal_id=deal_uuid,
            version_number=version_number,
            s3_key=pdf_key,
            html_s3_key=html_key,
            page_count=page_count,
            file_size=len(pdf_bytes),
            financial_model_snapshot=fm,
            narrative_snapshot=narratives,
            status="ready",
        )
        db.add(om_version)
        await db.flush()

        return ToolResult(data={
            "deal_id": str(deal_uuid),
            "version_number": version_number,
            "page_count": page_count,
            "file_size": len(pdf_bytes),
            "s3_key": pdf_key,
        })


class ReviewOMDraftTool(PlumbTool):
    name = "review_om_draft"
    description = "Self-review the OM draft for factual accuracy, narrative quality, and completeness."
    permission = ToolPermission.AUTO

    def get_input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "om_sections": {"type": "object", "description": "Generated OM sections"},
                "financial_model": {"type": "object", "description": "Financial model for fact-checking"},
            },
            "required": ["om_sections", "financial_model"],
        }

    async def execute(self, _ctx: ToolContext | None = None, om_sections: dict | None = None, financial_model: dict | None = None, **kwargs) -> ToolResult:
        from app.services.om_evaluator import evaluate_om

        deal_context = {}
        if _ctx and _ctx.db and _ctx.deal_id:
            from app.services.context_engine import build_l1_context
            deal_context = await build_l1_context(_ctx.db, _ctx.deal_id)

        evaluation = await evaluate_om(
            om_sections=om_sections or {},
            financial_model=financial_model or {},
            deal_context=deal_context,
        )

        return ToolResult(data=evaluation)
