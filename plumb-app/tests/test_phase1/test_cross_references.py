"""Tests for cross-reference comparison logic."""

from app.extraction.cross_references import compare_values, parse_numeric


class TestParseNumeric:
    def test_plain_number(self):
        assert parse_numeric("415") == 415.0

    def test_number_with_commas(self):
        assert parse_numeric("125,000,000") == 125_000_000.0

    def test_number_with_dollar_sign(self):
        assert parse_numeric("$125,000,000") == 125_000_000.0

    def test_percentage(self):
        assert parse_numeric("65%") == 65.0

    def test_decimal(self):
        assert parse_numeric("0.65") == 0.65

    def test_none(self):
        assert parse_numeric(None) is None

    def test_non_numeric(self):
        assert parse_numeric("not a number") is None

    def test_whitespace(self):
        assert parse_numeric(" 100 ") == 100.0

    def test_negative(self):
        assert parse_numeric("-500") == -500.0


class TestCompareValues:
    # --- Exact comparison ---

    def test_exact_match(self):
        result, delta = compare_values("415", "415", "exact", 0.0)
        assert result == "match"
        assert delta is None

    def test_exact_mismatch(self):
        result, delta = compare_values("415", "425", "exact", 0.0)
        assert result == "mismatch"
        assert "415" in delta
        assert "425" in delta

    def test_exact_match_with_formatting(self):
        result, _ = compare_values("$1,000", "1000", "exact", 0.0)
        assert result == "match"

    # --- Percentage comparison ---

    def test_percentage_match(self):
        result, delta = compare_values("100000000", "100000000", "percentage", 0.20)
        assert result == "match"

    def test_percentage_within_tolerance(self):
        result, delta = compare_values("100000000", "110000000", "percentage", 0.20)
        assert result == "within_tolerance"
        assert "tolerance" in delta

    def test_percentage_mismatch(self):
        result, delta = compare_values("100000000", "200000000", "percentage", 0.20)
        assert result == "mismatch"
        assert "exceeds" in delta

    def test_percentage_small_difference(self):
        result, _ = compare_values("417500000", "330000000", "percentage", 0.20)
        assert result == "mismatch"  # ~23.4% diff, exceeds 20%

    def test_percentage_zero_values(self):
        result, _ = compare_values("0", "0", "percentage", 0.20)
        assert result == "match"

    def test_percentage_one_zero(self):
        result, _ = compare_values("100000", "0", "percentage", 0.20)
        assert result == "mismatch"

    # --- Edge cases ---

    def test_unable_to_check_none(self):
        result, delta = compare_values(None, "100", "exact", 0.0)
        assert result == "unable_to_check"

    def test_unable_to_check_non_numeric(self):
        result, delta = compare_values("abc", "100", "exact", 0.0)
        assert result == "unable_to_check"

    def test_both_none(self):
        result, _ = compare_values(None, None, "exact", 0.0)
        assert result == "unable_to_check"


class TestConstructionLoanRules:
    """Verify known synthetic-fixture discrepancies are caught."""

    def test_unit_count_mismatch(self):
        """Synthetic fixture: 415 vs 425 units should be caught as exact mismatch."""
        result, delta = compare_values("415", "425", "exact", 0.0)
        assert result == "mismatch"

    def test_affordable_units_mismatch(self):
        """Synthetic fixture: 107 vs 113 affordable units should be caught."""
        result, _ = compare_values("107", "113", "exact", 0.0)
        assert result == "mismatch"

    def test_sellout_mismatch(self):
        """Synthetic fixture: $417.5M vs $330M should exceed 20% tolerance."""
        result, delta = compare_values("417500000", "330000000", "percentage", 0.20)
        assert result == "mismatch"
        # Difference is ~23.4%, which exceeds 20% tolerance
