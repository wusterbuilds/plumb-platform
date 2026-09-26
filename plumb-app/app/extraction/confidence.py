"""Confidence scoring for extracted values.

Scoring rubric:
  Base scores by source_type:
    table_cell: 0.95  — value in a structured table
    list_item:  0.90  — value in a bullet/numbered list
    paragraph:  0.80  — value embedded in narrative text
    footnote:   0.75  — value in a footnote or endnote
    inferred:   0.50  — value derived/calculated, not directly stated

  Adjustments:
    synonym label:     -0.05  (label doesn't exactly match but is equivalent)
    contextual label:  -0.10  (value inferred from surrounding context)
    OCR sourced:       -0.10  (from scanned/OCR'd document)
    corroboration:     +0.05  (value confirmed by another document)

  Flag assignment:
    green:  score >= 0.85
    yellow: score >= 0.60
    red:    score <  0.60
"""

BASE_SCORES = {
    "table_cell": 0.95,
    "list_item": 0.90,
    "paragraph": 0.80,
    "footnote": 0.75,
    "inferred": 0.50,
}

LABEL_ADJUSTMENTS = {
    "exact": 0.0,
    "synonym": -0.05,
    "contextual": -0.10,
}


def score_confidence(raw_field: dict) -> tuple[float, dict]:
    """Score an extracted field's confidence.

    Args:
        raw_field: dict with keys source_type, label_match.
                   Optional: ocr_sourced (bool).

    Returns:
        (score, confidence_basis) where confidence_basis is a dict
        suitable for storing in ExtractedValue.confidence_basis.
    """
    source_type = raw_field.get("source_type", "paragraph")
    label_match = raw_field.get("label_match", "contextual")
    ocr_sourced = raw_field.get("ocr_sourced", False)

    base = BASE_SCORES.get(source_type, 0.80)
    adjustments = []

    # Label match adjustment
    label_adj = LABEL_ADJUSTMENTS.get(label_match, -0.10)
    if label_adj != 0:
        adjustments.append(f"label_{label_match}: {label_adj:+.2f}")
    score = base + label_adj

    # OCR penalty
    if ocr_sourced:
        adjustments.append("ocr_sourced: -0.10")
        score -= 0.10

    # Clamp to [0, 1]
    score = max(0.0, min(1.0, score))

    confidence_basis = {
        "source_type": source_type,
        "label_match": label_match,
        "corroborated": False,
        "ocr_sourced": ocr_sourced,
        "adjustments_applied": adjustments if adjustments else None,
    }

    return (round(score, 4), confidence_basis)


def assign_flag(score: float) -> str:
    """Assign a flag color based on confidence score."""
    if score >= 0.85:
        return "green"
    if score >= 0.60:
        return "yellow"
    return "red"


def apply_corroboration(values: list[dict]) -> None:
    """Apply corroboration bonus to values confirmed across multiple documents.

    Mutates the list in place. Each dict should have:
      field_name, source_doc_id, confidence_score, confidence_basis

    Values with the same field_name from different documents get +0.05 bonus.
    """
    # Group by field_name
    by_field: dict[str, list[dict]] = {}
    for v in values:
        by_field.setdefault(v["field_name"], []).append(v)

    for field_name, field_values in by_field.items():
        # Only corroborate if same field appears in multiple documents
        unique_docs = {v.get("source_doc_id") for v in field_values}
        if len(unique_docs) < 2:
            continue

        for v in field_values:
            old_score = v["confidence_score"]
            new_score = min(1.0, old_score + 0.05)
            v["confidence_score"] = round(new_score, 4)
            v["flag"] = assign_flag(new_score)

            basis = v.get("confidence_basis") or {}
            basis["corroborated"] = True
            adj = basis.get("adjustments_applied") or []
            adj.append("corroboration: +0.05")
            basis["adjustments_applied"] = adj
            v["confidence_basis"] = basis
