"""Risk Assessment Report schemas."""

from __future__ import annotations

from pydantic import BaseModel


class RiskFinding(BaseModel):
    """A single risk finding with provenance."""

    category: str  # capital_stack, construction, zoning, sponsor, market, title, environmental, underwriting
    severity: str  # critical, warning, info, positive
    title: str
    description: str
    source: str  # Cited data source (e.g., "ACRIS", "Sponsor Financial Model", "DOB BIS")
    evidence: str  # The receipt — specific numbers/text backing the finding
    recommendation: str = ""  # Actionable mitigant for lender/credit committee


class RiskContext(BaseModel):
    """Full context for rendering a Risk Assessment Report PDF."""

    deal_id: str
    property_name: str = ""
    property_address: str = ""
    deal_type_label: str = "CONSTRUCTION FINANCING"

    # Overall assessment
    overall_risk_rating: str = "medium"  # high, medium, low
    risk_summary: str = ""

    # Screening results
    screening_recommendation: str = ""  # proceed, proceed_with_caution, decline
    screening_confidence: float = 0.0
    screening_strengths: list[str] = []
    screening_risks: list[str] = []
    screening_missing: list[str] = []

    # Financial summary
    loan_amount: float = 0.0
    total_development_cost: float = 0.0
    ltc: float = 0.0
    equity: float = 0.0
    total_units: int = 0
    gross_sellout: float = 0.0
    profit_margin: float = 0.0

    # All findings grouped by category
    findings: list[RiskFinding] = []
