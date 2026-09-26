"""Tests for Sensitivity Matrix calculations."""

import pytest

from app.financial.sensitivity import build_sensitivity_matrix


class TestSensitivityMatrix:
    def test_default_7x7_grid(self):
        m = build_sensitivity_matrix(
            base_noi=500_000, base_cap_rate=0.05, loan_amount=20_000_000,
            tdc=40_000_000, abatement_npv=1_000_000,
        )
        assert len(m.cap_rates) == 7
        assert len(m.rent_growth_rates) == 7
        assert len(m.cells) == 7
        assert all(len(row) == 7 for row in m.cells)

    def test_base_case_at_center(self):
        m = build_sensitivity_matrix(
            base_noi=500_000, base_cap_rate=0.05, loan_amount=20_000_000,
            tdc=40_000_000, abatement_npv=0,
        )
        assert m.base_row == 3
        assert m.base_col == 3
        # Base case rent growth should be 0
        assert m.rent_growth_rates[m.base_col] == pytest.approx(0.0)
        # Base case cap rate should be 0.05
        assert m.cap_rates[m.base_row] == pytest.approx(0.05)

    def test_base_cell_value_matches_direct_calc(self):
        noi = 500_000
        cap = 0.05
        npv = 1_500_000
        m = build_sensitivity_matrix(
            base_noi=noi, base_cap_rate=cap, loan_amount=20_000_000,
            tdc=40_000_000, abatement_npv=npv,
        )
        base_cell = m.cells[m.base_row][m.base_col]
        expected_value = (noi / cap) + npv
        assert base_cell.asset_value == pytest.approx(expected_value, rel=1e-4)

    def test_higher_cap_rate_lower_value(self):
        m = build_sensitivity_matrix(
            base_noi=500_000, base_cap_rate=0.05, loan_amount=20_000_000,
            tdc=40_000_000, abatement_npv=0,
        )
        # Higher cap rate row → lower asset value (holding rent growth constant)
        col = m.base_col
        for i in range(len(m.cap_rates) - 1):
            assert m.cells[i][col].asset_value >= m.cells[i + 1][col].asset_value

    def test_higher_rent_growth_higher_value(self):
        m = build_sensitivity_matrix(
            base_noi=500_000, base_cap_rate=0.05, loan_amount=20_000_000,
            tdc=40_000_000, abatement_npv=0,
        )
        # Higher rent growth → higher asset value (holding cap rate constant)
        row = m.base_row
        for j in range(len(m.rent_growth_rates) - 1):
            assert m.cells[row][j].asset_value <= m.cells[row][j + 1].asset_value

    def test_ltv_inversely_related_to_cap_rate(self):
        m = build_sensitivity_matrix(
            base_noi=500_000, base_cap_rate=0.05, loan_amount=20_000_000,
            tdc=40_000_000, abatement_npv=0,
        )
        col = m.base_col
        # Higher cap rate → lower value → higher LTV
        for i in range(len(m.cap_rates) - 1):
            assert m.cells[i][col].ltv <= m.cells[i + 1][col].ltv

    def test_debt_yield_increases_with_rent_growth(self):
        m = build_sensitivity_matrix(
            base_noi=500_000, base_cap_rate=0.05, loan_amount=20_000_000,
            tdc=40_000_000, abatement_npv=0,
        )
        row = m.base_row
        for j in range(len(m.rent_growth_rates) - 1):
            assert m.cells[row][j].debt_yield <= m.cells[row][j + 1].debt_yield

    def test_cap_rates_25bp_increments(self):
        m = build_sensitivity_matrix(
            base_noi=500_000, base_cap_rate=0.05, loan_amount=20_000_000,
            tdc=40_000_000, abatement_npv=0,
        )
        for i in range(len(m.cap_rates) - 1):
            diff = m.cap_rates[i + 1] - m.cap_rates[i]
            assert diff == pytest.approx(0.0025, abs=1e-6)

    def test_rent_growth_50bp_increments(self):
        m = build_sensitivity_matrix(
            base_noi=500_000, base_cap_rate=0.05, loan_amount=20_000_000,
            tdc=40_000_000, abatement_npv=0,
        )
        for j in range(len(m.rent_growth_rates) - 1):
            diff = m.rent_growth_rates[j + 1] - m.rent_growth_rates[j]
            assert diff == pytest.approx(0.005, abs=1e-6)

    def test_no_negative_cap_rates(self):
        """Even with a very low base cap rate, no cap rate should be <= 0."""
        m = build_sensitivity_matrix(
            base_noi=500_000, base_cap_rate=0.01, loan_amount=20_000_000,
            tdc=40_000_000, abatement_npv=0,
        )
        assert all(c > 0 for c in m.cap_rates)
