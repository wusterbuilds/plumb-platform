import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.events import log_event
from app.models.deal import Deal
from app.schemas.enums import DealStatus, EventType
from app.state_machine.states import get_transition_rule


class TransitionError(HTTPException):
    def __init__(self, detail: str):
        super().__init__(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail)


async def transition(
    db: AsyncSession,
    deal_id: uuid.UUID,
    target_status: DealStatus,
    actor_id: uuid.UUID | None = None,
    reason: str | None = None,
    dead_reason: str | None = None,
) -> Deal:
    result = await db.execute(
        select(Deal).where(Deal.id == deal_id).with_for_update()
    )
    deal = result.scalar_one_or_none()
    if deal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deal not found")

    current_status = DealStatus(deal.status)

    # No-op if already in target state
    if current_status == target_status:
        return deal

    # Look up transition rule
    rule_result = get_transition_rule(current_status, target_status)
    if rule_result is None:
        raise TransitionError(
            f"Transition from {current_status.value} to {target_status.value} is not allowed"
        )

    rule, transition_type = rule_result

    # Enforce human gate
    if rule["gate"] == "human" and actor_id is None:
        raise TransitionError(
            f"Transition to {target_status.value} requires a human actor (gate=human)"
        )

    # Backward transitions require a reason
    if transition_type == "backward" and not reason:
        raise TransitionError("Backward transitions require a reason")

    # DEAD requires a dead_reason
    if transition_type == "kill" and not dead_reason:
        raise TransitionError("Killing a deal requires a dead_reason")

    # ON_HOLD: store current state so we can resume
    if transition_type == "hold":
        deal.previous_status = deal.status

    # Resume from ON_HOLD: validate target matches previous_status
    if transition_type == "resume":
        if deal.previous_status and target_status.value != deal.previous_status:
            raise TransitionError(
                f"Can only resume to previous state ({deal.previous_status}), "
                f"not {target_status.value}"
            )
        deal.previous_status = None

    # Apply transition
    old_status = deal.status
    deal.status = target_status.value

    # Increment revision on backward transitions
    if transition_type == "backward":
        deal.revision_number += 1

    deal.version += 1

    # Determine event type
    event_type_map = {
        "forward": EventType.STATE_TRANSITION,
        "backward": EventType.BACKWARD_TRANSITION,
        "error": EventType.STATE_TRANSITION,
        "hold": EventType.DEAL_ON_HOLD,
        "resume": EventType.DEAL_RESUMED,
        "kill": EventType.DEAL_KILLED,
        "retry": EventType.STATE_TRANSITION,
    }
    event_type = event_type_map[transition_type]

    # Build event payload
    payload = {
        "from_status": old_status,
        "to_status": target_status.value,
        "transition_type": transition_type,
    }
    if reason:
        payload["reason"] = reason
    if dead_reason:
        payload["dead_reason"] = dead_reason

    await log_event(
        db=db,
        deal_id=deal_id,
        event_type=event_type.value,
        actor_id=actor_id,
        payload=payload,
        revision_number=deal.revision_number,
    )

    await db.flush()
    await db.refresh(deal)
    return deal
