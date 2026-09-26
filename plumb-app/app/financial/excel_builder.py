"""XlsxWriter-based Excel workbook generator.

Builds a 9-tab workbook from a FinancialModel with locked formatting and
unlocked assumption cells.
"""

from __future__ import annotations

import io
import logging
from typing import Any

import xlsxwriter
from xlsxwriter.format import Format
from xlsxwriter.worksheet import Worksheet

from app.financial.schemas import (
    BudgetLineItem,
    FinancialModel,
    ProFormaLine,
    SourcesUsesLine,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Format catalogue
# ---------------------------------------------------------------------------

class Formats:
    """Lazy-initialised format collection bound to a workbook."""

    def __init__(self, wb: xlsxwriter.Workbook) -> None:
        self.header: Format = wb.add_format({
            "bg_color": "#1A1A1A",
            "font_color": "#FFFFFF",
            "bold": True,
            "font_size": 11,
            "border": 1,
            "text_wrap": True,
            "align": "center",
            "valign": "vcenter",
            "locked": True,
        })
        self.header_left: Format = wb.add_format({
            "bg_color": "#1A1A1A",
            "font_color": "#FFFFFF",
            "bold": True,
            "font_size": 11,
            "border": 1,
            "text_wrap": True,
            "align": "left",
            "valign": "vcenter",
            "locked": True,
        })
        self.subheader: Format = wb.add_format({
            "bg_color": "#4A4A4A",
            "font_color": "#FFFFFF",
            "bold": True,
            "font_size": 10,
            "border": 1,
            "locked": True,
        })
        self.section_label: Format = wb.add_format({
            "bold": True,
            "font_size": 10,
            "bottom": 1,
            "locked": True,
        })
        self.label: Format = wb.add_format({
            "font_size": 10,
            "indent": 1,
            "locked": True,
        })
        self.label_bold: Format = wb.add_format({
            "font_size": 10,
            "bold": True,
            "top": 1,
            "bottom": 1,
            "locked": True,
        })
        self.currency: Format = wb.add_format({
            "num_format": "$#,##0",
            "font_size": 10,
            "locked": True,
        })
        self.currency_bold: Format = wb.add_format({
            "num_format": "$#,##0",
            "font_size": 10,
            "bold": True,
            "top": 1,
            "bottom": 1,
            "locked": True,
        })
        self.currency_sf: Format = wb.add_format({
            "num_format": "$#,##0.00",
            "font_size": 10,
            "locked": True,
        })
        self.currency_sf_bold: Format = wb.add_format({
            "num_format": "$#,##0.00",
            "font_size": 10,
            "bold": True,
            "top": 1,
            "bottom": 1,
            "locked": True,
        })
        self.percent: Format = wb.add_format({
            "num_format": "0.00%",
            "font_size": 10,
            "locked": True,
        })
        self.percent_bold: Format = wb.add_format({
            "num_format": "0.00%",
            "font_size": 10,
            "bold": True,
            "top": 1,
            "bottom": 1,
            "locked": True,
        })
        self.negative_currency: Format = wb.add_format({
            "num_format": '($#,##0)',
            "font_size": 10,
            "font_color": "#CC0000",
            "locked": True,
        })
        self.number: Format = wb.add_format({
            "num_format": "#,##0",
            "font_size": 10,
            "locked": True,
        })
        self.number_bold: Format = wb.add_format({
            "num_format": "#,##0",
            "font_size": 10,
            "bold": True,
            "top": 1,
            "bottom": 1,
            "locked": True,
        })
        self.number_2dp: Format = wb.add_format({
            "num_format": "#,##0.00",
            "font_size": 10,
            "locked": True,
        })
        self.text: Format = wb.add_format({
            "font_size": 10,
            "locked": True,
        })
        self.text_bold: Format = wb.add_format({
            "font_size": 10,
            "bold": True,
            "locked": True,
        })
        self.assumption_cell: Format = wb.add_format({
            "bg_color": "#FFFDE7",
            "font_size": 10,
            "border": 1,
            "locked": False,
        })
        self.assumption_pct: Format = wb.add_format({
            "bg_color": "#FFFDE7",
            "num_format": "0.00%",
            "font_size": 10,
            "border": 1,
            "locked": False,
        })
        self.title: Format = wb.add_format({
            "bold": True,
            "font_size": 14,
            "locked": True,
        })
        self.subtitle: Format = wb.add_format({
            "bold": True,
            "font_size": 12,
            "bottom": 2,
            "locked": True,
        })
        self.sensitivity_base: Format = wb.add_format({
            "bg_color": "#E8F5E9",
            "num_format": "$#,##0",
            "font_size": 9,
            "border": 1,
            "bold": True,
            "locked": True,
        })
        self.sensitivity_cell_fmt: Format = wb.add_format({
            "num_format": "$#,##0",
            "font_size": 9,
            "border": 1,
            "locked": True,
        })
        self.sensitivity_header: Format = wb.add_format({
            "bg_color": "#E0E0E0",
            "num_format": "0.00%",
            "font_size": 9,
            "border": 1,
            "bold": True,
            "align": "center",
            "locked": True,
        })


# ---------------------------------------------------------------------------
# Tab helpers
# ---------------------------------------------------------------------------

def _setup_tab(ws: Worksheet, title: str, fmt: Formats) -> None:
    """Common worksheet setup: landscape, fit to page, frozen panes."""
    ws.set_landscape()
    ws.fit_to_pages(1, 0)  # 1 page wide, unlimited height
    ws.set_paper(1)  # Letter
    ws.set_margins(left=0.5, right=0.5, top=0.75, bottom=0.75)
    ws.set_header(f"&L{title}&R&D")
    ws.freeze_panes(2, 0)
    ws.hide_gridlines(2)


def _write_su_line(
    ws: Worksheet,
    row: int,
    line: SourcesUsesLine,
    fmt: Formats,
    is_total: bool = False,
) -> int:
    """Write a Sources & Uses line and return the next row."""
    lf = fmt.label_bold if is_total else fmt.label
    cf = fmt.currency_bold if is_total else fmt.currency
    pf = fmt.percent_bold if is_total else fmt.percent
    sf = fmt.currency_sf_bold if is_total else fmt.currency_sf

    ws.write(row, 0, line.label, lf)
    ws.write_number(row, 1, line.total, cf)
    ws.write_number(row, 2, line.pct_total, pf)
    ws.write_number(row, 3, line.per_zfa or 0, sf)
    ws.write_number(row, 4, line.per_gsf or 0, sf)
    ws.write_number(row, 5, line.per_nra or 0, sf)
    ws.write_number(row, 6, line.prior_to_closing, cf)
    ws.write_number(row, 7, line.at_closing, cf)
    ws.write_number(row, 8, line.future_funding, cf)
    return row + 1


def _write_proforma_line(
    ws: Worksheet,
    row: int,
    line: ProFormaLine,
    fmt: Formats,
) -> int:
    """Write a pro forma line and return the next row."""
    is_sub = line.is_subtotal
    lf = fmt.label_bold if is_sub else fmt.label
    cf = fmt.currency_bold if is_sub else fmt.currency
    sf = fmt.currency_sf_bold if is_sub else fmt.currency_sf
    pf = fmt.percent_bold if is_sub else fmt.percent

    if line.total < 0 and not is_sub:
        cf = fmt.negative_currency

    ws.write(row, 0, line.label, lf)
    ws.write_number(row, 1, line.per_sf or 0, sf)
    ws.write_number(row, 2, line.per_unit_yr or 0, cf)
    ws.write_number(row, 3, line.pct_of_egi or 0, pf)
    ws.write_number(row, 4, line.total, cf)
    return row + 1


# ---------------------------------------------------------------------------
# Tab builders
# ---------------------------------------------------------------------------

def _tab_summary(wb: xlsxwriter.Workbook, model: FinancialModel, deal_name: str, fmt: Formats) -> None:
    ws = wb.add_worksheet("Summary")
    _setup_tab(ws, "Summary", fmt)
    ws.set_column(0, 0, 35)
    ws.set_column(1, 1, 22)

    row = 0
    ws.write(row, 0, deal_name, fmt.title)
    row += 1
    ws.write(row, 0, f"Calculated: {model.calculated_at[:10]}", fmt.text)
    row += 2

    ws.write(row, 0, "Key Metrics", fmt.subtitle)
    row += 1

    metrics: list[tuple[str, Any, Format]] = [
        ("Total Development Cost", model.total_development_cost, fmt.currency),
        ("Construction Loan", model.loan_amount, fmt.currency),
        ("Sponsor Equity", model.equity, fmt.currency),
        ("Loan-to-Cost (LTC)", model.ltc, fmt.percent),
        ("Total Units", model.total_units, fmt.number),
        ("Gross SF", model.total_gsf, fmt.number),
        ("Net Rentable Area", model.nra, fmt.number),
        ("", "", fmt.text),
        ("Effective Gross Income", model.proforma.egi.total, fmt.currency),
        ("Total Expenses", model.proforma.total_expenses.total, fmt.currency),
        ("Net Operating Income", model.proforma.noi.total, fmt.currency),
        ("", "", fmt.text),
        ("Cap Rate", model.assumptions.cap_rate, fmt.percent),
        ("Yield on Cost", model.valuation.yield_on_cost, fmt.percent),
        ("Estimated Value (A)", model.valuation.estimated_value_a, fmt.currency),
        ("Abatement Value (B)", model.valuation.abatement_value_b, fmt.currency),
        ("Total Asset Value", model.valuation.total_asset_value, fmt.currency),
        ("", "", fmt.text),
        ("Stabilized LTV", model.valuation.stabilized_ltv, fmt.percent),
        ("Debt Yield", model.valuation.debt_yield, fmt.percent),
        ("Value per Unit", model.valuation.value_per_unit, fmt.currency),
        ("Value per GSF", model.valuation.value_per_gsf, fmt.currency_sf),
        ("Debt per Unit", model.valuation.debt_per_unit, fmt.currency),
        ("Debt per GSF", model.valuation.debt_per_gsf, fmt.currency_sf),
    ]

    if model.zfa:
        metrics.insert(6, ("Zoning Floor Area", model.zfa, fmt.number))

    for label, value, cell_fmt in metrics:
        ws.write(row, 0, label, fmt.label_bold if label else fmt.text)
        if isinstance(value, (int, float)):
            ws.write_number(row, 1, value, cell_fmt)
        else:
            ws.write(row, 1, value, fmt.text)
        row += 1

    # Warnings
    if model.errors:
        row += 1
        ws.write(row, 0, "Warnings", fmt.subtitle)
        row += 1
        for err in model.errors:
            ws.write(row, 0, err, fmt.text)
            row += 1


def _tab_assumptions(wb: xlsxwriter.Workbook, model: FinancialModel, fmt: Formats) -> None:
    ws = wb.add_worksheet("Assumptions")
    _setup_tab(ws, "Assumptions", fmt)
    ws.set_column(0, 0, 35)
    ws.set_column(1, 1, 18)

    row = 0
    ws.write(row, 0, "Underwriting Assumptions", fmt.subtitle)
    row += 1

    assumptions_data: list[tuple[str, str, float, Format]] = [
        ("Cap Rate", "cap_rate", model.assumptions.cap_rate, fmt.assumption_pct),
        ("Vacancy — Free Market", "vacancy_fm", model.assumptions.vacancy_fm, fmt.assumption_pct),
        ("Vacancy — Affordable", "vacancy_affordable", model.assumptions.vacancy_affordable, fmt.assumption_pct),
        ("Vacancy — Retail", "vacancy_retail", model.assumptions.vacancy_retail, fmt.assumption_pct),
        ("Management Fee %", "mgmt_fee_pct", model.assumptions.mgmt_fee_pct, fmt.assumption_pct),
        ("Assessment Growth Rate", "assessment_growth", model.assumptions.assessment_growth, fmt.assumption_pct),
        ("Tax Rate Growth", "tax_rate_growth", model.assumptions.tax_rate_growth, fmt.assumption_pct),
        ("Discount Rate", "discount_rate", model.assumptions.discount_rate, fmt.assumption_pct),
    ]

    for label, named_range, value, cell_fmt in assumptions_data:
        ws.write(row, 0, label, fmt.label)
        ws.write_number(row, 1, value, cell_fmt)
        # Create named range for this cell
        try:
            wb.define_name(named_range, f"=Assumptions!$B${row + 1}")
        except Exception:
            pass  # xlsxwriter may reject duplicate names
        row += 1


def _tab_sources_uses(wb: xlsxwriter.Workbook, model: FinancialModel, fmt: Formats) -> None:
    ws = wb.add_worksheet("Sources & Uses")
    _setup_tab(ws, "Sources & Uses", fmt)

    col_widths = [30, 18, 10, 14, 14, 14, 18, 18, 18]
    for i, w in enumerate(col_widths):
        ws.set_column(i, i, w)

    row = 0
    headers = ["", "Total", "% Total", "$/ZFA", "$/GSF", "$/NRA",
               "Prior to Closing", "At Closing", "Future Funding"]
    for c, h in enumerate(headers):
        ws.write(row, c, h, fmt.header if c > 0 else fmt.header_left)
    row += 1

    # Sources
    ws.write(row, 0, "SOURCES", fmt.subheader)
    for c in range(1, len(headers)):
        ws.write(row, c, "", fmt.subheader)
    row += 1
    for line in model.sources_uses.sources:
        row = _write_su_line(ws, row, line, fmt)
    row = _write_su_line(ws, row, model.sources_uses.total_sources, fmt, is_total=True)

    row += 1

    # Uses
    ws.write(row, 0, "USES", fmt.subheader)
    for c in range(1, len(headers)):
        ws.write(row, c, "", fmt.subheader)
    row += 1
    for line in model.sources_uses.uses:
        row = _write_su_line(ws, row, line, fmt)
    row = _write_su_line(ws, row, model.sources_uses.total_uses, fmt, is_total=True)


def _tab_budget(wb: xlsxwriter.Workbook, model: FinancialModel, fmt: Formats) -> None:
    ws = wb.add_worksheet("Construction Budget")
    _setup_tab(ws, "Construction Budget", fmt)

    col_widths = [35, 18, 10, 14, 14, 14, 18, 18, 18, 10]
    for i, w in enumerate(col_widths):
        ws.set_column(i, i, w)

    row = 0
    headers = ["Item", "Total Cost", "% TDC", "$/ZFA", "$/GSF", "$/NSF",
               "Spent to Date", "At Closing", "Future Funding", "Rate %"]
    for c, h in enumerate(headers):
        ws.write(row, c, h, fmt.header if c > 0 else fmt.header_left)
    row += 1

    # Group by category
    categories_order = ["acquisition", "hard", "soft", "financing", "interest"]
    cat_labels = {
        "acquisition": "ACQUISITION",
        "hard": "HARD COSTS",
        "soft": "SOFT COSTS",
        "financing": "FINANCING COSTS",
        "interest": "INTEREST / CARRY",
    }

    grouped: dict[str, list[BudgetLineItem]] = {}
    for item in model.budget_detail:
        grouped.setdefault(item.category, []).append(item)

    grand_total = sum(i.total_cost for i in model.budget_detail)

    for cat in categories_order:
        items = grouped.get(cat, [])
        if not items:
            continue

        ws.write(row, 0, cat_labels.get(cat, cat.upper()), fmt.subheader)
        for c in range(1, len(headers)):
            ws.write(row, c, "", fmt.subheader)
        row += 1

        cat_total = 0.0
        for item in items:
            ws.write(row, 0, item.label, fmt.label)
            ws.write_number(row, 1, item.total_cost, fmt.currency)
            ws.write_number(row, 2, item.pct_total, fmt.percent)
            ws.write_number(row, 3, item.per_zfa or 0, fmt.currency_sf)
            ws.write_number(row, 4, item.per_gsf or 0, fmt.currency_sf)
            ws.write_number(row, 5, item.per_nsf or 0, fmt.currency_sf)
            ws.write_number(row, 6, item.spent_to_date, fmt.currency)
            ws.write_number(row, 7, item.at_closing, fmt.currency)
            ws.write_number(row, 8, item.future_funding, fmt.currency)
            if item.rate_pct is not None:
                ws.write_number(row, 9, item.rate_pct / 100.0, fmt.percent)
            row += 1
            cat_total += item.total_cost

        # Category subtotal
        ws.write(row, 0, f"Subtotal {cat_labels.get(cat, cat)}", fmt.label_bold)
        ws.write_number(row, 1, cat_total, fmt.currency_bold)
        ws.write_number(row, 2, cat_total / grand_total if grand_total else 0, fmt.percent_bold)
        row += 1

    # Grand total
    row += 1
    ws.write(row, 0, "TOTAL DEVELOPMENT COST", fmt.label_bold)
    ws.write_number(row, 1, grand_total, fmt.currency_bold)
    ws.write_number(row, 2, 1.0, fmt.percent_bold)


def _tab_unit_mix(wb: xlsxwriter.Workbook, model: FinancialModel, fmt: Formats) -> None:
    ws = wb.add_worksheet("Unit Mix")
    _setup_tab(ws, "Unit Mix", fmt)

    col_widths = [18, 8, 8, 8, 12, 16, 14]
    for i, w in enumerate(col_widths):
        ws.set_column(i, i, w)

    row = 0
    headers = ["Tier", "Beds", "Baths", "Units", "SF/Unit", "Avg Mo. Rent", "Rent/SF"]
    for c, h in enumerate(headers):
        ws.write(row, c, h, fmt.header)
    row += 1

    tier_sections = [
        ("FREE MARKET", model.unit_mix.fm),
        ("421-A AFFORDABLE", model.unit_mix.affordable_421a),
        ("MIH", model.unit_mix.mih),
        ("COMMERCIAL", model.unit_mix.commercial),
    ]

    for section_label, rows_data in tier_sections:
        if not rows_data:
            continue
        ws.write(row, 0, section_label, fmt.subheader)
        for c in range(1, len(headers)):
            ws.write(row, c, "", fmt.subheader)
        row += 1

        tier_units = 0
        for umr in rows_data:
            ws.write(row, 0, umr.tier, fmt.label)
            if umr.beds is not None:
                ws.write_number(row, 1, umr.beds, fmt.number)
            if umr.baths is not None:
                ws.write_number(row, 2, umr.baths, fmt.number)
            ws.write_number(row, 3, umr.units, fmt.number)
            ws.write_number(row, 4, umr.sf_per_unit, fmt.number)
            ws.write_number(row, 5, umr.avg_monthly_rent, fmt.currency)
            ws.write_number(row, 6, umr.rent_per_sf, fmt.currency_sf)
            row += 1
            tier_units += umr.units

        # Tier subtotal
        ws.write(row, 0, f"Subtotal", fmt.label_bold)
        ws.write_number(row, 3, tier_units, fmt.number_bold)
        row += 1

    # Grand total
    row += 1
    ws.write(row, 0, "TOTAL", fmt.subheader)
    for c in range(1, len(headers)):
        ws.write(row, c, "", fmt.subheader)
    row += 1
    for tr in model.unit_mix.total:
        beds_label = f"{tr.beds}BR" if tr.beds is not None else "N/A"
        ws.write(row, 0, beds_label, fmt.label)
        if tr.beds is not None:
            ws.write_number(row, 1, tr.beds, fmt.number)
        ws.write_number(row, 3, tr.units, fmt.number)
        ws.write_number(row, 4, tr.sf_per_unit, fmt.number)
        ws.write_number(row, 5, tr.avg_monthly_rent, fmt.currency)
        ws.write_number(row, 6, tr.rent_per_sf, fmt.currency_sf)
        row += 1

    ws.write(row, 0, "Grand Total", fmt.label_bold)
    ws.write_number(row, 3, model.total_units, fmt.number_bold)


def _tab_proforma(wb: xlsxwriter.Workbook, model: FinancialModel, fmt: Formats) -> None:
    ws = wb.add_worksheet("Rental Pro Forma")
    _setup_tab(ws, "Rental Pro Forma", fmt)

    col_widths = [35, 14, 16, 12, 18]
    for i, w in enumerate(col_widths):
        ws.set_column(i, i, w)

    row = 0
    headers = ["", "$/SF", "$/Unit/Yr", "% of EGI", "Total"]
    for c, h in enumerate(headers):
        ws.write(row, c, h, fmt.header if c > 0 else fmt.header_left)
    row += 1

    # Income
    ws.write(row, 0, "INCOME", fmt.subheader)
    for c in range(1, len(headers)):
        ws.write(row, c, "", fmt.subheader)
    row += 1

    for line in model.proforma.income_lines:
        row = _write_proforma_line(ws, row, line, fmt)

    # EGI
    row = _write_proforma_line(ws, row, model.proforma.egi, fmt)
    row += 1

    # Expenses
    ws.write(row, 0, "EXPENSES", fmt.subheader)
    for c in range(1, len(headers)):
        ws.write(row, c, "", fmt.subheader)
    row += 1

    for line in model.proforma.expense_lines:
        row = _write_proforma_line(ws, row, line, fmt)

    row = _write_proforma_line(ws, row, model.proforma.total_expenses, fmt)
    row += 1

    # NOI
    row = _write_proforma_line(ws, row, model.proforma.noi, fmt)


def _tab_valuation(wb: xlsxwriter.Workbook, model: FinancialModel, fmt: Formats) -> None:
    ws = wb.add_worksheet("Valuation")
    _setup_tab(ws, "Valuation", fmt)
    ws.set_column(0, 0, 35)
    ws.set_column(1, 1, 22)

    row = 0
    ws.write(row, 0, "Stabilized Valuation", fmt.subtitle)
    row += 1

    v = model.valuation
    val_lines: list[tuple[str, float, Format]] = [
        ("Net Operating Income", v.actual_noi, fmt.currency),
        ("Cap Rate", v.cap_rate, fmt.percent),
        ("Yield on Cost", v.yield_on_cost, fmt.percent),
        ("", 0, fmt.text),
        ("Estimated Value — Component A", v.estimated_value_a, fmt.currency),
        ("421(a) Abatement Value — Component B", v.abatement_value_b, fmt.currency),
        ("Total Asset Value (A + B)", v.total_asset_value, fmt.currency),
        ("", 0, fmt.text),
        ("Value per Unit", v.value_per_unit, fmt.currency),
        ("Value per GSF", v.value_per_gsf, fmt.currency_sf),
        ("", 0, fmt.text),
        ("Total Project Capitalization", v.total_project_cap, fmt.currency),
        ("Construction Loan", v.construction_loan, fmt.currency),
        ("Stabilized LTV", v.stabilized_ltv, fmt.percent),
        ("Debt Yield", v.debt_yield, fmt.percent),
        ("Debt per Unit", v.debt_per_unit, fmt.currency),
        ("Debt per GSF", v.debt_per_gsf, fmt.currency_sf),
    ]

    for label, value, cell_fmt in val_lines:
        if label:
            ws.write(row, 0, label, fmt.label)
            ws.write_number(row, 1, value, cell_fmt)
        row += 1


def _tab_abatement(wb: xlsxwriter.Workbook, model: FinancialModel, fmt: Formats) -> None:
    if model.abatement is None:
        return

    ws = wb.add_worksheet("421(a) Schedule")
    _setup_tab(ws, "421(a) Abatement Schedule", fmt)

    col_widths = [6, 12, 16, 16, 16, 10, 16, 16, 10, 16, 16, 16]
    for i, w in enumerate(col_widths):
        ws.set_column(i, i, w)

    ab = model.abatement

    # Header info
    row = 0
    ws.write(row, 0, f"421(a) Option {ab.program_option}", fmt.subtitle)
    row += 1
    info_lines = [
        ("Borough", ab.borough or "N/A"),
        ("Block / Lot", ab.block_lot or "N/A"),
        ("AV Prior to Construction", None),
        ("Assessment Growth Rate", None),
        ("Tax Rate Growth", None),
        ("Discount Rate", None),
        ("NPV of Tax Savings", None),
    ]
    for label, val in info_lines:
        ws.write(row, 0, label, fmt.label)
        if val is not None:
            ws.write(row, 1, val, fmt.text)
        row += 1
    # Write numeric header values
    info_row = 3  # row for AV Prior
    ws.write_number(info_row, 1, ab.av_prior_to_construction, fmt.currency)
    ws.write_number(info_row + 1, 1, ab.assessment_growth_rate, fmt.percent)
    ws.write_number(info_row + 2, 1, ab.tax_rate_growth, fmt.percent)
    ws.write_number(info_row + 3, 1, ab.discount_rate, fmt.percent)
    ws.write_number(info_row + 4, 1, ab.npv_of_tax_savings, fmt.currency)

    row += 1

    # Column headers
    col_headers = [
        "Year", "Benefit Year", "Taxable AV", "AV Prior", "Increase in AV",
        "% Exempt", "Exemption", "Final Taxable AV", "Tax Rate",
        "Unabated RET", "Abated RET", "RET Savings",
    ]
    for c, h in enumerate(col_headers):
        ws.write(row, c, h, fmt.header)
    row += 1

    for yr in ab.years:
        ws.write_number(row, 0, yr.year, fmt.number)
        ws.write(row, 1, yr.benefit_year_start, fmt.text)
        ws.write_number(row, 2, yr.taxable_assessment, fmt.currency)
        ws.write_number(row, 3, yr.av_prior, fmt.currency)
        ws.write_number(row, 4, yr.increase_in_av, fmt.currency)
        ws.write_number(row, 5, yr.pct_exempt, fmt.percent)
        ws.write_number(row, 6, yr.exemption_amount, fmt.currency)
        ws.write_number(row, 7, yr.final_taxable_assessment, fmt.currency)
        ws.write_number(row, 8, yr.tax_rate, fmt.percent)
        ws.write_number(row, 9, yr.unabated_ret, fmt.currency)
        ws.write_number(row, 10, yr.abated_ret, fmt.currency)
        ws.write_number(row, 11, yr.ret_savings, fmt.currency)
        row += 1


def _tab_sensitivity(wb: xlsxwriter.Workbook, model: FinancialModel, fmt: Formats) -> None:
    ws = wb.add_worksheet("Sensitivity")
    _setup_tab(ws, "Sensitivity Analysis", fmt)

    s = model.sensitivity
    n_cols = len(s.rent_growth_rates)
    n_rows = len(s.cap_rates)

    # Set column widths
    ws.set_column(0, 0, 14)
    for c in range(1, n_cols + 1):
        ws.set_column(c, c, 16)

    row = 0
    ws.write(row, 0, "Asset Value Sensitivity", fmt.subtitle)
    row += 1
    ws.write(row, 0, "Cap Rate \\ Rent Growth", fmt.header)
    for c, rg in enumerate(s.rent_growth_rates):
        ws.write_number(row, c + 1, rg, fmt.sensitivity_header)
    row += 1

    for r_idx, cap in enumerate(s.cap_rates):
        ws.write_number(row, 0, cap, fmt.sensitivity_header)
        for c_idx in range(n_cols):
            cell = s.cells[r_idx][c_idx]
            is_base = (r_idx == s.base_row and c_idx == s.base_col)
            cell_fmt = fmt.sensitivity_base if is_base else fmt.sensitivity_cell_fmt
            ws.write_number(row, c_idx + 1, cell.asset_value, cell_fmt)
        row += 1

    # LTV section
    row += 2
    ws.write(row, 0, "LTV Sensitivity", fmt.subtitle)
    row += 1
    ws.write(row, 0, "Cap Rate \\ Rent Growth", fmt.header)
    for c, rg in enumerate(s.rent_growth_rates):
        ws.write_number(row, c + 1, rg, fmt.sensitivity_header)
    row += 1

    ltv_fmt = wb.add_format({
        "num_format": "0.0%",
        "font_size": 9,
        "border": 1,
        "locked": True,
    })
    ltv_base_fmt = wb.add_format({
        "num_format": "0.0%",
        "font_size": 9,
        "border": 1,
        "bold": True,
        "bg_color": "#E8F5E9",
        "locked": True,
    })

    for r_idx, cap in enumerate(s.cap_rates):
        ws.write_number(row, 0, cap, fmt.sensitivity_header)
        for c_idx in range(n_cols):
            cell = s.cells[r_idx][c_idx]
            is_base = (r_idx == s.base_row and c_idx == s.base_col)
            ws.write_number(row, c_idx + 1, cell.ltv, ltv_base_fmt if is_base else ltv_fmt)
        row += 1

    # Debt Yield section
    row += 2
    ws.write(row, 0, "Debt Yield Sensitivity", fmt.subtitle)
    row += 1
    ws.write(row, 0, "Cap Rate \\ Rent Growth", fmt.header)
    for c, rg in enumerate(s.rent_growth_rates):
        ws.write_number(row, c + 1, rg, fmt.sensitivity_header)
    row += 1

    dy_fmt = wb.add_format({
        "num_format": "0.00%",
        "font_size": 9,
        "border": 1,
        "locked": True,
    })
    dy_base_fmt = wb.add_format({
        "num_format": "0.00%",
        "font_size": 9,
        "border": 1,
        "bold": True,
        "bg_color": "#E8F5E9",
        "locked": True,
    })

    for r_idx, cap in enumerate(s.cap_rates):
        ws.write_number(row, 0, cap, fmt.sensitivity_header)
        for c_idx in range(n_cols):
            cell = s.cells[r_idx][c_idx]
            is_base = (r_idx == s.base_row and c_idx == s.base_col)
            ws.write_number(row, c_idx + 1, cell.debt_yield, dy_base_fmt if is_base else dy_fmt)
        row += 1


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_excel(model: FinancialModel, deal_name: str) -> bytes:
    """Build a complete .xlsx workbook from a FinancialModel.

    Returns the raw bytes of the Excel file.
    """
    output = io.BytesIO()
    wb = xlsxwriter.Workbook(output, {"in_memory": True})

    fmt = Formats(wb)

    # Build all 9 tabs
    _tab_summary(wb, model, deal_name, fmt)
    _tab_assumptions(wb, model, fmt)
    _tab_sources_uses(wb, model, fmt)
    _tab_budget(wb, model, fmt)
    _tab_unit_mix(wb, model, fmt)
    _tab_proforma(wb, model, fmt)
    _tab_valuation(wb, model, fmt)
    _tab_abatement(wb, model, fmt)
    _tab_sensitivity(wb, model, fmt)

    # Protect the workbook — assumption cells are already unlocked
    for ws in wb.worksheets():
        ws.protect()

    wb.close()
    output.seek(0)
    return output.read()
