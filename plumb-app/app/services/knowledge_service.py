"""Sprint 2: Knowledge Library — CRUD, search, context assembly."""

import uuid

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import KnowledgeEntry


async def create_entry(
    db: AsyncSession,
    entry_type: str,
    title: str,
    content: str,
    tags: list[str] | None = None,
    created_by: uuid.UUID | None = None,
) -> KnowledgeEntry:
    entry = KnowledgeEntry(
        entry_type=entry_type,
        title=title,
        content=content,
        tags=tags or [],
        created_by=created_by,
    )
    db.add(entry)
    await db.flush()
    await db.refresh(entry)
    return entry


async def list_entries(
    db: AsyncSession,
    entry_type: str | None = None,
    search: str | None = None,
) -> list[KnowledgeEntry]:
    query = select(KnowledgeEntry).order_by(KnowledgeEntry.updated_at.desc())
    if entry_type:
        query = query.where(KnowledgeEntry.entry_type == entry_type)
    if search:
        query = query.where(
            or_(
                KnowledgeEntry.title.ilike(f"%{search}%"),
                KnowledgeEntry.content.ilike(f"%{search}%"),
            )
        )
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_entry(db: AsyncSession, entry_id: uuid.UUID) -> KnowledgeEntry | None:
    result = await db.execute(select(KnowledgeEntry).where(KnowledgeEntry.id == entry_id))
    return result.scalar_one_or_none()


async def update_entry(db: AsyncSession, entry_id: uuid.UUID, **kwargs) -> KnowledgeEntry | None:
    entry = await get_entry(db, entry_id)
    if not entry:
        return None
    for k, v in kwargs.items():
        if hasattr(entry, k):
            setattr(entry, k, v)
    await db.flush()
    await db.refresh(entry)
    return entry


async def delete_entry(db: AsyncSession, entry_id: uuid.UUID) -> bool:
    entry = await get_entry(db, entry_id)
    if not entry:
        return False
    await db.delete(entry)
    await db.flush()
    return True


async def get_context_by_tags(db: AsyncSession, tags: list[str]) -> list[dict]:
    """Assemble context bundle for given tags. Uses JSON contains for tag matching."""
    result = await db.execute(
        select(KnowledgeEntry).order_by(KnowledgeEntry.updated_at.desc())
    )
    entries = result.scalars().all()

    matched = []
    for entry in entries:
        entry_tags = entry.tags or []
        if any(t in entry_tags for t in tags):
            matched.append({
                "id": str(entry.id),
                "entry_type": entry.entry_type,
                "title": entry.title,
                "content": entry.content,
                "tags": entry_tags,
            })
    return matched
