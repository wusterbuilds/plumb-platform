from datetime import datetime

from pydantic import BaseModel


class RiskReportResponse(BaseModel):
    id: str
    deal_id: str
    version_number: int
    page_count: int | None
    file_size: int | None
    overall_risk_rating: str | None
    risk_summary: str | None
    findings_count: int
    generated_at: datetime | None
    status: str

    model_config = {"from_attributes": True}


class RiskReportListResponse(BaseModel):
    versions: list[RiskReportResponse]


class RiskReportStatusResponse(BaseModel):
    deal_id: str
    status: str  # idle, ready
    latest_version: RiskReportResponse | None = None
