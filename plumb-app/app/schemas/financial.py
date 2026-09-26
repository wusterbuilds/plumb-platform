from pydantic import BaseModel


class CalculateRequest(BaseModel):
    assumptions: dict | None = None  # Optional assumption overrides


class CalculateResponse(BaseModel):
    deal_id: str
    status: str  # "success" or "error"
    model: dict | None = None
    errors: list[str] | None = None


class AssumptionsUpdate(BaseModel):
    cap_rate: float | None = None
    vacancy_fm: float | None = None
    vacancy_affordable: float | None = None
    vacancy_retail: float | None = None
    mgmt_fee_pct: float | None = None
    assessment_growth: float | None = None
    tax_rate_growth: float | None = None
    discount_rate: float | None = None
