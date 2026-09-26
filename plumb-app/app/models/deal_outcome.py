import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DealDistribution(Base):
    __tablename__ = "deal_distributions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    deal_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("deals.id"), nullable=False, index=True)
    lender_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("lenders.id"), nullable=False, index=True)
    distributed_at: Mapped[datetime] = mapped_column(server_default=func.now())
    distributed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    approach_angle: Mapped[str | None] = mapped_column(nullable=True)


class LenderResponse(Base):
    __tablename__ = "lender_responses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    deal_distribution_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("deal_distributions.id"), nullable=False, index=True)
    response_type: Mapped[str] = mapped_column(String(50), nullable=False)
    response_at: Mapped[datetime] = mapped_column(server_default=func.now())
    terms_offered: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    pass_reason: Mapped[str | None] = mapped_column(nullable=True)
    notes: Mapped[str | None] = mapped_column(nullable=True)


class DealClosing(Base):
    __tablename__ = "deal_closings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    deal_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("deals.id"), nullable=False, unique=True)
    winning_lender_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("lenders.id"), nullable=False)
    final_terms: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    closed_at: Mapped[datetime] = mapped_column(server_default=func.now())
    total_turnaround_days: Mapped[int | None] = mapped_column(nullable=True)
    notes: Mapped[str | None] = mapped_column(nullable=True)
