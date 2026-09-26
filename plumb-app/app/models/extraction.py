import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ExtractedValue(Base):
    __tablename__ = "extracted_values"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    deal_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("deals.id"), nullable=False, index=True)
    field_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    value: Mapped[str | None] = mapped_column(Text)
    source_doc_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("documents.id"))
    source_page: Mapped[int | None] = mapped_column()
    source_text_snippet: Mapped[str | None] = mapped_column(Text)
    confidence_score: Mapped[float | None] = mapped_column()
    confidence_basis: Mapped[dict | None] = mapped_column(JSON)
    extraction_method: Mapped[str | None] = mapped_column(String(50))
    prompt_version: Mapped[str | None] = mapped_column(String(20))
    flag: Mapped[str] = mapped_column(String(10), nullable=False, default="red")
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column()
    override_value: Mapped[str | None] = mapped_column(Text)
    override_reason: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class CrossReference(Base):
    __tablename__ = "cross_references"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    deal_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("deals.id"), nullable=False, index=True)
    rule_name: Mapped[str] = mapped_column(String(100), nullable=False)
    field_a: Mapped[str] = mapped_column(String(100), nullable=False)
    field_a_value: Mapped[str | None] = mapped_column(Text)
    field_a_source_doc_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("documents.id"))
    field_b: Mapped[str] = mapped_column(String(100), nullable=False)
    field_b_value: Mapped[str | None] = mapped_column(Text)
    field_b_source_doc_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("documents.id"))
    result: Mapped[str] = mapped_column(String(20), nullable=False)
    tolerance_applied: Mapped[str | None] = mapped_column(String(20))
    delta: Mapped[str | None] = mapped_column(Text)
    resolution: Mapped[str | None] = mapped_column(String(20))
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    resolved_at: Mapped[datetime | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
