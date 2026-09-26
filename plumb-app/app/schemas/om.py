from datetime import datetime

from pydantic import BaseModel


class OMGenerateRequest(BaseModel):
    regenerate_narratives: bool = True


class OMGenerateResponse(BaseModel):
    deal_id: str
    status: str  # "generating"
    message: str


class OMVersionResponse(BaseModel):
    id: str
    deal_id: str
    version_number: int
    page_count: int | None
    file_size: int | None
    generated_at: datetime | None
    status: str

    model_config = {"from_attributes": True}


class OMVersionListResponse(BaseModel):
    versions: list[OMVersionResponse]


class OMStatusResponse(BaseModel):
    deal_id: str
    status: str  # "idle", "generating", "ready"
    latest_version: OMVersionResponse | None = None


class OMNarrativeUpdate(BaseModel):
    transaction_overview: list[str] | None = None
    investment_highlights: list[dict] | None = None
    market_narrative: list[dict] | None = None
    sponsor_bios: dict[str, list[str]] | None = None
