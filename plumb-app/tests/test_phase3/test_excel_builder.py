"""Tests for Excel workbook generation."""

import io

import pytest

from app.financial.excel_builder import build_excel
from app.financial.schemas import (
    AbatementSchedule,
    AbatementYear,
    BudgetLineItem,
    FinancialModel,
    ModelAssumptions,
    ProFormaLine,
    RentalProForma,
    SensitivityCell,
    SensitivityMatrix,
    SourcesUses,
    SourcesUsesLine,
    UnitMixRow,
    UnitMixTiered,
    ValuationSummary,
)


def _su_line(label: str, total: float) -> SourcesUsesLine:
    return SourcesUsesLine(label=label, total=total, pct_total=0.5, per_gsf=10.0)


def _pf_line(label: str, total: float, is_subtotal: bool = False) -> ProFormaLine:
    return ProFormaLine(label=label, total=total, per_sf=5.0, per_unit_yr=7000, pct_of_egi=0.5, is_subtotal=is_subtotal)


@pytest.fixture
def sample_financial_model() -> FinancialModel:
    """Minimal but complete FinancialModel for Excel generation."""
    assumptions = ModelAssumptions(cap_rate=0.05)

    sources_uses = SourcesUses(
        sources=[_su_line("Construction Loan", 30_000_000), _su_line("Equity", 14_000_000)],
        uses=[_su_line("Hard Costs", 28_000_000), _su_line("Soft Costs", 16_000_000)],
        total_sources=_su_line("Total Sources", 44_000_000),
        total_uses=_su_line("Total Uses", 44_000_000),
    )

    budget_detail = [
        BudgetLineItem(category="hard", label="Construction", total_cost=28_000_000, pct_total=0.64),
        BudgetLineItem(category="soft", label="Architecture", total_cost=3_000_000, pct_total=0.07),
        BudgetLineItem(category="financing", label="Closing Costs", total_cost=1_000_000, pct_total=0.02),
    ]

    unit_mix = UnitMixTiered(
        fm=[UnitMixRow(tier="FM", beds=1, units=20, sf_per_unit=700, avg_monthly_rent=3500, rent_per_sf=5.0)],
        affordable_421a=[UnitMixRow(tier="421A", beds=1, units=15, sf_per_unit=600, avg_monthly_rent=1500, rent_per_sf=2.5)],
        total=[UnitMixRow(tier="Total", beds=1, units=35, sf_per_unit=657, avg_monthly_rent=2643, rent_per_sf=4.02)],
    )

    proforma = RentalProForma(
        income_lines=[
            _pf_line("Gross Residential Income (FM)", 840_000),
            _pf_line("Vacancy (FM)", -42_000),
            _pf_line("Gross Residential Income (421-A)", 270_000),
        ],
        egi=_pf_line("EGI", 1_068_000, is_subtotal=True),
        expense_lines=[
            _pf_line("Real Estate Taxes", 300_000),
            _pf_line("Management Fee", 26_700),
        ],
        total_expenses=_pf_line("Total Expenses", 326_700, is_subtotal=True),
        noi=_pf_line("NOI", 741_300, is_subtotal=True),
    )

    valuation = ValuationSummary(
        actual_noi=741_300,
        yield_on_cost=0.0168,
        full_tax_noi=741_300,
        cap_rate=0.05,
        estimated_value_a=14_826_000,
        abatement_value_b=2_000_000,
        total_asset_value=16_826_000,
        value_per_unit=480_743,
        value_per_gsf=258.86,
        total_project_cap=44_000_000,
        construction_loan=30_000_000,
        stabilized_ltv=0.604,
        debt_yield=0.0371,
        debt_per_unit=857_143,
        debt_per_gsf=461.54,
    )

    abatement = AbatementSchedule(
        program_option="C",
        borough="Brooklyn",
        block_lot="03784/0001",
        av_prior_to_construction=2_500_000,
        assessment_growth_rate=0.02,
        tax_rate_growth=0.005,
        discount_rate=0.05,
        npv_of_tax_savings=2_000_000,
        years=[
            AbatementYear(
                year=i + 1,
                benefit_year_start=str(2026 + i),
                taxable_assessment=2_500_000 * (1.02 ** i),
                av_prior=2_500_000,
                increase_in_av=2_500_000 * (1.02 ** i) - 2_500_000,
                pct_exempt=1.0 if i < 25 else max(0, 1.0 - 0.1 * (i - 24)),
                exemption_amount=0,
                final_taxable_assessment=2_500_000,
                tax_rate=0.10694,
                unabated_ret=267_350,
                abated_ret=267_350,
                ret_savings=0,
            )
            for i in range(35)
        ],
    )

    # 3x3 sensitivity for simplicity
    sensitivity = SensitivityMatrix(
        cap_rates=[0.0425, 0.045, 0.0475, 0.05, 0.0525, 0.055, 0.0575],
        rent_growth_rates=[-0.015, -0.01, -0.005, 0.0, 0.005, 0.01, 0.015],
        cells=[
            [SensitivityCell(asset_value=15_000_000, ltv=0.6, debt_yield=0.04) for _ in range(7)]
            for _ in range(7)
        ],
        base_row=3,
        base_col=3,
    )

    return FinancialModel(
        deal_id="test-deal-id",
        assumptions=assumptions,
        sources_uses=sources_uses,
        budget_detail=budget_detail,
        unit_mix=unit_mix,
        proforma=proforma,
        valuation=valuation,
        abatement=abatement,
        sensitivity=sensitivity,
        ltc=0.682,
        total_development_cost=44_000_000,
        loan_amount=30_000_000,
        equity=14_000_000,
        total_units=35,
        total_gsf=65_000,
        zfa=58_000,
        nra=52_000,
        calculated_at="2026-04-07T12:00:00Z",
    )


class TestExcelBuilder:
    def test_returns_bytes(self, sample_financial_model):
        result = build_excel(sample_financial_model, "Test Deal")
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_valid_xlsx(self, sample_financial_model):
        """Output should be a valid .xlsx file readable by openpyxl."""
        import openpyxl

        result = build_excel(sample_financial_model, "Test Deal")
        wb = openpyxl.load_workbook(io.BytesIO(result))
        assert wb is not None
        wb.close()

    def test_has_9_tabs(self, sample_financial_model):
        import openpyxl

        result = build_excel(sample_financial_model, "Test Deal")
        wb = openpyxl.load_workbook(io.BytesIO(result))
        assert len(wb.sheetnames) == 9
        expected = [
            "Summary", "Assumptions", "Sources & Uses", "Construction Budget",
            "Unit Mix", "Rental Pro Forma", "Valuation", "421(a) Schedule", "Sensitivity",
        ]
        assert wb.sheetnames == expected
        wb.close()

    def test_summary_has_deal_name(self, sample_financial_model):
        import openpyxl

        result = build_excel(sample_financial_model, "Harbor Point")
        wb = openpyxl.load_workbook(io.BytesIO(result))
        ws = wb["Summary"]
        assert ws.cell(1, 1).value == "Harbor Point"
        wb.close()

    def test_assumptions_tab_has_values(self, sample_financial_model):
        import openpyxl

        result = build_excel(sample_financial_model, "Test Deal")
        wb = openpyxl.load_workbook(io.BytesIO(result))
        ws = wb["Assumptions"]
        # Row 2 should have Cap Rate label and value
        assert ws.cell(2, 1).value == "Cap Rate"
        assert ws.cell(2, 2).value == pytest.approx(0.05)
        wb.close()

    def test_no_abatement_tab_when_none(self, sample_financial_model):
        """When abatement is None, the 421(a) tab should be skipped."""
        import openpyxl

        sample_financial_model.abatement = None
        result = build_excel(sample_financial_model, "Test Deal")
        wb = openpyxl.load_workbook(io.BytesIO(result))
        assert "421(a) Schedule" not in wb.sheetnames
        assert len(wb.sheetnames) == 8
        wb.close()

    def test_worksheets_are_protected(self, sample_financial_model):
        import openpyxl

        result = build_excel(sample_financial_model, "Test Deal")
        wb = openpyxl.load_workbook(io.BytesIO(result))
        for ws in wb.worksheets:
            assert ws.protection.sheet is True
        wb.close()

    def test_output_size_reasonable(self, sample_financial_model):
        result = build_excel(sample_financial_model, "Test Deal")
        # Should be between 10KB and 5MB
        assert 10_000 < len(result) < 5_000_000
