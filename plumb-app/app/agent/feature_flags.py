"""Sprint 4: Feature flag system — control agent vs. pipeline per deal."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import FeatureFlag


async def is_enabled(
    db: AsyncSession,
    flag_name: str,
    deal_id: uuid.UUID | None = None,
    deal_type: str | None = None,
) -> bool:
    result = await db.execute(
        select(FeatureFlag).where(FeatureFlag.flag_name == flag_name)
    )
    flag = result.scalar_one_or_none()
    if not flag:
        return False
    if not flag.enabled:
        return False

    has_id_restriction = bool(flag.enabled_deal_ids)
    has_type_restriction = bool(flag.enabled_deal_types)

    # If no restrictions at all, enabled globally
    if not has_id_restriction and not has_type_restriction:
        return True

    # Check deal-specific enablement (OR logic: either match suffices)
    if deal_id and has_id_restriction and str(deal_id) in flag.enabled_deal_ids:
        return True
    if deal_type and has_type_restriction and deal_type in flag.enabled_deal_types:
        return True

    # If only one restriction type exists and the caller didn't provide
    # the matching dimension, don't block — treat as globally enabled.
    # e.g., enabled_deal_ids has stale entries but deal_type wasn't passed,
    # or enabled_deal_types is set but no deal_id restriction exists.
    if has_id_restriction and not has_type_restriction:
        # ID whitelist is the only restriction; if deal not in list, deny
        return False
    if has_type_restriction and not has_id_restriction:
        # Type whitelist is the only restriction; if type didn't match, deny
        return False

    # Both restrictions exist but neither matched
    return False


async def set_flag(
    db: AsyncSession,
    flag_name: str,
    enabled: bool,
    enabled_deal_types: list[str] | None = None,
    enabled_deal_ids: list[str] | None = None,
) -> FeatureFlag:
    result = await db.execute(
        select(FeatureFlag).where(FeatureFlag.flag_name == flag_name)
    )
    flag = result.scalar_one_or_none()
    if flag:
        flag.enabled = enabled
        if enabled_deal_types is not None:
            flag.enabled_deal_types = enabled_deal_types
        if enabled_deal_ids is not None:
            flag.enabled_deal_ids = enabled_deal_ids
    else:
        flag = FeatureFlag(
            flag_name=flag_name,
            enabled=enabled,
            enabled_deal_types=enabled_deal_types or [],
            enabled_deal_ids=enabled_deal_ids or [],
        )
        db.add(flag)
    await db.flush()
    await db.refresh(flag)
    return flag


async def list_flags(db: AsyncSession) -> list[FeatureFlag]:
    result = await db.execute(select(FeatureFlag).order_by(FeatureFlag.flag_name))
    return list(result.scalars().all())
