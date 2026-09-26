"""Sprint 2: Skill CRUD, versioning, test execution, and prompt injection."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.skill import Skill, SkillVersion, SkillTestResult


async def create_skill(
    db: AsyncSession,
    name: str,
    skill_type: str,
    target_prompt: str,
    description: str | None = None,
    created_by: uuid.UUID | None = None,
) -> Skill:
    skill = Skill(
        name=name,
        description=description,
        skill_type=skill_type,
        target_prompt=target_prompt,
        status="draft",
        created_by=created_by,
    )
    db.add(skill)
    await db.flush()
    await db.refresh(skill)
    return skill


async def list_skills(db: AsyncSession, status: str | None = None) -> list[Skill]:
    query = select(Skill).order_by(Skill.updated_at.desc())
    if status:
        query = query.where(Skill.status == status)
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_skill(db: AsyncSession, skill_id: uuid.UUID) -> Skill | None:
    result = await db.execute(select(Skill).where(Skill.id == skill_id))
    return result.scalar_one_or_none()


async def update_skill(db: AsyncSession, skill_id: uuid.UUID, **kwargs) -> Skill | None:
    skill = await get_skill(db, skill_id)
    if not skill:
        return None
    for k, v in kwargs.items():
        if hasattr(skill, k):
            setattr(skill, k, v)
    await db.flush()
    await db.refresh(skill)
    return skill


async def create_skill_version(
    db: AsyncSession,
    skill_id: uuid.UUID,
    instructions: str,
    reference_examples: list | None = None,
    validation_criteria: list | None = None,
    created_by: uuid.UUID | None = None,
) -> SkillVersion:
    max_ver = await db.execute(
        select(func.max(SkillVersion.version_number))
        .where(SkillVersion.skill_id == skill_id)
    )
    current_max = max_ver.scalar() or 0

    version = SkillVersion(
        skill_id=skill_id,
        version_number=current_max + 1,
        instructions=instructions,
        reference_examples=reference_examples or [],
        validation_criteria=validation_criteria or [],
        created_by=created_by,
    )
    db.add(version)
    await db.flush()
    await db.refresh(version)
    return version


async def get_skill_versions(db: AsyncSession, skill_id: uuid.UUID) -> list[SkillVersion]:
    result = await db.execute(
        select(SkillVersion)
        .where(SkillVersion.skill_id == skill_id)
        .order_by(SkillVersion.version_number.desc())
    )
    return list(result.scalars().all())


async def promote_skill_version(
    db: AsyncSession,
    skill_id: uuid.UUID,
    version_id: uuid.UUID,
) -> SkillVersion | None:
    # Deactivate all other versions
    result = await db.execute(
        select(SkillVersion).where(
            SkillVersion.skill_id == skill_id,
            SkillVersion.is_active == True,  # noqa: E712
        )
    )
    for v in result.scalars().all():
        v.is_active = False

    # Activate the target version
    result = await db.execute(select(SkillVersion).where(SkillVersion.id == version_id))
    version = result.scalar_one_or_none()
    if not version:
        return None
    version.is_active = True
    version.published_at = datetime.now(timezone.utc)

    # Activate the parent skill
    skill = await get_skill(db, skill_id)
    if skill:
        skill.status = "active"

    await db.flush()
    await db.refresh(version)
    return version


async def get_active_skills_for_prompt(db: AsyncSession, prompt_name: str) -> list[dict]:
    """Get active skill instructions and examples for prompt injection."""
    result = await db.execute(
        select(Skill, SkillVersion)
        .join(SkillVersion, SkillVersion.skill_id == Skill.id)
        .where(
            Skill.target_prompt == prompt_name,
            Skill.status == "active",
            SkillVersion.is_active == True,  # noqa: E712
        )
    )
    rows = result.all()
    return [
        {
            "skill_name": skill.name,
            "instructions": version.instructions,
            "reference_examples": version.reference_examples or [],
        }
        for skill, version in rows
    ]


async def save_test_result(
    db: AsyncSession,
    skill_version_id: uuid.UUID,
    deal_id: uuid.UUID,
    results: dict,
    overall_accuracy: float,
    improvement_delta: float | None = None,
) -> SkillTestResult:
    test_result = SkillTestResult(
        skill_version_id=skill_version_id,
        deal_id=deal_id,
        results=results,
        overall_accuracy=overall_accuracy,
        improvement_delta=improvement_delta,
    )
    db.add(test_result)
    await db.flush()
    await db.refresh(test_result)
    return test_result


async def get_test_results(db: AsyncSession, skill_id: uuid.UUID) -> list[SkillTestResult]:
    result = await db.execute(
        select(SkillTestResult)
        .join(SkillVersion, SkillTestResult.skill_version_id == SkillVersion.id)
        .where(SkillVersion.skill_id == skill_id)
        .order_by(SkillTestResult.tested_at.desc())
    )
    return list(result.scalars().all())
