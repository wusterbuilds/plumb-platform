"""Sprint 3: Developer profiles — CRUD, deal linking, correction patterns."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.developer import Developer, DeveloperDeal
from app.models.extraction import ExtractedValue


async def create_developer(db: AsyncSession, name: str, **kwargs) -> Developer:
    dev = Developer(name=name, **kwargs)
    db.add(dev)
    await db.flush()
    await db.refresh(dev)
    return dev


async def list_developers(db: AsyncSession, search: str | None = None) -> list[Developer]:
    query = select(Developer).order_by(Developer.name)
    if search:
        query = query.where(Developer.name.ilike(f"%{search}%"))
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_developer(db: AsyncSession, developer_id: uuid.UUID) -> Developer | None:
    result = await db.execute(select(Developer).where(Developer.id == developer_id))
    return result.scalar_one_or_none()


async def update_developer(db: AsyncSession, developer_id: uuid.UUID, **kwargs) -> Developer | None:
    dev = await get_developer(db, developer_id)
    if not dev:
        return None
    for k, v in kwargs.items():
        if hasattr(dev, k):
            setattr(dev, k, v)
    await db.flush()
    await db.refresh(dev)
    return dev


async def link_deal(
    db: AsyncSession,
    developer_id: uuid.UUID,
    deal_id: uuid.UUID,
    role: str = "sponsor",
) -> DeveloperDeal:
    link = DeveloperDeal(developer_id=developer_id, deal_id=deal_id, role=role)
    db.add(link)

    # Update deal count
    dev = await get_developer(db, developer_id)
    if dev:
        count_result = await db.execute(
            select(func.count(DeveloperDeal.id)).where(DeveloperDeal.developer_id == developer_id)
        )
        dev.deal_count = (count_result.scalar() or 0) + 1

    await db.flush()
    await db.refresh(link)
    return link


async def get_developer_deals(db: AsyncSession, developer_id: uuid.UUID) -> list[DeveloperDeal]:
    result = await db.execute(
        select(DeveloperDeal).where(DeveloperDeal.developer_id == developer_id)
    )
    return list(result.scalars().all())


async def get_correction_patterns(db: AsyncSession, developer_id: uuid.UUID) -> list[dict]:
    """Get override patterns across all deals for this developer."""
    deal_links = await get_developer_deals(db, developer_id)
    deal_ids = [link.deal_id for link in deal_links]
    if not deal_ids:
        return []

    result = await db.execute(
        select(
            ExtractedValue.field_name,
            func.count(ExtractedValue.id).label("override_count"),
        )
        .where(
            ExtractedValue.deal_id.in_(deal_ids),
            ExtractedValue.override_value.isnot(None),
        )
        .group_by(ExtractedValue.field_name)
        .having(func.count(ExtractedValue.id) >= 2)
        .order_by(func.count(ExtractedValue.id).desc())
    )
    rows = result.all()
    return [
        {"field_name": r.field_name, "override_count": r.override_count}
        for r in rows
    ]
