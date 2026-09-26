"""Tests for 421(a) Abatement Schedule calculations."""

import pytest

from app.financial.abatement import (
    _exemption_schedule_a,
    _exemption_schedule_b,
    _exemption_schedule_c,
    calculate_abatement,
)
from app.financial.schemas import ModelAssumptions


class TestExemptionSchedules:
    def test_option_a_all_100_pct(self):
        schedule = _exemption_schedule_a(35)
        assert len(schedule) == 35
        assert all(p == 1.0 for p in schedule)

    def test_option_b_25_years_full_then_decline(self):
        schedule = _exemption_schedule_b(35)
        assert len(schedule) == 35
        assert all(p == 1.0 for p in schedule[:25])
        # Year 26 = 0.98, Year 27 = 0.96, ...
        assert schedule[25] == pytest.approx(0.98)
        assert schedule[26] == pytest.approx(0.96)
        # Floors at 0.80
        assert schedule[34] == pytest.approx(0.80)

    def test_option_c_25_years_full_then_10pct_decline(self):
        schedule = _exemption_schedule_c(35)
        assert len(schedule) == 35
        assert all(p == 1.0 for p in schedule[:25])
        assert schedule[25] == pytest.approx(0.90)
        assert schedule[26] == pytest.approx(0.80)
        assert schedule[33] == pytest.approx(0.10)
        assert schedule[34] == pytest.approx(0.0)


class TestAbatementCalculation:
    def test_35_years_generated(self, default_assumptions):
        result = calculate_abatement(
            av_prior=2_500_000,
            assumptions=default_assumptions,
            program_option="C",
            benefit_years=35,
        )
        assert len(result.years) == 35
        assert result.program_option == "C"

    def test_year1_no_increase_no_savings(self, default_assumptions):
        """Year 1: assessment hasn't grown, so increase_in_av = 0 → savings = 0."""
        result = calculate_abatement(
            av_prior=2_500_000,
            assumptions=default_assumptions,
        )
        yr1 = result.years[0]
        assert yr1.year == 1
        assert yr1.increase_in_av == 0.0
        assert yr1.exemption_amount == 0.0
        assert yr1.ret_savings == 0.0

    def test_year2_has_savings(self, default_assumptions):
        """Year 2+: assessment grows → increase → exemption → savings > 0."""
        result = calculate_abatement(
            av_prior=2_500_000,
            assumptions=default_assumptions,
            program_option="C",
        )
        yr2 = result.years[1]
        assert yr2.increase_in_av > 0
        assert yr2.ret_savings > 0

    def test_npv_is_positive(self, default_assumptions):
        result = calculate_abatement(
            av_prior=2_500_000,
            assumptions=default_assumptions,
            program_option="C",
        )
        assert result.npv_of_tax_savings > 0

    def test_option_a_npv_higher_than_c(self, default_assumptions):
        """Option A (full exemption all years) should have higher NPV than Option C."""
        result_a = calculate_abatement(
            av_prior=2_500_000, assumptions=default_assumptions, program_option="A",
        )
        result_c = calculate_abatement(
            av_prior=2_500_000, assumptions=default_assumptions, program_option="C",
        )
        assert result_a.npv_of_tax_savings > result_c.npv_of_tax_savings

    def test_higher_av_means_higher_npv(self, default_assumptions):
        result_low = calculate_abatement(
            av_prior=1_000_000, assumptions=default_assumptions,
        )
        result_high = calculate_abatement(
            av_prior=5_000_000, assumptions=default_assumptions,
        )
        assert result_high.npv_of_tax_savings > result_low.npv_of_tax_savings

    def test_custom_tax_rate(self, default_assumptions):
        result = calculate_abatement(
            av_prior=2_500_000,
            assumptions=default_assumptions,
            base_tax_rate=0.12,
        )
        yr1 = result.years[0]
        assert yr1.tax_rate == pytest.approx(0.12)

    def test_assessment_grows_each_year(self, default_assumptions):
        result = calculate_abatement(
            av_prior=2_500_000, assumptions=default_assumptions,
        )
        for i in range(1, len(result.years)):
            assert result.years[i].taxable_assessment > result.years[i - 1].taxable_assessment

    def test_unabated_ret_increases(self, default_assumptions):
        result = calculate_abatement(
            av_prior=2_500_000, assumptions=default_assumptions,
        )
        for i in range(1, len(result.years)):
            assert result.years[i].unabated_ret >= result.years[i - 1].unabated_ret

    def test_borough_and_block_lot_stored(self, default_assumptions):
        result = calculate_abatement(
            av_prior=2_500_000,
            assumptions=default_assumptions,
            borough="Brooklyn",
            block_lot="03784/0001",
        )
        assert result.borough == "Brooklyn"
        assert result.block_lot == "03784/0001"

    def test_option_c_year35_zero_exempt(self, default_assumptions):
        result = calculate_abatement(
            av_prior=2_500_000, assumptions=default_assumptions, program_option="C",
        )
        yr35 = result.years[34]
        assert yr35.pct_exempt == pytest.approx(0.0)
        assert yr35.exemption_amount == pytest.approx(0.0)
        # With 0% exemption, abated == unabated
        assert yr35.abated_ret == pytest.approx(yr35.unabated_ret)
        assert yr35.ret_savings == pytest.approx(0.0)
