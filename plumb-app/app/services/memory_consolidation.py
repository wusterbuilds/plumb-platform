"""Sprint 5: Memory consolidation (autoDream) — daily process to consolidate episodic memory."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.episode import Episode
from app.models.lender import LenderAppetite


async def run_consolidation(db: AsyncSession) -> dict:
    """Daily memory consolidation. Merges tentative → confirmed, flags stale data."""
    results = {
        "consolidated_at": datetime.now(timezone.utc).isoformat(),
        "episodes_merged": 0,
        "episodes_promoted": 0,
        "stale_appetite_flagged": 0,
        "contradictions_removed": 0,
    }

    # 1. Merge similar episodes (same event_type and overlapping tags)
    tentative_result = await db.execute(
        select(Episode)
        .where(Episode.confidence == "tentative")
        .order_by(Episode.created_at)
    )
    tentative_episodes = tentative_result.scalars().all()

    # Group by event_type
    by_type: dict[str, list[Episode]] = {}
    for ep in tentative_episodes:
        by_type.setdefault(ep.event_type, []).append(ep)

    for event_type, episodes in by_type.items():
        # Find episodes with overlapping lessons (simple word overlap heuristic)
        seen = set()
        for i, ep_a in enumerate(episodes):
            if ep_a.id in seen:
                continue
            words_a = set(ep_a.lesson.lower().split())
            for ep_b in episodes[i + 1:]:
                if ep_b.id in seen:
                    continue
                words_b = set(ep_b.lesson.lower().split())
                overlap = len(words_a & words_b) / max(len(words_a | words_b), 1)
                if overlap > 0.5:
                    # Merge: increment the first, remove the second
                    ep_a.occurrence_count += ep_b.occurrence_count
                    if ep_a.occurrence_count >= 3:
                        ep_a.confidence = "confirmed"
                        results["episodes_promoted"] += 1
                    # Merge tags
                    all_tags = set(ep_a.relevance_tags or []) | set(ep_b.relevance_tags or [])
                    ep_a.relevance_tags = list(all_tags)
                    await db.delete(ep_b)
                    seen.add(ep_b.id)
                    results["episodes_merged"] += 1

    # 2. Promote tentative episodes with 3+ occurrences
    promote_result = await db.execute(
        select(Episode).where(
            Episode.confidence == "tentative",
            Episode.occurrence_count >= 3,
        )
    )
    for ep in promote_result.scalars().all():
        ep.confidence = "confirmed"
        results["episodes_promoted"] += 1

    # 3. Flag stale lender appetite data
    now = datetime.now(timezone.utc)
    stale_result = await db.execute(
        select(LenderAppetite).where(
            LenderAppetite.expires_at < now,
            LenderAppetite.is_stale == False,  # noqa: E712
        )
    )
    for appetite in stale_result.scalars().all():
        appetite.is_stale = True
        results["stale_appetite_flagged"] += 1

    await db.flush()
    return results
