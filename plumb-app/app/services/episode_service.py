"""Sprint 3: Episodic memory — CRUD, relevance-based retrieval."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.episode import Episode


async def create_episode(
    db: AsyncSession,
    event_type: str,
    lesson: str,
    deal_id: uuid.UUID | None = None,
    relevance_tags: list[str] | None = None,
    confidence: str = "tentative",
) -> Episode:
    episode = Episode(
        deal_id=deal_id,
        event_type=event_type,
        lesson=lesson,
        relevance_tags=relevance_tags or [],
        confidence=confidence,
    )
    db.add(episode)
    await db.flush()
    await db.refresh(episode)
    return episode


async def list_episodes(
    db: AsyncSession,
    event_type: str | None = None,
    deal_id: uuid.UUID | None = None,
) -> list[Episode]:
    query = select(Episode).order_by(Episode.updated_at.desc())
    if event_type:
        query = query.where(Episode.event_type == event_type)
    if deal_id:
        query = query.where(Episode.deal_id == deal_id)
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_episode(db: AsyncSession, episode_id: uuid.UUID) -> Episode | None:
    result = await db.execute(select(Episode).where(Episode.id == episode_id))
    return result.scalar_one_or_none()


async def query_episodes_by_tags(db: AsyncSession, tags: list[str]) -> list[Episode]:
    """Retrieve episodes matching any of the given tags."""
    result = await db.execute(
        select(Episode).order_by(Episode.updated_at.desc())
    )
    episodes = result.scalars().all()

    matched = []
    for ep in episodes:
        ep_tags = ep.relevance_tags or []
        if any(t in ep_tags for t in tags):
            matched.append(ep)
    return matched


async def increment_occurrence(db: AsyncSession, episode_id: uuid.UUID) -> Episode | None:
    ep = await get_episode(db, episode_id)
    if not ep:
        return None
    ep.occurrence_count += 1
    if ep.occurrence_count >= 3:
        ep.confidence = "confirmed"
    await db.flush()
    await db.refresh(ep)
    return ep


async def update_episode(db: AsyncSession, episode_id: uuid.UUID, **kwargs) -> Episode | None:
    ep = await get_episode(db, episode_id)
    if not ep:
        return None
    for k, v in kwargs.items():
        if hasattr(ep, k):
            setattr(ep, k, v)
    await db.flush()
    await db.refresh(ep)
    return ep
