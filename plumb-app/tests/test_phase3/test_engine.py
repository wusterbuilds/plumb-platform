"""Tests for the financial engine — unit mix parsing and tier aliases."""

import pytest

from app.financial.engine import _normalize_tier, parse_unit_mix
from app.financial.schemas import ResolvedField


class TestTierNormalization:
    @pytest.mark.parametrize("raw,expected", [
        ("Free Market", "FM"),
        ("free market", "FM"),
        ("market rate", "FM"),
        ("market-rate", "FM"),
        ("FM", "FM"),
        ("fm", "FM"),
        ("421a", "421A"),
        ("421-a", "421A"),
        ("affordable", "421A"),
        ("affordable 421a", "421A"),
        ("affordable_421a", "421A"),
        ("MIH", "MIH"),
        ("mih", "MIH"),
        ("inclusionary", "MIH"),
        ("mandatory inclusionary", "MIH"),
        ("commercial", "Commercial"),
        ("retail", "Commercial"),
        ("Commercial", "Commercial"),
        # Unknown → default FM
        ("luxury", "FM"),
        ("unknown tier", "FM"),
    ])
    def test_tier_alias_mapping(self, raw, expected):
        assert _normalize_tier(raw) == expected

    def test_none_defaults_to_fm(self):
        assert _normalize_tier(None) == "FM"


class TestParseUnitMix:
    def test_basic_parsing(self, raw_unit_mix_data):
        result = parse_unit_mix(raw_unit_mix_data, {})
        assert len(result.fm) == 3
        assert len(result.affordable_421a) == 3
        assert len(result.commercial) == 1

    def test_total_units_match(self, raw_unit_mix_data):
        result = parse_unit_mix(raw_unit_mix_data, {})
        total = sum(r.units for r in result.fm + result.affordable_421a + result.mih + result.commercial)
        expected = sum(d.get("units", 0) for d in raw_unit_mix_data)
        assert total == expected

    def test_rent_per_sf_auto_calculated(self, raw_unit_mix_data):
        """When rent_per_sf not provided but sf and rent are, it should be calculated."""
        result = parse_unit_mix(raw_unit_mix_data, {})
        for row in result.fm:
            if row.sf_per_unit > 0 and row.avg_monthly_rent > 0:
                expected = row.avg_monthly_rent / row.sf_per_unit
                assert row.rent_per_sf == pytest.approx(expected, rel=1e-3)

    def test_total_rows_generated(self, raw_unit_mix_data):
        result = parse_unit_mix(raw_unit_mix_data, {})
        assert len(result.total) > 0
        total_units = sum(r.units for r in result.total)
        all_units = sum(r.units for r in result.fm + result.affordable_421a + result.mih + result.commercial)
        assert total_units == all_units

    def test_commercial_from_inputs_fallback(self):
        """When no commercial in raw mix, falls back to commercial_sf/rent inputs."""
        inputs = {
            "commercial_sf": ResolvedField(field_name="commercial_sf", value=5000),
            "commercial_rent_psf": ResolvedField(field_name="commercial_rent_psf", value=40),
            "commercial_units": ResolvedField(field_name="commercial_units", value=2),
        }
        result = parse_unit_mix([], inputs)
        assert len(result.commercial) == 1
        assert result.commercial[0].units == 2
        assert result.commercial[0].sf_per_unit == pytest.approx(2500)

    def test_empty_raw_mix(self):
        result = parse_unit_mix([], {})
        assert len(result.fm) == 0
        assert len(result.affordable_421a) == 0
        assert len(result.total) == 0

    def test_non_dict_entries_skipped(self):
        raw = [
            {"tier": "FM", "beds": 1, "units": 10, "sf_per_unit": 700, "avg_monthly_rent": 3000},
            "invalid_entry",
            42,
            None,
        ]
        result = parse_unit_mix(raw, {})
        assert len(result.fm) == 1

    def test_alternative_key_names(self):
        """Parser should handle various key naming conventions from extraction."""
        raw = [
            {"program": "market", "bedrooms": 2, "count": 5, "area": 800, "monthly_rent": 3500},
            {"type": "421a", "br": 1, "bathrooms": 1, "units": 8, "sf": 600, "rent": 1400},
        ]
        result = parse_unit_mix(raw, {})
        assert len(result.fm) == 1
        assert result.fm[0].beds == 2
        assert result.fm[0].units == 5
        assert len(result.affordable_421a) == 1
        assert result.affordable_421a[0].baths == 1
