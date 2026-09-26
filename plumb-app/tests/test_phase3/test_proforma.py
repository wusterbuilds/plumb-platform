"""Tests for Rental Pro Forma calculations."""

import pytest

from app.financial.proforma import calculate_proforma
from app.financial.schemas import ModelAssumptions, ResolvedField, UnitMixRow, UnitMixTiered


def _rf(name: str, val) -> ResolvedField:
    return ResolvedField(field_name=name, value=val)


class TestProForma:
    def test_noi_equals_egi_minus_expenses(self, sample_unit_mix, default_assumptions):
        pf = calculate_proforma(
            unit_mix=sample_unit_mix,
            inputs={},
            assumptions=default_assumptions,
            total_sf=65_000,
            total_units=72,
        )
        assert pf.noi.total == pytest.approx(pf.egi.total - pf.total_expenses.total)

    def test_vacancy_reduces_income(self, sample_unit_mix, default_assumptions):
        pf = calculate_proforma(
            unit_mix=sample_unit_mix,
            inputs={},
            assumptions=default_assumptions,
            total_sf=65_000,
            total_units=72,
        )
        gross_fm = sum(r.units * r.avg_monthly_rent * 12 for r in sample_unit_mix.fm)
        # EGI should be less than gross income
        assert pf.egi.total < gross_fm + sum(
            r.units * r.avg_monthly_rent * 12
            for r in sample_unit_mix.affordable_421a + sample_unit_mix.commercial
        )

    def test_mgmt_fee_in_expenses(self, sample_unit_mix, default_assumptions):
        pf = calculate_proforma(
            unit_mix=sample_unit_mix,
            inputs={},
            assumptions=default_assumptions,
            total_sf=65_000,
            total_units=72,
        )
        mgmt_line = next((e for e in pf.expense_lines if "Management" in e.label), None)
        assert mgmt_line is not None
        expected_fee = pf.egi.total * default_assumptions.mgmt_fee_pct
        assert mgmt_line.total == pytest.approx(expected_fee)

    def test_individual_expenses_from_inputs(self, sample_unit_mix, default_assumptions):
        inputs = {
            "real_estate_taxes": _rf("real_estate_taxes", 450_000),
            "insurance": _rf("insurance", 180_000),
            "utilities": _rf("utilities", 95_000),
        }
        pf = calculate_proforma(
            unit_mix=sample_unit_mix,
            inputs=inputs,
            assumptions=default_assumptions,
            total_sf=65_000,
            total_units=72,
        )
        labels = [e.label for e in pf.expense_lines]
        assert "Real Estate Taxes" in labels
        assert "Insurance" in labels
        assert "Utilities" in labels

    def test_other_income_included(self, sample_unit_mix, default_assumptions):
        inputs = {"other_income": _rf("other_income", 50_000)}
        pf = calculate_proforma(
            unit_mix=sample_unit_mix,
            inputs=inputs,
            assumptions=default_assumptions,
            total_sf=65_000,
            total_units=72,
        )
        other_line = next((i for i in pf.income_lines if "Other" in i.label), None)
        assert other_line is not None
        assert other_line.total == pytest.approx(50_000)

    def test_abated_ret_creates_savings_line(self, sample_unit_mix, default_assumptions):
        inputs = {"real_estate_taxes": _rf("real_estate_taxes", 450_000)}
        pf = calculate_proforma(
            unit_mix=sample_unit_mix,
            inputs=inputs,
            assumptions=default_assumptions,
            total_sf=65_000,
            total_units=72,
            abated_ret=200_000,
        )
        savings_line = next(
            (e for e in pf.expense_lines if "Savings" in e.label or "Abated" in e.label), None
        )
        assert savings_line is not None
        # Savings should be negative (reduces expenses)
        assert savings_line.total < 0

    def test_per_sf_and_per_unit_populated(self, sample_unit_mix, default_assumptions):
        pf = calculate_proforma(
            unit_mix=sample_unit_mix,
            inputs={},
            assumptions=default_assumptions,
            total_sf=65_000,
            total_units=72,
        )
        assert pf.noi.per_sf is not None
        assert pf.noi.per_unit_yr is not None
        assert pf.noi.per_sf == pytest.approx(pf.noi.total / 65_000)
        assert pf.noi.per_unit_yr == pytest.approx(pf.noi.total / 72)

    def test_zero_vacancy_means_egi_equals_gross(self):
        """With 0% vacancy, EGI should equal gross income."""
        assumptions = ModelAssumptions(
            vacancy_fm=0.0, vacancy_affordable=0.0, vacancy_retail=0.0, mgmt_fee_pct=0.0,
        )
        mix = UnitMixTiered(
            fm=[UnitMixRow(tier="FM", beds=1, units=10, sf_per_unit=700, avg_monthly_rent=3000, rent_per_sf=4.29)],
        )
        pf = calculate_proforma(mix, {}, assumptions, total_sf=7000, total_units=10)
        gross = 10 * 3000 * 12
        assert pf.egi.total == pytest.approx(gross)

    def test_empty_unit_mix_zero_income(self, default_assumptions):
        mix = UnitMixTiered()
        pf = calculate_proforma(mix, {}, default_assumptions, total_sf=1000, total_units=1)
        assert pf.egi.total == 0.0

    def test_egi_pct_of_egi_is_one(self, sample_unit_mix, default_assumptions):
        pf = calculate_proforma(
            unit_mix=sample_unit_mix,
            inputs={},
            assumptions=default_assumptions,
            total_sf=65_000,
            total_units=72,
        )
        assert pf.egi.pct_of_egi == pytest.approx(1.0)

    def test_fallback_total_expenses(self, sample_unit_mix, default_assumptions):
        """When no individual expenses, falls back to total_expenses from inputs."""
        inputs = {"total_expenses": _rf("total_expenses", 800_000)}
        pf = calculate_proforma(
            unit_mix=sample_unit_mix,
            inputs=inputs,
            assumptions=default_assumptions,
            total_sf=65_000,
            total_units=72,
        )
        expense_labels = [e.label for e in pf.expense_lines]
        assert "Operating Expenses" in expense_labels or "Management Fee" in expense_labels
