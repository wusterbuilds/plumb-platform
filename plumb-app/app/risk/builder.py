"""Risk Assessment Report builder.

Assembles findings data, renders each page as HTML via Jinja2, converts to
portrait PDF via Playwright, and concatenates into a single document.
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

from app.om.builder import _file_to_data_uri, concatenate_pdfs
from app.om.page_registry import (
    format_currency,
    format_currency_sf,
    format_number,
    format_pct,
    format_pct_raw,
)
from app.om.renderer import render_pages_to_pdf_sync
from app.risk.schemas import RiskContext, RiskFinding

logger = logging.getLogger(__name__)

# Portrait dimensions
RISK_PAGE_WIDTH = "8.5in"
RISK_PAGE_HEIGHT = "11in"

# Max findings per page before overflow
MAX_FINDINGS_PER_PAGE = 5


def build_risk_report(
    ctx: RiskContext,
    logo_path: str | None = None,
) -> tuple[bytes, int, list[str]]:
    """Build the complete Risk Assessment Report PDF.

    Returns:
        Tuple of (pdf_bytes, page_count, html_pages_for_preview).
    """
    # 1. Setup Jinja2
    template_dir = Path(__file__).parents[1] / "om" / "templates"
    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=False,
    )
    env.filters["currency"] = format_currency
    env.filters["currency_sf"] = format_currency_sf
    env.filters["pct"] = format_pct
    env.filters["number"] = format_number
    env.filters["pct_raw"] = format_pct_raw

    # 2. Resolve logo
    if not logo_path:
        svg_path = Path(__file__).parents[1] / "plumb-logo.svg"
        png_path = Path(__file__).parents[1] / "plumb-logo.png"
        if svg_path.exists():
            logo_path = str(svg_path)
        elif png_path.exists():
            logo_path = str(png_path)
        else:
            logo_path = str(svg_path)
    logo_data_uri = _file_to_data_uri(logo_path)

    # 3. Build page manifest
    manifest = _build_risk_page_manifest(ctx)

    # 4. Render pages
    styles_css_path = template_dir / "styles.css"
    styles_css_content = styles_css_path.read_text(encoding="utf-8")
    styles_css_content = "\n".join(
        line for line in styles_css_content.splitlines()
        if not line.strip().startswith("@import")
    )

    html_pages: list[str] = []

    with tempfile.TemporaryDirectory() as tmpdir:
        html_paths: list[Path] = []

        for i, page_spec in enumerate(manifest):
            page_ctx = page_spec["ctx"]
            page_ctx["logo_path"] = logo_data_uri
            page_ctx["page_number"] = i + 1

            template = env.get_template(page_spec["template"])
            html = template.render(ctx=page_ctx, styles_css=styles_css_content)
            html_pages.append(html)

            html_path = Path(tmpdir) / f"risk_page_{i:03d}.html"
            html_path.write_text(html, encoding="utf-8")
            html_paths.append(html_path)

        # 5. Batch render with portrait dimensions
        pdf_page_bytes = render_pages_to_pdf_sync(
            html_paths,
            width=RISK_PAGE_WIDTH,
            height=RISK_PAGE_HEIGHT,
        )

    # 6. Concatenate
    final_pdf = concatenate_pdfs(pdf_page_bytes)
    return final_pdf, len(pdf_page_bytes), html_pages


def _build_risk_page_manifest(ctx: RiskContext) -> list[dict]:
    """Build the ordered list of pages for the risk report."""
    pages: list[dict] = []
    base = {
        "property_name": ctx.property_name,
        "property_address": ctx.property_address,
        "deal_type_label": ctx.deal_type_label,
        "overall_risk_rating": ctx.overall_risk_rating,
    }

    def _add(template: str, page_ctx: dict) -> None:
        merged = {**base, **page_ctx}
        pages.append({"template": f"pages/{template}", "ctx": merged})

    # --- Cover ---
    _add("risk_cover.html", {})

    # --- Executive Summary ---
    severity_counts = _count_severities(ctx.findings)
    _add("risk_summary.html", {
        "risk_summary": ctx.risk_summary,
        "key_metrics": _build_key_metrics(ctx),
        "critical_count": severity_counts.get("critical", 0),
        "warning_count": severity_counts.get("warning", 0),
        "positive_count": severity_counts.get("positive", 0),
        "info_count": severity_counts.get("info", 0),
        "screening_recommendation": ctx.screening_recommendation,
    })

    # --- Findings by category (client-facing, sourced from deal facts) ---
    category_config = [
        ("capital_stack", "Capital Stack & Leverage", "Loan sizing, equity contribution, and contingency relative to peer construction deals."),
        ("construction", "Construction Cost & Feasibility", "Hard/soft cost reasonableness versus NYC condo comps and GC track record."),
        ("zoning", "Zoning & Entitlements", "As-of-right versus discretionary approvals, MIH affordability obligations, and BSA/ULURP exposure."),
        ("sponsor", "Sponsor & Guarantor", "Experience, balance-sheet capacity, and prior performance on comparable projects."),
        ("market", "Market & Demand Validation", "Absorption, pricing, and competitive supply against current NYC condo data."),
        ("title", "Title, Ownership & Liens", "ACRIS chain of title, outstanding liens, and mortgage encumbrances."),
        ("environmental", "Environmental", "Phase I ESA status, known contamination, and remediation exposure."),
        ("underwriting", "Credit Underwriting", "Underwriting assumptions, debt service coverage, and financial model review."),
    ]

    for cat_key, cat_title, cat_subtitle in category_config:
        cat_findings = [f for f in ctx.findings if f.category == cat_key]
        if not cat_findings:
            continue

        # Paginate findings
        for page_idx in range(0, len(cat_findings), MAX_FINDINGS_PER_PAGE):
            chunk = cat_findings[page_idx : page_idx + MAX_FINDINGS_PER_PAGE]
            title = cat_title
            if page_idx > 0:
                title = f"{cat_title} (continued)"
            _add("risk_findings.html", {
                "section_title": title,
                "section_subtitle": cat_subtitle if page_idx == 0 else None,
                "narrative": None,
                "findings": [f.model_dump() for f in chunk],
            })

    # --- Risk Matrix (all findings in one table, sorted by severity) ---
    severity_order = {"critical": 0, "warning": 1, "info": 2, "positive": 3}
    sorted_findings = sorted(
        ctx.findings,
        key=lambda f: severity_order.get(f.severity, 99),
    )
    # Paginate matrix at ~15 rows per page
    MATRIX_PER_PAGE = 15
    for page_idx in range(0, len(sorted_findings), MATRIX_PER_PAGE):
        chunk = sorted_findings[page_idx : page_idx + MATRIX_PER_PAGE]
        _add("risk_matrix.html", {
            "findings": [f.model_dump() for f in chunk],
        })

    return pages


def _count_severities(findings: list[RiskFinding]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for f in findings:
        counts[f.severity] = counts.get(f.severity, 0) + 1
    return counts


def _build_key_metrics(ctx: RiskContext) -> list[dict]:
    metrics = []
    if ctx.loan_amount:
        metrics.append({"label": "Loan Request", "value": f"${ctx.loan_amount:,.0f}"})
    if ctx.total_development_cost:
        metrics.append({"label": "TDC", "value": f"${ctx.total_development_cost:,.0f}"})
    if ctx.ltc:
        metrics.append({"label": "LTC", "value": f"{ctx.ltc:.1%}"})
    if ctx.total_units:
        metrics.append({"label": "Units", "value": f"{ctx.total_units:,}"})
    return metrics
