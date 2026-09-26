import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class OMVersion(Base):
    __tablename__ = "om_versions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    deal_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("deals.id"), nullable=False, index=True)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    s3_key: Mapped[str] = mapped_column(String(500), nullable=False)
    html_s3_key: Mapped[str | None] = mapped_column(String(500))
    page_count: Mapped[int | None] = mapped_column(Integer)
    file_size: Mapped[int | None] = mapped_column(Integer)
    generated_at: Mapped[datetime] = mapped_column(server_default=func.now())
    generated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    financial_model_snapshot: Mapped[dict | None] = mapped_column(JSON)
    narrative_snapshot: Mapped[dict | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default="generating")  # generating, ready, superseded

    approval_status: Mapped[str | None] = mapped_column(String(20))
    archetype_signature: Mapped[str | None] = mapped_column(String(120), index=True)
    exemplar_eligible: Mapped[bool] = mapped_column(default=False)
    redline_count: Mapped[int] = mapped_column(Integer, default=0)
    applied_episodes: Mapped[list | None] = mapped_column(JSON)

    __table_args__ = (UniqueConstraint("deal_id", "version_number"),)
