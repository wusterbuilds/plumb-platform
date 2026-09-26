import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RiskReport(Base):
    __tablename__ = "risk_reports"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    deal_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("deals.id"), nullable=False, index=True)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    s3_key: Mapped[str] = mapped_column(String(500), nullable=False)
    html_s3_key: Mapped[str | None] = mapped_column(String(500))
    page_count: Mapped[int | None] = mapped_column(Integer)
    file_size: Mapped[int | None] = mapped_column(Integer)
    overall_risk_rating: Mapped[str | None] = mapped_column(String(20))
    risk_summary: Mapped[str | None] = mapped_column(Text)
    findings_count: Mapped[int] = mapped_column(Integer, default=0)
    findings_snapshot: Mapped[list | None] = mapped_column(JSON)
    generated_at: Mapped[datetime] = mapped_column(server_default=func.now())
    generated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(20), default="ready")  # ready, superseded

    __table_args__ = (UniqueConstraint("deal_id", "version_number"),)
