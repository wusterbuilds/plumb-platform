"""Sprint 5: Override pattern automation — detect patterns, generate few-shot examples."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.extraction import ExtractedValue


async def detect_override_patterns(db: AsyncSession) -> list[dict]:
    """Detect systematic override patterns across all deals."""
    result = await db.execute(
        select(
            ExtractedValue.field_name,
            func.count(ExtractedValue.id).label("override_count"),
            func.count(ExtractedValue.deal_id.distinct()).label("deal_count"),
        )
        .where(ExtractedValue.override_value.isnot(None))
        .group_by(ExtractedValue.field_name)
        .having(func.count(ExtractedValue.id) >= 3)
        .order_by(func.count(ExtractedValue.id).desc())
    )
    rows = result.all()

    patterns = []
    for r in rows:
        # Get example corrections
        examples_result = await db.execute(
            select(ExtractedValue)
            .where(
                ExtractedValue.field_name == r.field_name,
                ExtractedValue.override_value.isnot(None),
            )
            .order_by(ExtractedValue.created_at.desc())
            .limit(5)
        )
        examples = examples_result.scalars().all()

        few_shot = []
        for ex in examples:
            few_shot.append({
                "original_value": ex.value,
                "corrected_value": ex.override_value,
                "reason": ex.override_reason,
                "source_text": ex.source_text_snippet,
            })

        patterns.append({
            "field_name": r.field_name,
            "override_count": r.override_count,
            "deal_count": r.deal_count,
            "pattern": f"{r.field_name} corrected in {r.deal_count} deals ({r.override_count} times)",
            "few_shot_examples": few_shot,
        })

    return patterns


async def generate_few_shot_context(db: AsyncSession, field_name: str) -> str:
    """Generate few-shot example text for injection into extraction prompts."""
    result = await db.execute(
        select(ExtractedValue)
        .where(
            ExtractedValue.field_name == field_name,
            ExtractedValue.override_value.isnot(None),
        )
        .order_by(ExtractedValue.created_at.desc())
        .limit(3)
    )
    examples = result.scalars().all()

    if not examples:
        return ""

    lines = [f"\n## Correction examples for {field_name}:"]
    for i, ex in enumerate(examples, 1):
        lines.append(f"\nExample {i}:")
        lines.append(f"  Source text: {ex.source_text_snippet}")
        lines.append(f"  System extracted: {ex.value}")
        lines.append(f"  Human corrected to: {ex.override_value}")
        if ex.override_reason:
            lines.append(f"  Reason: {ex.override_reason}")

    return "\n".join(lines)
