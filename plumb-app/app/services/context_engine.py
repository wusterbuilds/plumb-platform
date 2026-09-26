"""Sprint 3: Context engine — three-layer context assembly for agents/prompts.

L1: Deal summary (always present, ~200 tokens)
L2: Working context (extraction results, flags, corrections, financial model)
L3: Knowledge (developer profile, lender targets, episodic memories, skills)
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.deal import Deal
from app.models.developer import Developer, DeveloperDeal
from app.models.document import Document
from app.models.episode import Episode
from app.models.extraction import ExtractedValue
from app.services import episode_service, knowledge_service, skill_service


async def build_l1_context(db: AsyncSession, deal_id: uuid.UUID) -> dict:
    """Deal summary — always present in every prompt/agent call."""
    result = await db.execute(select(Deal).where(Deal.id == deal_id))
    deal = result.scalar_one_or_none()
    if not deal:
        return {}

    return {
        "deal_id": str(deal.id),
        "deal_type": deal.deal_type,
        "deal_subtype": deal.deal_subtype,
        "capital_ask": deal.capital_ask,
        "status": deal.status,
        "property_name": deal.property_name,
        "property_address": deal.property_address,
        "property_type": deal.property_type,
        "sponsor": deal.sponsor,
        "revision_number": deal.revision_number,
    }


async def build_l2_context(db: AsyncSession, deal_id: uuid.UUID) -> dict:
    """Working context — extraction results, flags, financial model, documents."""
    # Get documents for this deal
    doc_result = await db.execute(
        select(Document)
        .where(Document.deal_id == deal_id)
        .order_by(Document.uploaded_at)
    )
    documents = doc_result.scalars().all()
    doc_list = [
        {
            "id": str(d.id),
            "filename": d.filename,
            "document_type": d.document_type,
            "mime_type": d.mime_type,
            "page_count": d.page_count,
            "status": d.status,
        }
        for d in documents
    ]

    # Get extraction summary
    result = await db.execute(
        select(ExtractedValue)
        .where(ExtractedValue.deal_id == deal_id)
        .order_by(ExtractedValue.field_name)
    )
    values = result.scalars().all()

    fields = {}
    flags = {"red": [], "yellow": [], "green": []}
    for v in values:
        effective_value = v.override_value if v.override_value else v.value
        fields[v.field_name] = effective_value
        if v.flag:
            flags[v.flag].append(v.field_name)

    # Get deal for financial model and market context
    deal_result = await db.execute(select(Deal).where(Deal.id == deal_id))
    deal = deal_result.scalar_one_or_none()

    typed_extension = deal.typed_extension if deal else None
    financial_model = (typed_extension or {}).get("financial_model") if typed_extension else None

    return {
        "documents": doc_list,
        "extracted_fields": fields,
        "flag_summary": {
            "red": len(flags["red"]),
            "yellow": len(flags["yellow"]),
            "green": len(flags["green"]),
        },
        "red_fields": flags["red"],
        "yellow_fields": flags["yellow"],
        "typed_extension": typed_extension,
        "financial_model": financial_model,
        "market_context": deal.market_context if deal else None,
        "regulatory": deal.regulatory if deal else None,
    }


async def build_l3_context(
    db: AsyncSession,
    deal_id: uuid.UUID,
    tags: list[str] | None = None,
) -> dict:
    """Knowledge layer — developer, episodes, skills, knowledge entries."""
    # Developer profile
    dev_link_result = await db.execute(
        select(DeveloperDeal).where(DeveloperDeal.deal_id == deal_id)
    )
    dev_link = dev_link_result.scalar_one_or_none()
    developer_profile = None
    correction_patterns = []
    if dev_link:
        dev_result = await db.execute(
            select(Developer).where(Developer.id == dev_link.developer_id)
        )
        dev = dev_result.scalar_one_or_none()
        if dev:
            developer_profile = {
                "name": dev.name,
                "entity_structure": dev.entity_structure,
                "track_record": dev.track_record,
                "known_patterns": dev.known_patterns,
                "deal_count": dev.deal_count,
            }
            from app.services.developer_service import get_correction_patterns
            correction_patterns = await get_correction_patterns(db, dev.id)

    # Episodic memories
    episodes = []
    if tags:
        eps = await episode_service.query_episodes_by_tags(db, tags)
        episodes = [
            {"lesson": ep.lesson, "confidence": ep.confidence, "event_type": ep.event_type}
            for ep in eps[:10]
        ]

    # Knowledge entries
    knowledge = []
    if tags:
        knowledge = await knowledge_service.get_context_by_tags(db, tags)

    # Active skills — fetch all active skills (agents can use any)
    skills = await skill_service.get_active_skills_for_prompt(db, "all")

    return {
        "developer_profile": developer_profile,
        "correction_patterns": correction_patterns,
        "episodes": episodes,
        "knowledge": knowledge[:10],
        "skills": skills,
    }


async def build_deal_context(
    db: AsyncSession,
    deal_id: uuid.UUID,
    include_l2: bool = True,
    include_l3: bool = True,
    tags: list[str] | None = None,
) -> dict:
    """Assemble full deal context for agents/prompts."""
    context = {"l1": await build_l1_context(db, deal_id)}

    if include_l2:
        context["l2"] = await build_l2_context(db, deal_id)

    if include_l3:
        context["l3"] = await build_l3_context(db, deal_id, tags=tags)

    return context
