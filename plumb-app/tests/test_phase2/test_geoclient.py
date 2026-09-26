"""Tests for NYC GeoSearch geocoding utility."""

import os

import httpx
import pytest

from app.fetchers.nyc.geoclient import GeoResult, geocode_address, parse_bbl

from .conftest import CANNED_GEOSEARCH_RESPONSE


# ---------------------------------------------------------------------------
# parse_bbl — pure unit tests
# ---------------------------------------------------------------------------


class TestParseBBL:
    def test_standard_10_digit(self):
        borough, block, lot = parse_bbl("1011230001")
        assert borough == "1"
        assert block == "01123"
        assert lot == "0001"

    def test_short_input_zero_padded(self):
        # "12345" → zfill(10) → "0000012345"
        borough, block, lot = parse_bbl("12345")
        assert borough == "0"
        assert block == "00001"
        assert lot == "2345"

    def test_all_zeros(self):
        borough, block, lot = parse_bbl("0000000000")
        assert borough == "0"
        assert block == "00000"
        assert lot == "0000"

    def test_queens_bbl(self):
        # Queens is borough 4
        borough, block, lot = parse_bbl("4004560078")
        assert borough == "4"
        assert block == "00456"
        assert lot == "0078"


# ---------------------------------------------------------------------------
# geocode_address — mock httpx
# ---------------------------------------------------------------------------


class TestGeocodeAddress:
    async def test_success(self):
        transport = httpx.MockTransport(
            lambda request: httpx.Response(200, json=CANNED_GEOSEARCH_RESPONSE)
        )
        async with httpx.AsyncClient(transport=transport) as client:
            result = await geocode_address("50 West 66th Street, New York", client)

        assert result is not None
        assert isinstance(result, GeoResult)
        assert result.bbl == "1011230001"
        assert result.bbl_numeric == 1011230001
        assert result.bin == "1022571"
        assert result.borough == "1"
        assert result.block == "01123"
        assert result.lot == "0001"
        assert result.latitude == pytest.approx(40.7747)
        assert result.longitude == pytest.approx(-73.9810)

    async def test_no_features(self):
        response = {"type": "FeatureCollection", "features": []}
        transport = httpx.MockTransport(
            lambda request: httpx.Response(200, json=response)
        )
        async with httpx.AsyncClient(transport=transport) as client:
            result = await geocode_address("Nonexistent Address", client)

        assert result is None

    async def test_missing_bbl(self):
        response = {
            "features": [
                {
                    "geometry": {"coordinates": [-73.98, 40.77]},
                    "properties": {
                        "label": "Test",
                        "addendum": {"pad": {"bin": "1234"}},
                    },
                }
            ]
        }
        transport = httpx.MockTransport(
            lambda request: httpx.Response(200, json=response)
        )
        async with httpx.AsyncClient(transport=transport) as client:
            result = await geocode_address("Some Address", client)

        assert result is None

    async def test_http_error(self):
        transport = httpx.MockTransport(
            lambda request: httpx.Response(500, text="Server error")
        )
        async with httpx.AsyncClient(transport=transport) as client:
            result = await geocode_address("Some Address", client)

        assert result is None


# ---------------------------------------------------------------------------
# Live test — real GeoSearch API
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    os.environ.get("SKIP_LIVE_TESTS", "1") == "1",
    reason="Set SKIP_LIVE_TESTS=0 to run live API tests",
)
class TestGeocodeAddressLive:
    async def test_real_address(self):
        result = await geocode_address("50 West 66th Street, New York, NY")
        assert result is not None
        assert len(result.bbl) == 10
        assert result.bin != ""
        assert result.latitude > 40
        assert result.longitude < -73
