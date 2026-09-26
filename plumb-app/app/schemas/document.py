import uuid
from datetime import datetime

from pydantic import BaseModel

from app.schemas.enums import DocumentStatus, DocumentType


class DocumentResponse(BaseModel):
    id: uuid.UUID
    deal_id: uuid.UUID
    filename: str
    document_type: DocumentType | None
    mime_type: str
    s3_key: str
    file_size: int | None
    page_count: int | None
    classification_confidence: float | None
    status: DocumentStatus
    superseded_by: uuid.UUID | None
    uploaded_at: datetime
    uploaded_by: uuid.UUID

    model_config = {"from_attributes": True}


class DocumentListResponse(BaseModel):
    documents: list[DocumentResponse]
    total: int
