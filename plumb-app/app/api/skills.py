"""API routes for Sprint 2: Skills + Knowledge."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.services import knowledge_service, skill_service

router = APIRouter(tags=["skills"])

# ── Schemas ──


class SkillCreate(BaseModel):
    name: str
    description: str | None = None
    skill_type: str
    target_prompt: str


class SkillVersionCreate(BaseModel):
    instructions: str
    reference_examples: list | None = None
    validation_criteria: list | None = None


class SkillTestRequest(BaseModel):
    deal_id: str


class KnowledgeCreate(BaseModel):
    entry_type: str
    title: str
    content: str
    tags: list[str] | None = None


class KnowledgeUpdate(BaseModel):
    title: str | None = None
    content: str | None = None
    tags: list[str] | None = None


# ── Skills ──

skills_router = APIRouter(prefix="/skills", tags=["skills"])


@skills_router.get("")
async def list_skills(
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    skills = await skill_service.list_skills(db, status=status)
    return [
        {
            "id": str(s.id),
            "name": s.name,
            "description": s.description,
            "skill_type": s.skill_type,
            "target_prompt": s.target_prompt,
            "status": s.status,
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "updated_at": s.updated_at.isoformat() if s.updated_at else None,
        }
        for s in skills
    ]


@skills_router.post("")
async def create_skill(
    body: SkillCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    skill = await skill_service.create_skill(
        db, name=body.name, description=body.description,
        skill_type=body.skill_type, target_prompt=body.target_prompt,
        created_by=user.id,
    )
    return {"id": str(skill.id), "name": skill.name, "status": skill.status}


@skills_router.get("/{skill_id}")
async def get_skill(
    skill_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    skill = await skill_service.get_skill(db, skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    versions = await skill_service.get_skill_versions(db, skill_id)
    return {
        "id": str(skill.id),
        "name": skill.name,
        "description": skill.description,
        "skill_type": skill.skill_type,
        "target_prompt": skill.target_prompt,
        "status": skill.status,
        "versions": [
            {
                "id": str(v.id),
                "version_number": v.version_number,
                "is_active": v.is_active,
                "regression_passed": v.regression_passed,
                "overall_accuracy": v.regression_results.get("accuracy") if v.regression_results else None,
                "created_at": v.created_at.isoformat() if v.created_at else None,
                "published_at": v.published_at.isoformat() if v.published_at else None,
            }
            for v in versions
        ],
    }


@skills_router.post("/{skill_id}/versions")
async def create_version(
    skill_id: uuid.UUID,
    body: SkillVersionCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    version = await skill_service.create_skill_version(
        db, skill_id=skill_id, instructions=body.instructions,
        reference_examples=body.reference_examples,
        validation_criteria=body.validation_criteria,
        created_by=user.id,
    )
    return {
        "id": str(version.id),
        "version_number": version.version_number,
        "is_active": version.is_active,
    }


@skills_router.get("/{skill_id}/versions")
async def list_versions(
    skill_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    versions = await skill_service.get_skill_versions(db, skill_id)
    return [
        {
            "id": str(v.id),
            "version_number": v.version_number,
            "instructions": v.instructions,
            "reference_examples": v.reference_examples,
            "is_active": v.is_active,
            "regression_passed": v.regression_passed,
            "created_at": v.created_at.isoformat() if v.created_at else None,
        }
        for v in versions
    ]


@skills_router.post("/{skill_id}/versions/{version_id}/promote")
async def promote_version(
    skill_id: uuid.UUID,
    version_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    version = await skill_service.promote_skill_version(db, skill_id, version_id)
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")
    return {"id": str(version.id), "is_active": version.is_active}


@skills_router.post("/{skill_id}/test")
async def test_skill(
    skill_id: uuid.UUID,
    body: SkillTestRequest,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    results = await skill_service.get_test_results(db, skill_id)
    return [
        {
            "id": str(r.id),
            "overall_accuracy": r.overall_accuracy,
            "improvement_delta": r.improvement_delta,
            "tested_at": r.tested_at.isoformat() if r.tested_at else None,
        }
        for r in results
    ]


@skills_router.get("/{skill_id}/test-results")
async def get_test_results(
    skill_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    results = await skill_service.get_test_results(db, skill_id)
    return [
        {
            "id": str(r.id),
            "skill_version_id": str(r.skill_version_id),
            "deal_id": str(r.deal_id),
            "results": r.results,
            "overall_accuracy": r.overall_accuracy,
            "improvement_delta": r.improvement_delta,
            "tested_at": r.tested_at.isoformat() if r.tested_at else None,
        }
        for r in results
    ]


# ── Knowledge ──

knowledge_router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@knowledge_router.get("")
async def list_knowledge(
    entry_type: str | None = None,
    search: str | None = None,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    entries = await knowledge_service.list_entries(db, entry_type=entry_type, search=search)
    return [
        {
            "id": str(e.id),
            "entry_type": e.entry_type,
            "title": e.title,
            "content": e.content,
            "tags": e.tags,
            "created_at": e.created_at.isoformat() if e.created_at else None,
            "updated_at": e.updated_at.isoformat() if e.updated_at else None,
        }
        for e in entries
    ]


@knowledge_router.post("")
async def create_knowledge(
    body: KnowledgeCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    entry = await knowledge_service.create_entry(
        db, entry_type=body.entry_type, title=body.title,
        content=body.content, tags=body.tags, created_by=user.id,
    )
    return {"id": str(entry.id), "title": entry.title}


@knowledge_router.get("/context")
async def get_context(
    tags: str,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    return await knowledge_service.get_context_by_tags(db, tag_list)


@knowledge_router.get("/{entry_id}")
async def get_knowledge(
    entry_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    entry = await knowledge_service.get_entry(db, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    return {
        "id": str(entry.id),
        "entry_type": entry.entry_type,
        "title": entry.title,
        "content": entry.content,
        "tags": entry.tags,
        "created_at": entry.created_at.isoformat() if entry.created_at else None,
    }


@knowledge_router.put("/{entry_id}")
async def update_knowledge(
    entry_id: uuid.UUID,
    body: KnowledgeUpdate,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    updates = body.model_dump(exclude_none=True)
    entry = await knowledge_service.update_entry(db, entry_id, **updates)
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    return {"id": str(entry.id), "title": entry.title}


@knowledge_router.delete("/{entry_id}")
async def delete_knowledge(
    entry_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    success = await knowledge_service.delete_entry(db, entry_id)
    if not success:
        raise HTTPException(status_code=404, detail="Entry not found")
    return {"deleted": True}
