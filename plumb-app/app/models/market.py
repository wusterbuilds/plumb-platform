import uuid
from datetime import datetime

from sqlalchemy import Float, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MarketData(Base):
    __tablename__ = "market_data"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    deal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("deals.id"), nullable=False, index=True
    )
    data_source: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    data_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    data: Mapped[dict | None] = mapped_column(JSON)
    raw_data: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(Text)
    source_doc_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id")
    )
    confidence_score: Mapped[float | None] = mapped_column(Float)
    fetch_date: Mapped[datetime | None] = mapped_column()
    cache_expires_at: Mapped[datetime | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class PublicDataCache(Base):
    __tablename__ = "public_data_cache"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    cache_key: Mapped[str] = mapped_column(String(500), nullable=False, unique=True, index=True)
    data_source: Mapped[str] = mapped_column(String(50), nullable=False)
    raw_response: Mapped[str | None] = mapped_column(Text)
    fetched_at: Mapped[datetime] = mapped_column(server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(nullable=False)
