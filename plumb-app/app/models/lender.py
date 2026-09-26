import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Lender(Base):
    __tablename__ = "lenders"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    lender_type: Mapped[str] = mapped_column(String(50), nullable=False)
    general_preferences: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    credit_committee_notes: Mapped[str | None] = mapped_column(nullable=True)
    relationship_contacts: Mapped[list | None] = mapped_column(JSON, default=list)
    notes: Mapped[str | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())


class LenderAppetite(Base):
    __tablename__ = "lender_appetite"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lender_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("lenders.id"), nullable=False, index=True)
    property_types: Mapped[list | None] = mapped_column(JSON, default=list)
    geographies: Mapped[list | None] = mapped_column(JSON, default=list)
    deal_size_min: Mapped[float | None] = mapped_column(nullable=True)
    deal_size_max: Mapped[float | None] = mapped_column(nullable=True)
    ltc_max: Mapped[float | None] = mapped_column(nullable=True)
    rate_indication: Mapped[str | None] = mapped_column(String(100), nullable=True)
    term_range: Mapped[str | None] = mapped_column(String(100), nullable=True)
    recourse_preference: Mapped[str | None] = mapped_column(String(50), nullable=True)
    appetite_signal: Mapped[str] = mapped_column(String(50), default="active")
    source: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source_detail: Mapped[str | None] = mapped_column(nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(server_default=func.now())
    recorded_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(nullable=True)
    is_stale: Mapped[bool] = mapped_column(default=False)


class LenderTransaction(Base):
    __tablename__ = "lender_transactions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lender_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("lenders.id"), nullable=False, index=True)
    deal_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("deals.id"), nullable=True)
    property_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    geography: Mapped[str | None] = mapped_column(String(100), nullable=True)
    deal_size: Mapped[float | None] = mapped_column(nullable=True)
    ltc_quoted: Mapped[float | None] = mapped_column(nullable=True)
    rate_quoted: Mapped[str | None] = mapped_column(String(100), nullable=True)
    term_quoted: Mapped[str | None] = mapped_column(String(100), nullable=True)
    outcome: Mapped[str | None] = mapped_column(String(50), nullable=True)
    pass_reason: Mapped[str | None] = mapped_column(nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    source: Mapped[str | None] = mapped_column(String(50), nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(server_default=func.now())
