"""Tests for confidence scoring engine."""

from app.extraction.confidence import apply_corroboration, assign_flag, score_confidence


class TestScoreConfidence:
    def test_table_cell_exact(self):
        score, basis = score_confidence({
            "source_type": "table_cell",
            "label_match": "exact",
        })
        assert score == 0.95
        assert basis["source_type"] == "table_cell"
        assert basis["label_match"] == "exact"

    def test_table_cell_synonym(self):
        score, basis = score_confidence({
            "source_type": "table_cell",
            "label_match": "synonym",
        })
        assert score == 0.90

    def test_table_cell_contextual(self):
        score, basis = score_confidence({
            "source_type": "table_cell",
            "label_match": "contextual",
        })
        assert score == 0.85

    def test_list_item_exact(self):
        score, _ = score_confidence({
            "source_type": "list_item",
            "label_match": "exact",
        })
        assert score == 0.90

    def test_paragraph_exact(self):
        score, _ = score_confidence({
            "source_type": "paragraph",
            "label_match": "exact",
        })
        assert score == 0.80

    def test_footnote_exact(self):
        score, _ = score_confidence({
            "source_type": "footnote",
            "label_match": "exact",
        })
        assert score == 0.75

    def test_inferred_exact(self):
        score, _ = score_confidence({
            "source_type": "inferred",
            "label_match": "exact",
        })
        assert score == 0.50

    def test_ocr_penalty(self):
        score, basis = score_confidence({
            "source_type": "table_cell",
            "label_match": "exact",
            "ocr_sourced": True,
        })
        assert score == 0.85
        assert basis["ocr_sourced"] is True

    def test_combined_penalties(self):
        score, _ = score_confidence({
            "source_type": "paragraph",
            "label_match": "contextual",
            "ocr_sourced": True,
        })
        # 0.80 - 0.10 (contextual) - 0.10 (OCR) = 0.60
        assert score == 0.60

    def test_score_clamps_to_zero(self):
        score, _ = score_confidence({
            "source_type": "inferred",
            "label_match": "contextual",
            "ocr_sourced": True,
        })
        # 0.50 - 0.10 - 0.10 = 0.30
        assert score == 0.30
        assert score >= 0.0

    def test_defaults_for_missing_keys(self):
        score, basis = score_confidence({})
        # defaults: paragraph + contextual
        assert score == 0.70
        assert basis["source_type"] == "paragraph"
        assert basis["label_match"] == "contextual"


class TestAssignFlag:
    def test_green_boundary(self):
        assert assign_flag(0.85) == "green"
        assert assign_flag(0.90) == "green"
        assert assign_flag(1.0) == "green"

    def test_yellow_boundary(self):
        assert assign_flag(0.60) == "yellow"
        assert assign_flag(0.84) == "yellow"
        assert assign_flag(0.75) == "yellow"

    def test_red_boundary(self):
        assert assign_flag(0.59) == "red"
        assert assign_flag(0.0) == "red"
        assert assign_flag(0.50) == "red"


class TestApplyCorroboration:
    def test_corroboration_bonus(self):
        values = [
            {
                "field_name": "total_units",
                "source_doc_id": "doc-1",
                "confidence_score": 0.90,
                "confidence_basis": {"source_type": "table_cell", "label_match": "exact"},
                "flag": "green",
            },
            {
                "field_name": "total_units",
                "source_doc_id": "doc-2",
                "confidence_score": 0.80,
                "confidence_basis": {"source_type": "paragraph", "label_match": "exact"},
                "flag": "yellow",
            },
        ]
        apply_corroboration(values)

        assert values[0]["confidence_score"] == 0.95
        assert values[0]["confidence_basis"]["corroborated"] is True
        assert values[1]["confidence_score"] == 0.85
        assert values[1]["flag"] == "green"  # promoted from yellow

    def test_no_corroboration_single_doc(self):
        values = [
            {
                "field_name": "total_units",
                "source_doc_id": "doc-1",
                "confidence_score": 0.80,
                "confidence_basis": {},
                "flag": "yellow",
            },
        ]
        apply_corroboration(values)
        assert values[0]["confidence_score"] == 0.80

    def test_no_corroboration_same_doc(self):
        values = [
            {
                "field_name": "total_units",
                "source_doc_id": "doc-1",
                "confidence_score": 0.80,
                "confidence_basis": {},
                "flag": "yellow",
            },
            {
                "field_name": "total_units",
                "source_doc_id": "doc-1",
                "confidence_score": 0.75,
                "confidence_basis": {},
                "flag": "yellow",
            },
        ]
        apply_corroboration(values)
        assert values[0]["confidence_score"] == 0.80
        assert values[1]["confidence_score"] == 0.75

    def test_score_capped_at_one(self):
        values = [
            {
                "field_name": "total_units",
                "source_doc_id": "doc-1",
                "confidence_score": 0.98,
                "confidence_basis": {},
                "flag": "green",
            },
            {
                "field_name": "total_units",
                "source_doc_id": "doc-2",
                "confidence_score": 0.97,
                "confidence_basis": {},
                "flag": "green",
            },
        ]
        apply_corroboration(values)
        assert values[0]["confidence_score"] == 1.0
        assert values[1]["confidence_score"] == 1.0
