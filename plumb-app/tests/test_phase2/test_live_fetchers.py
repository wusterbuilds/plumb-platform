"""Live integration tests — hit real NYC public data APIs.

These tests are skipped by default. Run with:
    SKIP_LIVE_TESTS=0 python -m pytest tests/test_phase2/test_live_fetchers.py -v -s
"""

import json
import os

import httpx
import pytest

skip_live = pytest.mark.skipif(
    os.environ.get("SKIP_LIVE_TESTS", "1") == "1",
    reason="Set SKIP_LIVE_TESTS=0 to run live API tests",
)

skip_needs_brave = pytest.mark.skipif(
    not os.environ.get("BRAVE_API_KEY"),
    reason="BRAVE_API_KEY required for news search tests",
)


@skip_live
class TestLiveGeoSearch:
    async def test_real_address(self):
        from app.fetchers.nyc.geoclient import geocode_address

        result = await geocode_address("50 West 66th Street, New York, NY")
        assert result is not None
        assert len(result.bbl) == 10
        assert result.bin != ""
        assert result.borough in ("1", "2", "3", "4", "5")
        print(f"  BBL: {result.bbl}, BIN: {result.bin}, Label: {result.label}")


@skip_live
class TestLiveACRIS:
    async def test_real_bbl(self):
        from app.fetchers.nyc.acris import ACRISFetcher
        from app.fetchers.nyc.geoclient import geocode_address

        geo = await geocode_address("50 West 66th Street, New York, NY")
        assert geo is not None

        fetcher = ACRISFetcher()
        async with httpx.AsyncClient(timeout=30.0) as client:
            result = await fetcher.fetch(client, geo=geo)

        if result.error and "No ACRIS legals" in result.error:
            pytest.skip("No ACRIS data for this property (may be expected)")

        assert result.error is None
        data = json.loads(result.raw_data)
        assert "legals" in data
        print(f"  Legals: {len(data['legals'])}, Masters: {len(data['masters'])}, Parties: {len(data['parties'])}")


@skip_live
class TestLiveZoLa:
    async def test_real_bbl(self):
        from app.fetchers.nyc.geoclient import geocode_address
        from app.fetchers.nyc.zola import ZoLaFetcher

        geo = await geocode_address("50 West 66th Street, New York, NY")
        assert geo is not None

        fetcher = ZoLaFetcher()
        async with httpx.AsyncClient(timeout=30.0) as client:
            result = await fetcher.fetch(client, geo=geo)

        assert result.error is None
        interpreted = fetcher.interpret(result.raw_data, {})
        assert "zoning_district" in interpreted
        print(f"  Zoning: {interpreted.get('zoning_district')}, FAR: {interpreted.get('residential_far')}")


@skip_live
class TestLiveDOB:
    async def test_real_bin(self):
        from app.fetchers.nyc.dob import DOBFetcher
        from app.fetchers.nyc.geoclient import geocode_address

        geo = await geocode_address("50 West 66th Street, New York, NY")
        assert geo is not None

        fetcher = DOBFetcher()
        async with httpx.AsyncClient(timeout=30.0) as client:
            result = await fetcher.fetch(client, geo=geo)

        assert result.error is None
        data = json.loads(result.raw_data)
        print(
            f"  Jobs: {len(data['job_filings'])}, "
            f"Violations: {len(data['violations'])}, "
            f"Permits: {len(data['approved_permits'])}"
        )


@skip_live
@skip_needs_brave
class TestLiveNews:
    async def test_real_search(self):
        from app.fetchers.nyc.news import NewsSearchFetcher

        fetcher = NewsSearchFetcher()
        async with httpx.AsyncClient(timeout=30.0) as client:
            result = await fetcher.fetch(
                client, property_address="50 West 66th Street New York"
            )

        assert result.error is None
        articles = json.loads(result.raw_data)
        print(f"  Results: {len(articles)}")
        for a in articles[:3]:
            print(f"    - {a['title']}")
