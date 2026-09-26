import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.models.event import Event


async def log_event(
    db: AsyncSession,
    deal_id: uuid.UUID,
    event_type: str,
    actor_id: uuid.UUID | None = None,
    payload: dict | None = None,
    revision_number: int = 1,
) -> Event:
    event = Event(
        deal_id=deal_id,
        event_type=event_type,
        actor_id=actor_id,
        payload=payload,
        revision_number=revision_number,
    )
    db.add(event)
    await db.flush()
    await db.refresh(event)
    return event


def log_event_sync(
    db: Session,
    deal_id: uuid.UUID,
    event_type: str,
    actor_id: uuid.UUID | None = None,
    payload: dict | None = None,
    revision_number: int = 1,
) -> Event:
    """Synchronous version for Celery tasks."""
    event = Event(
        deal_id=deal_id,
        event_type=event_type,
        actor_id=actor_id,
        payload=payload,
        revision_number=revision_number,
    )
    db.add(event)
    db.flush()
    db.refresh(event)
    return event
