import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.enums import (
    CrossRefResolution,
    CrossRefResult,
    ExtractionMethod,
    FlagColor,
)


class ExtractedValueResponse(BaseModel):
    id: uuid.UUID
    deal_id: uuid.UUID
    field_name: str
    value: Any | None
    source_doc_id: uuid.UUID | None
    source_page: int | None
    source_text_snippet: str | None
    confidence_score: float | None
    confidence_basis: dict | None = None
    extraction_method: ExtractionMethod | None
    prompt_version: str | None
    flag: FlagColor
    reviewed_by: uuid.UUID | None
    reviewed_at: datetime | None
    override_value: Any | None
    override_reason: str | None
    version: int
    created_at: datetime

    model_config = {"from_attributes": True}


class ExtractedValueListResponse(BaseModel):
    values: list[ExtractedValueResponse]
    total: int


class CrossReferenceResponse(BaseModel):
    id: uuid.UUID
    deal_id: uuid.UUID
    rule_name: str
    field_a: str
    field_a_value: str | None
    field_a_source_doc_id: uuid.UUID | None
    field_b: str
    field_b_value: str | None
    field_b_source_doc_id: uuid.UUID | None
    result: CrossRefResult
    tolerance_applied: str | None
    delta: str | None
    resolution: CrossRefResolution | None
    resolved_by: uuid.UUID | None
    resolved_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class CrossReferenceListResponse(BaseModel):
    cross_references: list[CrossReferenceResponse]
    total: int


# --- Request schemas ---


class ExtractionStartResponse(BaseModel):
    deal_id: uuid.UUID
    task_id: str
    message: str


class DocumentExtractionStatus(BaseModel):
    doc_id: uuid.UUID
    filename: str
    document_type: str | None
    status: str
    classification_confidence: float | None


class ExtractionStatusResponse(BaseModel):
    deal_id: uuid.UUID
    deal_status: str
    documents: list[DocumentExtractionStatus]
    total_fields_extracted: int
    fields_by_flag: dict[str, int]


class OverrideRequest(BaseModel):
    override_value: str = Field(..., min_length=1)
    override_reason: str = Field(..., min_length=1)
    version: int = Field(..., description="Current version for optimistic concurrency")


class ResolveRequest(BaseModel):
    resolution: CrossRefResolution
