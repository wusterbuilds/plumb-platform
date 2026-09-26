import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Deal(Base):
    __tablename__ = "deals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    deal_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    deal_subtype: Mapped[str | None] = mapped_column(String(50))
    capital_ask: Mapped[str | None] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="docs_received", index=True)
    previous_status: Mapped[str | None] = mapped_column(String(50))
    revision_number: Mapped[int] = mapped_column(default=1)
    property_name: Mapped[str | None] = mapped_column(String(255))
    property_address: Mapped[str | None] = mapped_column(String(500))
    property_type: Mapped[str | None] = mapped_column(String(50))
    sponsor: Mapped[dict | None] = mapped_column(JSON)
    regulatory: Mapped[dict | None] = mapped_column(JSON)
    typed_extension: Mapped[dict | None] = mapped_column(JSON)
    market_context: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
    version: Mapped[int] = mapped_column(default=1)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
