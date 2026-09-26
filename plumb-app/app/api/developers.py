"""API routes for Sprint 3: Developer profiles."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.services import developer_service

router = APIRouter(prefix="/developers", tags=["developers"])


class DeveloperCreate(BaseModel):
    name: str
    entity_structure: dict | None = None
    track_record: str | None = None
    notes: str | None = None


class DeveloperUpdate(BaseModel):
    name: str | None = None
    entity_structure: dict | None = None
    track_record: str | None = None
    known_patterns: list | None = None
    notes: str | None = None


class LinkDealRequest(BaseModel):
    deal_id: str
    role: str = "sponsor"


@router.get("")
async def list_developers(
    search: str | None = None,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    devs = await developer_service.list_developers(db, search=search)
    return [
        {
            "id": str(d.id),
            "name": d.name,
            "deal_count": d.deal_count,
            "notes": d.notes,
            "created_at": d.created_at.isoformat() if d.created_at else None,
        }
        for d in devs
    ]


@router.post("")
async def create_developer(
    body: DeveloperCreate,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    dev = await developer_service.create_developer(db, **body.model_dump())
    return {"id": str(dev.id), "name": dev.name}


@router.get("/{developer_id}")
async def get_developer(
    developer_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    dev = await developer_service.get_developer(db, developer_id)
    if not dev:
        raise HTTPException(status_code=404, detail="Developer not found")
    deals = await developer_service.get_developer_deals(db, developer_id)
    patterns = await developer_service.get_correction_patterns(db, developer_id)
    return {
        "id": str(dev.id),
        "name": dev.name,
        "entity_structure": dev.entity_structure,
        "track_record": dev.track_record,
        "known_patterns": dev.known_patterns,
        "notes": dev.notes,
        "deal_count": dev.deal_count,
        "deals": [
            {"deal_id": str(d.deal_id), "role": d.role}
            for d in deals
        ],
        "correction_patterns": patterns,
    }


@router.put("/{developer_id}")
async def update_developer(
    developer_id: uuid.UUID,
    body: DeveloperUpdate,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    updates = body.model_dump(exclude_none=True)
    dev = await developer_service.update_developer(db, developer_id, **updates)
    if not dev:
        raise HTTPException(status_code=404, detail="Developer not found")
    return {"id": str(dev.id), "name": dev.name}


@router.post("/{developer_id}/deals")
async def link_deal(
    developer_id: uuid.UUID,
    body: LinkDealRequest,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    link = await developer_service.link_deal(
        db, developer_id=developer_id, deal_id=uuid.UUID(body.deal_id), role=body.role,
    )
    return {"developer_id": str(link.developer_id), "deal_id": str(link.deal_id)}
