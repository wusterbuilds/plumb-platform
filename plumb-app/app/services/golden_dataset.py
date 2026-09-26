"""Sprint 4: Golden dataset — passive collection of confirmed extractions + approved OMs."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import GoldenExample
from app.models.extraction import ExtractedValue


async def collect_from_extraction_review(
    db: AsyncSession,
    deal_id: uuid.UUID,
) -> int:
    """After extraction review is completed, collect golden examples from confirmed fields."""
    result = await db.execute(
        select(ExtractedValue).where(ExtractedValue.deal_id == deal_id)
    )
    values = result.scalars().all()

    count = 0
    for v in values:
        confirmed_value = v.override_value if v.override_value else v.value
        example = GoldenExample(
            deal_id=deal_id,
            example_type="extraction",
            prompt_name=None,
            prompt_version=v.prompt_version,
            field_name=v.field_name,
            input_context={
                "source_page": v.source_page,
                "source_text_snippet": v.source_text_snippet,
            },
            output={"extracted_value": v.value},
            confirmed_value={"value": confirmed_value, "was_overridden": v.override_value is not None},
        )
        db.add(example)
        count += 1

    await db.flush()
    return count


async def collect_from_om_approval(
    db: AsyncSession,
    deal_id: uuid.UUID,
    om_version_id: uuid.UUID,
    narrative_snapshot: dict | None = None,
) -> GoldenExample:
    """After OM is approved without revision, collect as golden reference."""
    example = GoldenExample(
        deal_id=deal_id,
        example_type="om_approved",
        input_context={"om_version_id": str(om_version_id)},
        output=narrative_snapshot,
        confirmed_value={"approved": True},
    )
    db.add(example)
    await db.flush()
    await db.refresh(example)
    return example


async def list_golden_examples(
    db: AsyncSession,
    example_type: str | None = None,
    field_name: str | None = None,
    deal_id: uuid.UUID | None = None,
) -> list[GoldenExample]:
    query = select(GoldenExample).order_by(GoldenExample.created_at.desc())
    if example_type:
        query = query.where(GoldenExample.example_type == example_type)
    if field_name:
        query = query.where(GoldenExample.field_name == field_name)
    if deal_id:
        query = query.where(GoldenExample.deal_id == deal_id)
    result = await db.execute(query)
    return list(result.scalars().all())
