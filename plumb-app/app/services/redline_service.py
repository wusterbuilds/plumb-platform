"""Expert-feedback redline capture and projection.

Three responsibilities:

1. Persist a `DraftRedline` row when an expert corrects a section of an OM
   (or risk report) draft.

2. Project that redline into an `Episode` so the existing prompt-injection
   path (harness + sync LLM client) automatically surfaces the lesson on the
   next agent / narrative run for similar deals.

3. Retrieval helpers used at LLM call time to fetch lessons relevant to the
   current deal's archetype.

The design rationale lives in `feedback_capture_design_2026-04-11.md`.
"""

from __future__ import annotations

import re
import uuid
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.models.deal import Deal
from app.models.draft_redline import DraftRedline
from app.models.episode import Episode
from app.models.om import OMVersion


# ---------------------------------------------------------------------------
# Archetype computation
# ---------------------------------------------------------------------------

def _normalize(token: str | None) -> str:
    if not token:
        return "generic"
    return re.sub(r"[^a-z0-9]+", "_", token.lower()).strip("_") or "generic"


def _geo_tier_from_deal(deal: Deal) -> str:
    """Best-effort geography token.

    Prefer market_context.borough (extraction- or research-validated), fall
    back to a coarse parse of property_address. Only NYC boroughs are coded
    in Phase 1; everything else returns "generic" rather than fabricating a
    geo tier that retrieval would key on.
    """
    mc = deal.market_context or {}
    borough = (mc.get("borough") or "").strip().lower() if isinstance(mc, dict) else ""
    if borough:
        # Collapse all NYC boroughs to a single "nyc" tier so cross-borough
        # lessons are reusable. Geography can be sub-tiered later when we
        # have enough redline volume to justify it.
        if borough in {"manhattan", "brooklyn", "queens", "bronx", "staten island"}:
            return "nyc"
        return _normalize(borough)

    addr = (deal.property_address or "").lower()
    if any(b in addr for b in ("manhattan", "brooklyn", "queens", "bronx", "staten island", "new york")):
        return "nyc"
    return "generic"


def compute_archetype(deal: Deal) -> str:
    """Return a stable, retrieval-keyed archetype signature for a deal.

    Format: `{deal_type}__{deal_subtype}__{geo}`. Lower-cased, snake-cased.
    """
    return "__".join((
        _normalize(deal.deal_type),
        _normalize(deal.deal_subtype),
        _geo_tier_from_deal(deal),
    ))


# ---------------------------------------------------------------------------
# Redline → Episode projection
# ---------------------------------------------------------------------------

_MAX_LESSON_SNIPPET = 220


def _shorten(text: str, limit: int = _MAX_LESSON_SNIPPET) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def build_lesson(redline: DraftRedline, archetype: str) -> str:
    """Compose the one-sentence lesson injected into the system prompt.

    Lessons must be action-oriented, archetype-qualified, and short enough
    that 10 of them fit comfortably in a 4k-token context budget.
    """
    section = redline.section_key.replace("_", " ")
    if redline.rationale:
        # Use the expert's own words when available — that's the highest-
        # signal training data the system gets.
        return (
            f"On {archetype} deals, in the {section} section: "
            f"{_shorten(redline.rationale)}"
        )
    return (
        f"On {archetype} deals, in the {section} section, "
        f"prefer \"{_shorten(redline.edited_text, 120)}\" over "
        f"\"{_shorten(redline.original_text, 120)}\"."
    )


def _build_episode_tags(redline: DraftRedline, archetype: str, deal_type: str | None) -> list[str]:
    tags: list[str] = ["correction", archetype, redline.section_key]
    if redline.correction_category:
        tags.append(redline.correction_category)
    if redline.severity:
        tags.append(f"severity:{redline.severity}")
    # Coarse deal-type tag so the existing orchestrator query
    # (`tags=["construction_loan"]`) also surfaces this episode.
    if deal_type:
        tags.append(deal_type)
    return tags


# ---------------------------------------------------------------------------
# Sync helpers (Celery / OM generation path)
# ---------------------------------------------------------------------------

def store_redline_sync(
    db: Session,
    *,
    deal: Deal,
    artifact_type: str,
    artifact_ref_id: uuid.UUID,
    section_key: str,
    section_index: int | None,
    original_text: str,
    edited_text: str,
    rationale: str | None,
    correction_category: str | None,
    severity: str,
    reviewer_id: uuid.UUID | None,
    reviewer_role: str | None = "cre_expert",
) -> tuple[DraftRedline, Episode]:
    """Persist a redline + project an Episode in the same transaction."""
    archetype = compute_archetype(deal)
    redline = DraftRedline(
        deal_id=deal.id,
        artifact_type=artifact_type,
        artifact_ref_id=artifact_ref_id,
        section_key=section_key,
        section_index=section_index,
        original_text=original_text,
        edited_text=edited_text,
        rationale=rationale,
        correction_category=correction_category,
        severity=severity,
        archetype_signature=archetype,
        reviewer_id=reviewer_id,
        reviewer_role=reviewer_role,
    )
    db.add(redline)
    db.flush()

    lesson = build_lesson(redline, archetype)
    tags = _build_episode_tags(redline, archetype, deal.deal_type)
    episode = Episode(
        deal_id=deal.id,
        event_type="correction",
        lesson=lesson,
        relevance_tags=tags,
        confidence="tentative",
        occurrence_count=1,
    )
    db.add(episode)
    db.flush()

    redline.episode_id = episode.id

    # Bump the parent OMVersion.redline_count cache so the UI can show
    # "3 corrections saved" without a separate count query.
    if artifact_type == "om_section":
        version = db.query(OMVersion).filter(OMVersion.id == artifact_ref_id).one_or_none()
        if version:
            version.redline_count = (version.redline_count or 0) + 1

    db.flush()
    return redline, episode


def fetch_relevant_lessons_sync(
    db: Session,
    *,
    deal: Deal,
    section_key: str | None = None,
    limit: int = 10,
) -> list[str]:
    """Return up to `limit` correction lessons relevant to the deal.

    The matching is exact-string on tags. Two layers of filtering:

    - Archetype must match (so a value-add correction doesn't bleed into a
      construction loan).
    - If `section_key` is provided, prefer lessons tagged with that section
      and only fall back to other sections if there's room left in `limit`.

    Returned strings are pre-formatted for direct insertion into a system
    prompt. The caller does not need to re-format.
    """
    archetype = compute_archetype(deal)

    query = (
        select(Episode)
        .where(Episode.event_type == "correction")
        .order_by(Episode.occurrence_count.desc(), Episode.created_at.desc())
    )
    candidates = db.execute(query).scalars().all()

    primary: list[str] = []
    secondary: list[str] = []
    for ep in candidates:
        tags = ep.relevance_tags or []
        if archetype not in tags:
            continue
        if section_key and section_key in tags:
            primary.append(ep.lesson)
        else:
            secondary.append(ep.lesson)
        if len(primary) >= limit:
            break

    out = primary + secondary
    return out[:limit]


def list_redlines_for_version_sync(
    db: Session, *, version_id: uuid.UUID
) -> list[DraftRedline]:
    return (
        db.query(DraftRedline)
        .filter(DraftRedline.artifact_ref_id == version_id)
        .order_by(DraftRedline.created_at.asc())
        .all()
    )


# ---------------------------------------------------------------------------
# Async helpers (FastAPI request handlers)
# ---------------------------------------------------------------------------

async def store_redline_async(
    db: AsyncSession,
    *,
    deal: Deal,
    artifact_type: str,
    artifact_ref_id: uuid.UUID,
    section_key: str,
    section_index: int | None,
    original_text: str,
    edited_text: str,
    rationale: str | None,
    correction_category: str | None,
    severity: str,
    reviewer_id: uuid.UUID | None,
    reviewer_role: str | None = "cre_expert",
) -> tuple[DraftRedline, Episode]:
    archetype = compute_archetype(deal)
    redline = DraftRedline(
        deal_id=deal.id,
        artifact_type=artifact_type,
        artifact_ref_id=artifact_ref_id,
        section_key=section_key,
        section_index=section_index,
        original_text=original_text,
        edited_text=edited_text,
        rationale=rationale,
        correction_category=correction_category,
        severity=severity,
        archetype_signature=archetype,
        reviewer_id=reviewer_id,
        reviewer_role=reviewer_role,
    )
    db.add(redline)
    await db.flush()

    lesson = build_lesson(redline, archetype)
    tags = _build_episode_tags(redline, archetype, deal.deal_type)
    episode = Episode(
        deal_id=deal.id,
        event_type="correction",
        lesson=lesson,
        relevance_tags=tags,
        confidence="tentative",
        occurrence_count=1,
    )
    db.add(episode)
    await db.flush()

    redline.episode_id = episode.id

    if artifact_type == "om_section":
        version_result = await db.execute(
            select(OMVersion).where(OMVersion.id == artifact_ref_id)
        )
        version = version_result.scalar_one_or_none()
        if version:
            version.redline_count = (version.redline_count or 0) + 1

    await db.flush()
    return redline, episode


async def list_redlines_for_deal_async(
    db: AsyncSession, *, deal_id: uuid.UUID, version_id: uuid.UUID | None = None
) -> list[DraftRedline]:
    query = (
        select(DraftRedline)
        .where(DraftRedline.deal_id == deal_id)
        .order_by(DraftRedline.created_at.desc())
    )
    if version_id is not None:
        query = query.where(DraftRedline.artifact_ref_id == version_id)
    result = await db.execute(query)
    return list(result.scalars().all())


async def fetch_relevant_lessons_async(
    db: AsyncSession,
    *,
    deal: Deal,
    limit: int = 10,
) -> list[str]:
    archetype = compute_archetype(deal)
    result = await db.execute(
        select(Episode)
        .where(Episode.event_type == "correction")
        .order_by(Episode.occurrence_count.desc(), Episode.created_at.desc())
    )
    out: list[str] = []
    for ep in result.scalars().all():
        tags = ep.relevance_tags or []
        if archetype in tags:
            out.append(ep.lesson)
            if len(out) >= limit:
                break
    return out


def archetype_tags_for_deal(deal: Deal) -> list[str]:
    """Public helper used by the orchestrator to extend its retrieval tags."""
    archetype = compute_archetype(deal)
    base: list[str] = [archetype, "correction"]
    if deal.deal_type:
        base.append(deal.deal_type)
    return base
