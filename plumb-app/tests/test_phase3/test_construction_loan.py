"""Tests for Sources & Uses and Construction Budget calculations."""

import pytest

from app.financial.construction_loan import build_budget_detail, calculate_sources_uses
from app.financial.schemas import ModelAssumptions, ResolvedField


# ---------------------------------------------------------------------------
# Sources & Uses
# ---------------------------------------------------------------------------

class TestSourcesUses:
    def test_sources_equal_uses(self, linden_villa_inputs, default_assumptions):
        su = calculate_sources_uses(linden_villa_inputs, default_assumptions, zfa=58_000, gsf=65_000, nra=52_000)
        assert su.total_sources.total == pytest.approx(su.total_uses.total)

    def test_tdc_from_components(self, default_assumptions):
        """When total_development_cost is not provided, TDC = sum of components."""
        inputs = {
            "acquisition_cost": ResolvedField(field_name="acquisition_cost", value=1_000_000),
            "hard_costs": ResolvedField(field_name="hard_costs", value=5_000_000),
            "soft_costs": ResolvedField(field_name="soft_costs", value=1_000_000),
            "financing_costs": ResolvedField(field_name="financing_costs", value=500_000),
            "interest_reserve": ResolvedField(field_name="interest_reserve", value=500_000),
            "loan_amount": ResolvedField(field_name="loan_amount", value=5_000_000),
        }
        su = calculate_sources_uses(inputs, default_assumptions, zfa=None, gsf=10_000, nra=8_000)
        assert su.total_uses.total == pytest.approx(8_000_000)
        assert su.total_sources.total == pytest.approx(8_000_000)

    def test_equity_is_tdc_minus_loan(self, linden_villa_inputs, default_assumptions):
        su = calculate_sources_uses(linden_villa_inputs, default_assumptions, zfa=58_000, gsf=65_000, nra=52_000)
        loan_line = su.sources[0]
        equity_line = su.sources[1]
        assert loan_line.label == "Construction Loan"
        assert equity_line.label == "Sponsor Equity"
        assert loan_line.total + equity_line.total == pytest.approx(su.total_sources.total)

    def test_per_unit_metrics(self, linden_villa_inputs, default_assumptions):
        su = calculate_sources_uses(linden_villa_inputs, default_assumptions, zfa=58_000, gsf=65_000, nra=52_000)
        for line in su.uses:
            if line.total > 0:
                assert line.per_gsf == pytest.approx(line.total / 65_000)
                assert line.per_zfa == pytest.approx(line.total / 58_000)
                assert line.per_nra == pytest.approx(line.total / 52_000)

    def test_pct_total_sums_to_one(self, linden_villa_inputs, default_assumptions):
        su = calculate_sources_uses(linden_villa_inputs, default_assumptions, zfa=58_000, gsf=65_000, nra=52_000)
        assert su.total_uses.pct_total == pytest.approx(1.0)
        assert su.total_sources.pct_total == pytest.approx(1.0)

    def test_timing_columns_sum_to_total(self, linden_villa_inputs, default_assumptions):
        su = calculate_sources_uses(linden_villa_inputs, default_assumptions, zfa=58_000, gsf=65_000, nra=52_000)
        for line in su.uses:
            timing_sum = line.prior_to_closing + line.at_closing + line.future_funding
            assert timing_sum == pytest.approx(line.total, rel=1e-6)

    def test_zero_loan_means_all_equity(self, default_assumptions):
        inputs = {
            "hard_costs": ResolvedField(field_name="hard_costs", value=5_000_000),
        }
        su = calculate_sources_uses(inputs, default_assumptions, zfa=None, gsf=10_000, nra=8_000)
        loan_line = su.sources[0]
        equity_line = su.sources[1]
        assert loan_line.total == 0.0
        assert equity_line.total == pytest.approx(su.total_uses.total)

    def test_none_zfa_gives_none_per_zfa(self, default_assumptions):
        inputs = {
            "hard_costs": ResolvedField(field_name="hard_costs", value=5_000_000),
            "loan_amount": ResolvedField(field_name="loan_amount", value=3_000_000),
        }
        su = calculate_sources_uses(inputs, default_assumptions, zfa=None, gsf=10_000, nra=8_000)
        assert su.total_uses.per_zfa is None


# ---------------------------------------------------------------------------
# Budget Detail
# ---------------------------------------------------------------------------

class TestBudgetDetail:
    def test_structured_budget_parsed(self, linden_villa_inputs):
        """When construction_budget_detail is provided, line items are parsed."""
        linden_villa_inputs["construction_budget_detail"] = ResolvedField(
            field_name="construction_budget_detail",
            value=[
                {"label": "Land Acquisition", "category": "acquisition", "total_cost": 5_500_000},
                {"label": "General Construction", "category": "hard", "total_cost": 22_000_000},
                {"label": "Contingency", "category": "hard", "total_cost": 3_000_000},
                {"label": "Architecture & Engineering", "category": "soft", "total_cost": 2_500_000},
            ],
        )
        items = build_budget_detail(linden_villa_inputs, zfa=58_000, gsf=65_000, nsf=52_000)
        assert len(items) == 4
        assert items[0].category == "acquisition"
        assert items[1].category == "hard"
        assert items[2].category == "hard"
        assert items[3].category == "soft"

    def test_fallback_to_category_totals(self, linden_villa_inputs):
        """Without structured detail, uses category-level fields."""
        items = build_budget_detail(linden_villa_inputs, zfa=58_000, gsf=65_000, nsf=52_000)
        categories = {i.category for i in items}
        assert "acquisition" in categories
        assert "hard" in categories

    def test_budget_pct_sums_roughly_to_one(self, linden_villa_inputs):
        items = build_budget_detail(linden_villa_inputs, zfa=58_000, gsf=65_000, nsf=52_000)
        total_pct = sum(i.pct_total for i in items)
        assert total_pct == pytest.approx(1.0, abs=0.01)

    def test_category_classification(self):
        """_classify_category maps keywords correctly."""
        from app.financial.construction_loan import _classify_category
        assert _classify_category("Land Acquisition") == "acquisition"
        assert _classify_category("General Construction") == "hard"
        assert _classify_category("Hard Costs") == "hard"
        assert _classify_category("Professional Fees") == "soft"
        assert _classify_category("Closing Costs") == "financing"
        assert _classify_category("Interest Reserve") == "interest"
        assert _classify_category("Unknown Category") == "soft"  # default

    def test_empty_inputs_returns_empty(self):
        items = build_budget_detail({}, zfa=None, gsf=10_000, nsf=8_000)
        assert items == []
