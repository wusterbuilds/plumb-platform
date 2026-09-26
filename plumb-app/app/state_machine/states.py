from app.schemas.enums import DealStatus

# Gate types:
#   "auto"  — system can trigger without human action
#   "human" — requires an authenticated human actor

FORWARD_TRANSITIONS: dict[tuple[DealStatus, DealStatus], dict] = {
    (DealStatus.DOCS_RECEIVED, DealStatus.CLASSIFYING): {"gate": "auto"},
    (DealStatus.CLASSIFYING, DealStatus.EXTRACTING): {"gate": "auto"},
    (DealStatus.EXTRACTING, DealStatus.EXTRACTION_REVIEW): {"gate": "auto"},
    (DealStatus.EXTRACTION_REVIEW, DealStatus.MARKET_ENRICHMENT): {"gate": "human"},
    (DealStatus.MARKET_ENRICHMENT, DealStatus.MODEL_BUILDING): {"gate": "auto"},
    (DealStatus.MARKET_ENRICHMENT, DealStatus.OM_DRAFTING): {"gate": "auto"},
    (DealStatus.MODEL_BUILDING, DealStatus.OM_DRAFTING): {"gate": "auto"},
    (DealStatus.OM_DRAFTING, DealStatus.OM_REVIEW): {"gate": "auto"},
    (DealStatus.OM_REVIEW, DealStatus.LENDER_OUTREACH): {"gate": "human"},
    (DealStatus.LENDER_OUTREACH, DealStatus.TRACKING): {"gate": "auto"},
    (DealStatus.TRACKING, DealStatus.TERM_SHEET_RECEIVED): {"gate": "human"},
    (DealStatus.TERM_SHEET_RECEIVED, DealStatus.CLOSED): {"gate": "human"},
}

BACKWARD_TRANSITIONS: dict[tuple[DealStatus, DealStatus], dict] = {
    (DealStatus.MODEL_BUILDING, DealStatus.EXTRACTION_REVIEW): {"gate": "auto"},
    (DealStatus.OM_REVIEW, DealStatus.EXTRACTION_REVIEW): {"gate": "human"},
    (DealStatus.OM_REVIEW, DealStatus.MODEL_BUILDING): {"gate": "human"},
    (DealStatus.TRACKING, DealStatus.OM_DRAFTING): {"gate": "human"},
    (DealStatus.TRACKING, DealStatus.EXTRACTION_REVIEW): {"gate": "human"},
}

ERROR_TRANSITIONS: dict[tuple[DealStatus, DealStatus], dict] = {
    (DealStatus.EXTRACTING, DealStatus.EXTRACTION_FAILED): {"gate": "auto"},
    (DealStatus.MODEL_BUILDING, DealStatus.MODEL_ERROR): {"gate": "auto"},
}

# States from which ON_HOLD can be entered
ACTIVE_STATES: set[DealStatus] = {
    DealStatus.DOCS_RECEIVED,
    DealStatus.CLASSIFYING,
    DealStatus.EXTRACTING,
    DealStatus.EXTRACTION_REVIEW,
    DealStatus.MODEL_BUILDING,
    DealStatus.MARKET_ENRICHMENT,
    DealStatus.OM_DRAFTING,
    DealStatus.OM_REVIEW,
    DealStatus.LENDER_OUTREACH,
    DealStatus.TRACKING,
    DealStatus.TERM_SHEET_RECEIVED,
}

# Terminal states — no transitions out
TERMINAL_STATES: set[DealStatus] = {DealStatus.CLOSED, DealStatus.DEAD}


def get_transition_rule(
    from_status: DealStatus, to_status: DealStatus
) -> tuple[dict, str] | None:
    """Returns (rule, transition_type) or None if transition is not defined."""

    # Check forward
    key = (from_status, to_status)
    if key in FORWARD_TRANSITIONS:
        return FORWARD_TRANSITIONS[key], "forward"

    # Check backward
    if key in BACKWARD_TRANSITIONS:
        return BACKWARD_TRANSITIONS[key], "backward"

    # Check error
    if key in ERROR_TRANSITIONS:
        return ERROR_TRANSITIONS[key], "error"

    # ON_HOLD from any active state
    if to_status == DealStatus.ON_HOLD and from_status in ACTIVE_STATES:
        return {"gate": "human"}, "hold"

    # Resume from ON_HOLD (goes back to previous_status — handled in engine)
    if from_status == DealStatus.ON_HOLD and to_status in ACTIVE_STATES:
        return {"gate": "human"}, "resume"

    # DEAD from any non-terminal state
    if to_status == DealStatus.DEAD and from_status not in TERMINAL_STATES:
        return {"gate": "human"}, "kill"

    # Retry from error states
    if from_status == DealStatus.EXTRACTION_FAILED and to_status == DealStatus.EXTRACTING:
        return {"gate": "human"}, "retry"
    if from_status == DealStatus.MODEL_ERROR and to_status == DealStatus.MODEL_BUILDING:
        return {"gate": "human"}, "retry"

    return None
