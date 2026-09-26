"""Cross-reference engine for construction loan deals.

Compares values extracted from different documents to flag discrepancies.
Each rule defines two fields, the documents they come from, a comparison type,
and a tolerance.
"""

import re
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.extraction import CrossReference, ExtractedValue


@dataclass
class CrossRefRule:
    rule_name: str
    field_a: str
    field_a_doc_types: list[str]  # which doc types field_a comes from
    field_b: str
    field_b_doc_types: list[str]
    comparison: str  # "exact" or "percentage"
    tolerance: float  # 0.0 for exact, e.g. 0.20 for 20%


# Construction loan cross-reference rules
CONSTRUCTION_LOAN_RULES = [
    CrossRefRule(
        rule_name="unit_count_summary_vs_proforma",
        field_a="total_units",
        field_a_doc_types=["project_summary_deck"],
        field_b="total_units",
        field_b_doc_types=["pro_forma"],
        comparison="exact",
        tolerance=0.0,
    ),
    CrossRefRule(
        rule_name="unit_count_summary_vs_appraisal",
        field_a="total_units",
        field_a_doc_types=["project_summary_deck"],
        field_b="total_units",
        field_b_doc_types=["appraisal"],
        comparison="exact",
        tolerance=0.0,
    ),
    CrossRefRule(
        rule_name="affordable_units_summary_vs_zoning",
        field_a="affordable_units",
        field_a_doc_types=["project_summary_deck"],
        field_b="affordable_units",
        field_b_doc_types=["zoning_approval"],
        comparison="exact",
        tolerance=0.0,
    ),
    CrossRefRule(
        rule_name="gross_sellout_proforma_vs_appraisal",
        field_a="gross_sellout",
        field_a_doc_types=["pro_forma"],
        field_b="gross_sellout",
        field_b_doc_types=["appraisal"],
        comparison="percentage",
        tolerance=0.20,  # 20% tolerance
    ),
    CrossRefRule(
        rule_name="tdc_summary_vs_proforma",
        field_a="total_development_cost",
        field_a_doc_types=["project_summary_deck"],
        field_b="total_development_cost",
        field_b_doc_types=["pro_forma"],
        comparison="percentage",
        tolerance=0.05,  # 5% tolerance
    ),
]


def parse_numeric(value: str | None) -> float | None:
    """Parse a numeric value from a string, handling commas, $, %, etc."""
    if value is None:
        return None
    # Strip whitespace, $, commas
    cleaned = re.sub(r"[$,\s]", "", str(value))
    # Handle percentage
    if cleaned.endswith("%"):
        cleaned = cleaned[:-1]
    try:
        return float(cleaned)
    except (ValueError, TypeError):
        return None


def compare_values(
    a_str: str | None, b_str: str | None, comparison: str, tolerance: float
) -> tuple[str, str | None]:
    """Compare two values according to the rule's comparison type.

    Returns: (result, delta) where result is one of:
      "match", "mismatch", "within_tolerance", "unable_to_check"
    and delta is a human-readable description of the difference.
    """
    a = parse_numeric(a_str)
    b = parse_numeric(b_str)

    if a is None or b is None:
        return ("unable_to_check", f"Could not parse: a={a_str!r}, b={b_str!r}")

    if comparison == "exact":
        if a == b:
            return ("match", None)
        return ("mismatch", f"{a} vs {b} (diff: {abs(a - b)})")

    if comparison == "percentage":
        if a == 0 and b == 0:
            return ("match", None)
        if a == 0 or b == 0:
            return ("mismatch", f"{a} vs {b} (one is zero)")

        # Percentage difference relative to the average
        avg = (abs(a) + abs(b)) / 2
        pct_diff = abs(a - b) / avg

        if pct_diff == 0:
            return ("match", None)
        if pct_diff <= tolerance:
            return (
                "within_tolerance",
                f"{a:,.0f} vs {b:,.0f} ({pct_diff:.1%} diff, tolerance {tolerance:.0%})",
            )
        return (
            "mismatch",
            f"{a:,.0f} vs {b:,.0f} ({pct_diff:.1%} diff, exceeds {tolerance:.0%} tolerance)",
        )

    return ("unable_to_check", f"Unknown comparison type: {comparison}")


def _find_value(
    db: Session, deal_id: uuid.UUID, field_name: str, doc_types: list[str]
) -> tuple[ExtractedValue | None, str | None]:
    """Find the best extracted value for a field from specified document types."""
    from app.models.document import Document

    stmt = (
        select(ExtractedValue)
        .join(Document, ExtractedValue.source_doc_id == Document.id)
        .where(
            ExtractedValue.deal_id == deal_id,
            ExtractedValue.field_name == field_name,
            Document.document_type.in_(doc_types),
        )
        .order_by(ExtractedValue.confidence_score.desc().nullslast())
    )
    result = db.execute(stmt)
    ev = result.scalars().first()
    if ev is None:
        return (None, None)

    # Use override_value if it exists, otherwise the extracted value
    val = ev.override_value if ev.override_value else ev.value
    return (ev, val)


def run_all_cross_references(
    deal_id: uuid.UUID,
    db: Session,
    rules: list[CrossRefRule] | None = None,
) -> list[CrossReference]:
    """Run all cross-reference rules for a deal.

    Deletes existing cross-references for the deal before creating new ones
    (idempotent re-run).
    """
    if rules is None:
        rules = CONSTRUCTION_LOAN_RULES

    # Clear previous cross-references for this deal
    db.query(CrossReference).filter(CrossReference.deal_id == deal_id).delete()
    db.flush()

    results = []
    for rule in rules:
        ev_a, val_a = _find_value(db, deal_id, rule.field_a, rule.field_a_doc_types)
        ev_b, val_b = _find_value(db, deal_id, rule.field_b, rule.field_b_doc_types)

        result, delta = compare_values(val_a, val_b, rule.comparison, rule.tolerance)

        tolerance_str = None
        if rule.tolerance > 0:
            tolerance_str = f"{rule.tolerance:.0%}"

        xref = CrossReference(
            deal_id=deal_id,
            rule_name=rule.rule_name,
            field_a=rule.field_a,
            field_a_value=val_a,
            field_a_source_doc_id=ev_a.source_doc_id if ev_a else None,
            field_b=rule.field_b,
            field_b_value=val_b,
            field_b_source_doc_id=ev_b.source_doc_id if ev_b else None,
            result=result,
            tolerance_applied=tolerance_str,
            delta=delta,
        )
        db.add(xref)
        results.append(xref)

    db.flush()
    return results
