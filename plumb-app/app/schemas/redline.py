from datetime import datetime

from pydantic import BaseModel, Field


CORRECTION_CATEGORIES = (
    "factual_error",
    "tone",
    "omission",
    "aggressive_assumption",
    "compliance",
    "positioning",
)

SEVERITIES = ("minor", "moderate", "material")


class RedlineCreate(BaseModel):
    artifact_type: str = Field(default="om_section")
    section_key: str
    section_index: int | None = None
    original_text: str
    edited_text: str
    rationale: str | None = None
    correction_category: str | None = None
    severity: str = "moderate"


class RedlineResponse(BaseModel):
    id: str
    deal_id: str
    artifact_type: str
    artifact_ref_id: str
    section_key: str
    section_index: int | None
    original_text: str
    edited_text: str
    rationale: str | None
    correction_category: str | None
    severity: str
    archetype_signature: str | None
    reviewer_id: str | None
    reviewer_role: str | None
    episode_id: str | None
    applied_in_version_id: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class RedlineListResponse(BaseModel):
    redlines: list[RedlineResponse]
    total: int


class RerunWithFeedbackResponse(BaseModel):
    deal_id: str
    status: str
    message: str
    lessons_applied: list[str]


class OMNarrativeSnapshot(BaseModel):
    """Subset of the OMVersion narrative_snapshot, normalized for the editor.

    The on-disk shape is permissive (different prompts shipped at different
    times); this response normalizes the four primary editable section
    families that the redline UI knows how to render.
    """

    version_id: str
    version_number: int
    transaction_overview: list[str] = Field(default_factory=list)
    investment_highlights: list[dict] = Field(default_factory=list)
    market_narrative: list[dict] = Field(default_factory=list)
    sponsor_bios: dict[str, list[str]] = Field(default_factory=dict)
    redline_count: int = 0
    archetype_signature: str | None = None
    approval_status: str | None = None


class OMApproveResponse(BaseModel):
    deal_id: str
    version_id: str
    status: str
    archetype_signature: str | None
    exemplar_eligible: bool
