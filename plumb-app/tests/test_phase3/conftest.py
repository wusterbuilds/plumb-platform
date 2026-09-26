"""Shared fixtures for Phase 3 financial engine tests.

All fixtures here produce plain dicts / Pydantic models — no database needed.
"""

import pytest

from app.financial.schemas import (
    ModelAssumptions,
    ResolvedField,
    UnitMixRow,
    UnitMixTiered,
)


# ---------------------------------------------------------------------------
# Override root-level autouse fixtures that require PostgreSQL
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def cleanup_db():
    """No-op override — Phase 3 unit tests don't use the database."""
    yield


@pytest.fixture
def test_engine():
    """No-op override — Phase 3 unit tests don't use the database."""
    yield None


# ---------------------------------------------------------------------------
# Assumptions
# ---------------------------------------------------------------------------

@pytest.fixture
def default_assumptions() -> ModelAssumptions:
    return ModelAssumptions()


@pytest.fixture
def custom_assumptions() -> ModelAssumptions:
    return ModelAssumptions(
        cap_rate=0.05,
        vacancy_fm=0.05,
        vacancy_affordable=0.03,
        vacancy_retail=0.10,
        mgmt_fee_pct=0.03,
        assessment_growth=0.02,
        tax_rate_growth=0.005,
        discount_rate=0.06,
    )


# ---------------------------------------------------------------------------
# Resolved inputs (simulates resolve_inputs output without DB)
# ---------------------------------------------------------------------------

def _rf(field_name: str, value, confidence: float = 0.9) -> ResolvedField:
    return ResolvedField(
        field_name=field_name,
        value=value,
        confidence_score=confidence,
    )


@pytest.fixture
def linden_villa_inputs() -> dict[str, ResolvedField]:
    """Realistic inputs for a fully synthetic construction-loan scenario."""
    return {
        "acquisition_cost": _rf("acquisition_cost", 5_500_000),
        "hard_costs": _rf("hard_costs", 28_000_000),
        "soft_costs": _rf("soft_costs", 5_200_000),
        "financing_costs": _rf("financing_costs", 1_800_000),
        "interest_reserve": _rf("interest_reserve", 3_500_000),
        "total_development_cost": _rf("total_development_cost", 44_000_000),
        "loan_amount": _rf("loan_amount", 30_000_000),
        "gross_sf": _rf("gross_sf", 65_000),
        "zfa": _rf("zfa", 58_000),
        "nra": _rf("nra", 52_000),
        "residential_sf": _rf("residential_sf", 60_000),
        "commercial_sf": _rf("commercial_sf", 5_000),
        "total_units": _rf("total_units", 72),
        "borough": _rf("borough", "Brooklyn"),
        "block_lot": _rf("block_lot", "03784/0001"),
        "av_prior": _rf("av_prior", 2_500_000),
        "abatement_program": _rf("abatement_program", "C"),
        "real_estate_taxes": _rf("real_estate_taxes", 450_000),
        "insurance": _rf("insurance", 180_000),
        "repairs_maintenance": _rf("repairs_maintenance", 120_000),
        "payroll": _rf("payroll", 220_000),
        "utilities": _rf("utilities", 95_000),
        "other_income": _rf("other_income", 36_000),
    }


@pytest.fixture
def minimal_inputs() -> dict[str, ResolvedField]:
    """Bare-minimum inputs to exercise fallback paths."""
    return {
        "hard_costs": _rf("hard_costs", 10_000_000),
        "soft_costs": _rf("soft_costs", 2_000_000),
        "loan_amount": _rf("loan_amount", 8_000_000),
        "gross_sf": _rf("gross_sf", 20_000),
        "total_units": _rf("total_units", 20),
    }


# ---------------------------------------------------------------------------
# Unit mix
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_unit_mix() -> UnitMixTiered:
    """Pre-built unit mix with FM + 421A tiers."""
    return UnitMixTiered(
        fm=[
            UnitMixRow(tier="FM", beds=0, baths=1, units=10, sf_per_unit=500, avg_monthly_rent=2800, rent_per_sf=5.6),
            UnitMixRow(tier="FM", beds=1, baths=1, units=20, sf_per_unit=650, avg_monthly_rent=3500, rent_per_sf=5.385),
            UnitMixRow(tier="FM", beds=2, baths=1, units=12, sf_per_unit=900, avg_monthly_rent=4500, rent_per_sf=5.0),
        ],
        affordable_421a=[
            UnitMixRow(tier="421A", beds=0, baths=1, units=5, sf_per_unit=450, avg_monthly_rent=1200, rent_per_sf=2.667),
            UnitMixRow(tier="421A", beds=1, baths=1, units=15, sf_per_unit=600, avg_monthly_rent=1600, rent_per_sf=2.667),
            UnitMixRow(tier="421A", beds=2, baths=1, units=8, sf_per_unit=800, avg_monthly_rent=2000, rent_per_sf=2.5),
        ],
        mih=[],
        commercial=[
            UnitMixRow(tier="Commercial", beds=None, baths=None, units=2, sf_per_unit=2500, avg_monthly_rent=5000, rent_per_sf=2.0),
        ],
        total=[],
    )


@pytest.fixture
def raw_unit_mix_data() -> list[dict]:
    """Raw extracted unit mix dicts as they'd come from the LLM."""
    return [
        {"tier": "Free Market", "beds": 0, "units": 10, "sf_per_unit": 500, "avg_monthly_rent": 2800},
        {"tier": "Free Market", "beds": 1, "units": 20, "sf_per_unit": 650, "avg_monthly_rent": 3500},
        {"tier": "free-market", "beds": 2, "units": 12, "sf_per_unit": 900, "rent": 4500},
        {"tier": "421-a", "beds": 0, "units": 5, "sf": 450, "monthly_rent": 1200},
        {"tier": "affordable", "beds": 1, "units": 15, "sf_per_unit": 600, "avg_monthly_rent": 1600},
        {"type": "421a", "beds": 2, "units": 8, "sf_per_unit": 800, "avg_monthly_rent": 2000},
        {"tier": "retail", "beds": None, "units": 2, "area": 2500, "rent": 5000},
    ]
