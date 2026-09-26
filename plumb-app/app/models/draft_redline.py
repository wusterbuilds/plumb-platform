import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DraftRedline(Base):
    __tablename__ = "draft_redlines"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    deal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("deals.id"), nullable=False, index=True
    )
    artifact_type: Mapped[str] = mapped_column(String(40), nullable=False)
    artifact_ref_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    section_key: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    section_index: Mapped[int | None] = mapped_column(Integer)

    original_text: Mapped[str] = mapped_column(Text, nullable=False)
    edited_text: Mapped[str] = mapped_column(Text, nullable=False)
    diff_hunks: Mapped[dict | None] = mapped_column(JSON)

    rationale: Mapped[str | None] = mapped_column(Text)
    correction_category: Mapped[str | None] = mapped_column(String(40))
    severity: Mapped[str] = mapped_column(String(20), default="moderate")

    archetype_signature: Mapped[str | None] = mapped_column(String(120), index=True)

    reviewer_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    reviewer_role: Mapped[str | None] = mapped_column(String(40))

    episode_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("episodes.id"))
    promoted_to_skill_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))

    applied_in_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)

    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
