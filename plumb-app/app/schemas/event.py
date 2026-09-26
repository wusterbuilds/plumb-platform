import uuid
from datetime import datetime

from pydantic import BaseModel

from app.schemas.enums import EventType


class EventResponse(BaseModel):
    id: uuid.UUID
    deal_id: uuid.UUID
    event_type: EventType
    actor_id: uuid.UUID | None
    payload: dict | None
    revision_number: int
    timestamp: datetime

    model_config = {"from_attributes": True}


class EventListResponse(BaseModel):
    events: list[EventResponse]
    total: int
