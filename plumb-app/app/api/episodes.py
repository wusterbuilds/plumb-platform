"""API routes for Sprint 3: Episodic memory."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.services import episode_service

router = APIRouter(prefix="/episodes", tags=["episodes"])


class EpisodeCreate(BaseModel):
    event_type: str
    lesson: str
    deal_id: str | None = None
    relevance_tags: list[str] | None = None


@router.get("")
async def list_episodes(
    event_type: str | None = None,
    deal_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    episodes = await episode_service.list_episodes(db, event_type=event_type, deal_id=deal_id)
    return [
        {
            "id": str(e.id),
            "deal_id": str(e.deal_id) if e.deal_id else None,
            "event_type": e.event_type,
            "lesson": e.lesson,
            "relevance_tags": e.relevance_tags,
            "confidence": e.confidence,
            "occurrence_count": e.occurrence_count,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in episodes
    ]


@router.post("")
async def create_episode(
    body: EpisodeCreate,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    ep = await episode_service.create_episode(
        db,
        event_type=body.event_type,
        lesson=body.lesson,
        deal_id=uuid.UUID(body.deal_id) if body.deal_id else None,
        relevance_tags=body.relevance_tags,
    )
    return {"id": str(ep.id), "event_type": ep.event_type}


@router.get("/search")
async def search_episodes(
    tags: str,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    episodes = await episode_service.query_episodes_by_tags(db, tag_list)
    return [
        {
            "id": str(e.id),
            "event_type": e.event_type,
            "lesson": e.lesson,
            "relevance_tags": e.relevance_tags,
            "confidence": e.confidence,
            "occurrence_count": e.occurrence_count,
        }
        for e in episodes
    ]
