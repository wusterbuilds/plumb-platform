"""Tests for Valuation calculations."""

import pytest

from app.financial.schemas import ModelAssumptions
from app.financial.valuation import calculate_valuation


class TestValuation:
    def test_asset_value_equals_a_plus_b(self):
        v = calculate_valuation(
            noi=500_000,
            assumptions=ModelAssumptions(cap_rate=0.05),
            abatement_npv=2_000_000,
            tdc=44_000_000,
            loan_amount=30_000_000,
            total_units=72,
            gsf=65_000,
        )
        assert v.total_asset_value == pytest.approx(v.estimated_value_a + v.abatement_value_b)

    def test_component_a_is_noi_over_cap(self):
        noi = 600_000
        cap = 0.045
        v = calculate_valuation(
            noi=noi,
            assumptions=ModelAssumptions(cap_rate=cap),
            abatement_npv=None,
            tdc=40_000_000,
            loan_amount=25_000_000,
            total_units=50,
            gsf=40_000,
        )
        assert v.estimated_value_a == pytest.approx(noi / cap)

    def test_no_abatement_means_b_is_zero(self):
        v = calculate_valuation(
            noi=500_000,
            assumptions=ModelAssumptions(cap_rate=0.05),
            abatement_npv=None,
            tdc=30_000_000,
            loan_amount=20_000_000,
            total_units=50,
            gsf=30_000,
        )
        assert v.abatement_value_b == 0.0
        assert v.total_asset_value == pytest.approx(v.estimated_value_a)

    def test_ltv_is_loan_over_value(self):
        v = calculate_valuation(
            noi=500_000,
            assumptions=ModelAssumptions(cap_rate=0.05),
            abatement_npv=None,
            tdc=30_000_000,
            loan_amount=6_000_000,
            total_units=50,
            gsf=30_000,
        )
        # NOI/cap = 10M, LTV = 6M/10M = 0.6
        assert v.stabilized_ltv == pytest.approx(0.6)

    def test_debt_yield_is_noi_over_loan(self):
        v = calculate_valuation(
            noi=750_000,
            assumptions=ModelAssumptions(cap_rate=0.05),
            abatement_npv=None,
            tdc=30_000_000,
            loan_amount=10_000_000,
            total_units=50,
            gsf=30_000,
        )
        assert v.debt_yield == pytest.approx(0.075)

    def test_yield_on_cost(self):
        noi = 500_000
        tdc = 40_000_000
        v = calculate_valuation(
            noi=noi,
            assumptions=ModelAssumptions(cap_rate=0.05),
            abatement_npv=None,
            tdc=tdc,
            loan_amount=25_000_000,
            total_units=50,
            gsf=40_000,
        )
        assert v.yield_on_cost == pytest.approx(noi / tdc)

    def test_per_unit_and_per_gsf(self):
        v = calculate_valuation(
            noi=500_000,
            assumptions=ModelAssumptions(cap_rate=0.05),
            abatement_npv=1_000_000,
            tdc=30_000_000,
            loan_amount=20_000_000,
            total_units=50,
            gsf=40_000,
        )
        assert v.value_per_unit == pytest.approx(v.total_asset_value / 50)
        assert v.value_per_gsf == pytest.approx(v.total_asset_value / 40_000)
        assert v.debt_per_unit == pytest.approx(20_000_000 / 50)
        assert v.debt_per_gsf == pytest.approx(20_000_000 / 40_000)

    def test_zero_loan_means_zero_ltv_and_debt_yield(self):
        v = calculate_valuation(
            noi=500_000,
            assumptions=ModelAssumptions(cap_rate=0.05),
            abatement_npv=None,
            tdc=10_000_000,
            loan_amount=0,
            total_units=20,
            gsf=15_000,
        )
        assert v.stabilized_ltv == 0.0
        assert v.debt_yield == 0.0

    def test_zero_tdc_means_zero_yield_on_cost(self):
        v = calculate_valuation(
            noi=500_000,
            assumptions=ModelAssumptions(cap_rate=0.05),
            abatement_npv=None,
            tdc=0,
            loan_amount=0,
            total_units=20,
            gsf=15_000,
        )
        assert v.yield_on_cost == 0.0
