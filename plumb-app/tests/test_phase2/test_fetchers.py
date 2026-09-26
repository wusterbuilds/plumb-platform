"""Tests for public data fetchers (ACRIS, ZoLa, DOB, News, AG REFB) and registry."""

import json
from unittest.mock import MagicMock

import httpx
import pytest

from app.fetchers.nyc.acris import ACRISFetcher
from app.fetchers.nyc.ag_refb import AGREFBFetcher
from app.fetchers.nyc.dob import DOBFetcher
from app.fetchers.nyc.news import NewsSearchFetcher
from app.fetchers.nyc.zola import PLUTO_FIELD_MAP, ZoLaFetcher
from app.fetchers.registry import detect_geography, get_fetchers

from .conftest import (
    CANNED_ACRIS_LEGALS,
    CANNED_ACRIS_MASTERS,
    CANNED_ACRIS_PARTIES,
    CANNED_BRAVE_RESULTS,
    CANNED_DOB_JOB_FILINGS,
    CANNED_DOB_PERMITS,
    CANNED_DOB_VIOLATIONS,
    CANNED_PLUTO_RESPONSE,
)


# ===========================================================================
# ACRIS Fetcher
# ===========================================================================


class TestACRISFetch:
    def setup_method(self):
        self.fetcher = ACRISFetcher()

    async def test_no_geo_returns_error(self):
        transport = httpx.MockTransport(lambda r: httpx.Response(200, json=[]))
        async with httpx.AsyncClient(transport=transport) as client:
            result = await self.fetcher.fetch(client, geo=None)
        assert result.error is not None
        assert "No GeoResult" in result.error

    async def test_success(self, mock_geo_result):
        call_count = 0

        def _handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            url = str(request.url)
            if "8h5j-fqxa" in url:  # legals
                return httpx.Response(200, json=CANNED_ACRIS_LEGALS)
            elif "bnx9-e6tj" in url:  # masters
                return httpx.Response(200, json=CANNED_ACRIS_MASTERS)
            elif "636b-3b5g" in url:  # parties
                return httpx.Response(200, json=CANNED_ACRIS_PARTIES)
            return httpx.Response(200, json=[])

        transport = httpx.MockTransport(_handler)
        async with httpx.AsyncClient(transport=transport) as client:
            result = await self.fetcher.fetch(client, geo=mock_geo_result)

        assert result.error is None
        data = json.loads(result.raw_data)
        assert "legals" in data
        assert "masters" in data
        assert "parties" in data
        assert len(data["legals"]) == 2

    async def test_no_legals_returns_error(self, mock_geo_result):
        transport = httpx.MockTransport(lambda r: httpx.Response(200, json=[]))
        async with httpx.AsyncClient(transport=transport) as client:
            result = await self.fetcher.fetch(client, geo=mock_geo_result)
        assert result.error is not None
        assert "No ACRIS legals" in result.error

    async def test_http_error(self, mock_geo_result):
        transport = httpx.MockTransport(
            lambda r: httpx.Response(500, text="Server error")
        )
        async with httpx.AsyncClient(transport=transport) as client:
            result = await self.fetcher.fetch(client, geo=mock_geo_result)
        assert result.error is not None

    async def test_batch_splitting(self, mock_geo_result):
        """25+ doc_ids should be split into 2 batches."""
        many_legals = [
            {"document_id": f"DOC{i:03d}", "borough": "1", "block": "01123", "lot": "0001"}
            for i in range(25)
        ]
        master_calls = 0

        def _handler(request: httpx.Request) -> httpx.Response:
            nonlocal master_calls
            url = str(request.url)
            if "8h5j-fqxa" in url:
                return httpx.Response(200, json=many_legals)
            elif "bnx9-e6tj" in url:
                master_calls += 1
                return httpx.Response(200, json=[])
            elif "636b-3b5g" in url:
                return httpx.Response(200, json=[])
            return httpx.Response(200, json=[])

        transport = httpx.MockTransport(_handler)
        async with httpx.AsyncClient(transport=transport) as client:
            result = await self.fetcher.fetch(client, geo=mock_geo_result)

        assert result.error is None
        assert master_calls == 2  # 25 docs / batch_size 20 = 2 batches


class TestACRISInterpret:
    def setup_method(self):
        self.fetcher = ACRISFetcher()

    def test_empty_data(self):
        assert self.fetcher.interpret("", {}) == {}
        assert self.fetcher.interpret("[]", {}) == {}

    def test_no_llm_returns_count(self):
        data = json.dumps({"legals": CANNED_ACRIS_LEGALS, "masters": [], "parties": []})
        result = self.fetcher.interpret(data, {})
        assert result["raw_record_count"] == 2

    def test_with_llm(self):
        mock_llm = MagicMock()
        mock_llm.call_llm.return_value = {
            "summary": "Test summary",
            "current_owner": "Test LLC",
        }
        data = json.dumps({"legals": CANNED_ACRIS_LEGALS, "masters": [], "parties": []})
        result = self.fetcher.interpret(data, {"deal_id": "123"}, llm_client=mock_llm)
        assert result["summary"] == "Test summary"
        mock_llm.call_llm.assert_called_once()


# ===========================================================================
# ZoLa Fetcher
# ===========================================================================


class TestZoLaFetch:
    def setup_method(self):
        self.fetcher = ZoLaFetcher()

    async def test_no_geo_returns_error(self):
        transport = httpx.MockTransport(lambda r: httpx.Response(200, json=[]))
        async with httpx.AsyncClient(transport=transport) as client:
            result = await self.fetcher.fetch(client, geo=None)
        assert result.error is not None

    async def test_success(self, mock_geo_result):
        transport = httpx.MockTransport(
            lambda r: httpx.Response(200, json=CANNED_PLUTO_RESPONSE)
        )
        async with httpx.AsyncClient(transport=transport) as client:
            result = await self.fetcher.fetch(client, geo=mock_geo_result)

        assert result.error is None
        data = json.loads(result.raw_data)
        assert data[0]["zonedist1"] == "R8"

    async def test_empty_returns_error(self, mock_geo_result):
        transport = httpx.MockTransport(lambda r: httpx.Response(200, json=[]))
        async with httpx.AsyncClient(transport=transport) as client:
            result = await self.fetcher.fetch(client, geo=mock_geo_result)
        assert result.error is not None
        assert "No PLUTO record" in result.error


class TestZoLaInterpret:
    def setup_method(self):
        self.fetcher = ZoLaFetcher()

    def test_field_mapping(self):
        raw = json.dumps(CANNED_PLUTO_RESPONSE)
        result = self.fetcher.interpret(raw, {})

        assert result["zoning_district"] == "R8"
        assert result["overlay_1"] == "C1-5"
        assert result["residential_far"] == "6.02"
        assert result["lot_area_sf"] == "15000"
        assert result["building_area_sf"] == "85000"
        assert result["building_class"] == "R4"
        assert result["owner_name"] == "TEST OWNER LLC"
        assert result["year_built"] == "1965"
        assert result["residential_units"] == "120"

    def test_empty_data(self):
        assert self.fetcher.interpret("", {}) == {}
        assert self.fetcher.interpret("[]", {}) == {}

    def test_partial_fields(self):
        raw = json.dumps([{"zonedist1": "C6-1", "lotarea": "5000"}])
        result = self.fetcher.interpret(raw, {})
        assert result["zoning_district"] == "C6-1"
        assert result["lot_area_sf"] == "5000"
        assert "building_class" not in result

    def test_all_pluto_fields_mapped(self):
        """Every key in PLUTO_FIELD_MAP should produce a mapped field."""
        row = {k: f"val_{k}" for k in PLUTO_FIELD_MAP}
        raw = json.dumps([row])
        result = self.fetcher.interpret(raw, {})
        for pluto_key, our_key in PLUTO_FIELD_MAP.items():
            assert our_key in result, f"PLUTO key '{pluto_key}' not mapped to '{our_key}'"


# ===========================================================================
# DOB Fetcher
# ===========================================================================


class TestDOBFetch:
    def setup_method(self):
        self.fetcher = DOBFetcher()

    async def test_no_geo_returns_error(self):
        transport = httpx.MockTransport(lambda r: httpx.Response(200, json=[]))
        async with httpx.AsyncClient(transport=transport) as client:
            result = await self.fetcher.fetch(client, geo=None)
        assert result.error is not None

    async def test_success(self, mock_geo_result):
        def _handler(request: httpx.Request) -> httpx.Response:
            url = str(request.url)
            if "w9ak-ipjd" in url:
                return httpx.Response(200, json=CANNED_DOB_JOB_FILINGS)
            elif "6bgk-3dad" in url:
                return httpx.Response(200, json=CANNED_DOB_VIOLATIONS)
            elif "rbx6-tga4" in url:
                return httpx.Response(200, json=CANNED_DOB_PERMITS)
            return httpx.Response(200, json=[])

        transport = httpx.MockTransport(_handler)
        async with httpx.AsyncClient(transport=transport) as client:
            result = await self.fetcher.fetch(client, geo=mock_geo_result)

        assert result.error is None
        data = json.loads(result.raw_data)
        assert "job_filings" in data
        assert "violations" in data
        assert "approved_permits" in data
        assert data["sponsor_violations"] == []

    async def test_with_sponsor_name(self, mock_geo_result):
        sponsor_violation_calls = 0

        def _handler(request: httpx.Request) -> httpx.Response:
            nonlocal sponsor_violation_calls
            url = str(request.url)
            params = str(request.url.params)
            if "6bgk-3dad" in url and "respondent_name" in params:
                sponsor_violation_calls += 1
                return httpx.Response(200, json=[{"violation": "sponsor"}])
            if "w9ak-ipjd" in url:
                return httpx.Response(200, json=CANNED_DOB_JOB_FILINGS)
            if "6bgk-3dad" in url:
                return httpx.Response(200, json=CANNED_DOB_VIOLATIONS)
            if "rbx6-tga4" in url:
                return httpx.Response(200, json=CANNED_DOB_PERMITS)
            return httpx.Response(200, json=[])

        transport = httpx.MockTransport(_handler)
        async with httpx.AsyncClient(transport=transport) as client:
            result = await self.fetcher.fetch(
                client, geo=mock_geo_result, sponsor_name="Test Developer"
            )

        assert result.error is None
        data = json.loads(result.raw_data)
        assert sponsor_violation_calls == 1
        assert len(data["sponsor_violations"]) == 1


class TestDOBInterpret:
    def setup_method(self):
        self.fetcher = DOBFetcher()

    def test_empty_data(self):
        assert self.fetcher.interpret("", {}) == {}

    def test_no_llm_returns_counts(self):
        data = json.dumps({
            "job_filings": CANNED_DOB_JOB_FILINGS,
            "violations": CANNED_DOB_VIOLATIONS,
            "approved_permits": CANNED_DOB_PERMITS,
        })
        result = self.fetcher.interpret(data, {})
        assert result["job_filings_count"] == 1
        assert result["violations_count"] == 1
        assert result["permits_count"] == 1

    def test_with_llm(self):
        mock_llm = MagicMock()
        mock_llm.call_llm.return_value = {"summary": "No issues", "material_flags": []}
        raw = json.dumps({"job_filings": [], "violations": [], "approved_permits": []})
        result = self.fetcher.interpret(raw, {}, llm_client=mock_llm)
        assert result["summary"] == "No issues"


# ===========================================================================
# News Search Fetcher
# ===========================================================================


class TestNewsSearchFetch:
    def setup_method(self):
        self.fetcher = NewsSearchFetcher()

    async def test_no_api_key(self):
        from unittest.mock import patch

        with patch("app.fetchers.nyc.news.settings") as mock_settings:
            mock_settings.BRAVE_API_KEY = ""
            transport = httpx.MockTransport(lambda r: httpx.Response(200, json={}))
            async with httpx.AsyncClient(transport=transport) as client:
                result = await self.fetcher.fetch(client, property_address="123 Main")
        assert result.error is not None
        assert "BRAVE_API_KEY" in result.error

    async def test_no_search_terms(self):
        from unittest.mock import patch

        with patch("app.fetchers.nyc.news.settings") as mock_settings:
            mock_settings.BRAVE_API_KEY = "test-key"
            transport = httpx.MockTransport(lambda r: httpx.Response(200, json={}))
            async with httpx.AsyncClient(transport=transport) as client:
                result = await self.fetcher.fetch(client)
        assert result.error is not None

    async def test_success(self):
        from unittest.mock import patch

        with patch("app.fetchers.nyc.news.settings") as mock_settings:
            mock_settings.BRAVE_API_KEY = "test-key"
            transport = httpx.MockTransport(
                lambda r: httpx.Response(200, json=CANNED_BRAVE_RESULTS)
            )
            async with httpx.AsyncClient(transport=transport) as client:
                result = await self.fetcher.fetch(
                    client, property_address="50 W 66th St"
                )

        assert result.error is None
        articles = json.loads(result.raw_data)
        assert len(articles) == 2
        assert articles[0]["title"] == "New Condo Tower Planned for Upper West Side"

    async def test_deduplication(self):
        """Same URL from different queries should be deduped."""
        from unittest.mock import patch

        with patch("app.fetchers.nyc.news.settings") as mock_settings:
            mock_settings.BRAVE_API_KEY = "test-key"
            transport = httpx.MockTransport(
                lambda r: httpx.Response(200, json=CANNED_BRAVE_RESULTS)
            )
            async with httpx.AsyncClient(transport=transport) as client:
                result = await self.fetcher.fetch(
                    client,
                    property_address="50 W 66th St",
                    developer_name="Test Dev",
                )

        articles = json.loads(result.raw_data)
        urls = [a["url"] for a in articles]
        assert len(urls) == len(set(urls)), "Duplicate URLs found"

    async def test_partial_failure(self):
        """If one query fails, others still return results."""
        from unittest.mock import patch

        call_count = 0

        def _handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return httpx.Response(500, text="Server error")
            return httpx.Response(200, json=CANNED_BRAVE_RESULTS)

        with patch("app.fetchers.nyc.news.settings") as mock_settings:
            mock_settings.BRAVE_API_KEY = "test-key"
            transport = httpx.MockTransport(_handler)
            async with httpx.AsyncClient(transport=transport) as client:
                result = await self.fetcher.fetch(
                    client,
                    property_address="50 W 66th St",
                    developer_name="Test Dev",
                )

        assert result.error is None
        articles = json.loads(result.raw_data)
        assert len(articles) > 0


class TestNewsInterpret:
    def setup_method(self):
        self.fetcher = NewsSearchFetcher()

    def test_empty(self):
        assert self.fetcher.interpret("", {}) == {"articles": []}
        assert self.fetcher.interpret("[]", {}) == {"articles": []}

    def test_no_llm_returns_raw(self):
        raw = json.dumps([{"title": "Test", "url": "http://test.com"}])
        result = self.fetcher.interpret(raw, {})
        assert result["total_results"] == 1
        assert len(result["articles"]) == 1


# ===========================================================================
# AG REFB Fetcher
# ===========================================================================


class TestAGREFBFetch:
    def setup_method(self):
        self.fetcher = AGREFBFetcher()

    async def test_no_search_terms(self):
        """Both address and sponsor None still makes requests (welcome page)."""
        def _handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text="<html>Welcome</html>")

        transport = httpx.MockTransport(_handler)
        async with httpx.AsyncClient(transport=transport) as client:
            result = await self.fetcher.fetch(client)

        # No data found since no search terms → error message
        assert "No results" in (result.error or "")

    async def test_session_failure_graceful(self):
        transport = httpx.MockTransport(
            lambda r: httpx.Response(500, text="Server error")
        )
        async with httpx.AsyncClient(transport=transport) as client:
            result = await self.fetcher.fetch(
                client, property_address="50 W 66th St"
            )

        assert result.error is not None
        assert "manual verification" in result.error.lower()
        data = json.loads(result.raw_data)
        assert data["status"] == "manual_verification_needed"


class TestAGREFBInterpret:
    def setup_method(self):
        self.fetcher = AGREFBFetcher()

    def test_empty_data(self):
        assert self.fetcher.interpret("", {}) == {}

    def test_manual_verification_passthrough(self):
        data = json.dumps({"status": "manual_verification_needed", "search_url": "http://test"})
        result = self.fetcher.interpret(data, {})
        assert result["status"] == "manual_verification_needed"

    def test_no_llm(self):
        data = json.dumps({
            "address_search": [{"plan": "P001"}],
            "sponsor_search": [{"plan": "P002"}],
            "manual_verification_url": "http://test",
        })
        result = self.fetcher.interpret(data, {})
        assert len(result["address_results"]) == 1
        assert len(result["sponsor_results"]) == 1

    def test_with_llm(self):
        mock_llm = MagicMock()
        mock_llm.call_llm.return_value = {
            "offering_plans": [{"plan_id": "P001"}],
            "material_flags": [],
            "summary": "No issues",
        }
        data = json.dumps({
            "address_search": [{"plan": "P001"}],
            "sponsor_search": [],
            "manual_verification_url": "http://test",
        })
        result = self.fetcher.interpret(data, {}, llm_client=mock_llm)
        assert result["summary"] == "No issues"
        assert result["manual_verification_url"] == "http://test"


# ===========================================================================
# Fetcher Registry
# ===========================================================================


class TestFetcherRegistry:
    def test_get_fetchers_nyc(self):
        fetchers = get_fetchers("nyc")
        assert len(fetchers) == 5
        assert "zoning" in fetchers
        assert "property_records" in fetchers
        assert "permits" in fetchers
        assert "news" in fetchers
        assert "offering_plan" in fetchers

    def test_get_fetchers_unknown(self):
        assert get_fetchers("chicago") == {}
        assert get_fetchers("") == {}

    def test_detect_geography_nyc(self):
        assert detect_geography("123 Main St, New York, NY") == "nyc"
        assert detect_geography("456 Broadway, Manhattan") == "nyc"
        assert detect_geography("789 Flatbush Ave, Brooklyn") == "nyc"

    def test_detect_geography_non_nyc(self):
        assert detect_geography("123 Main St, Chicago, IL") is None
        assert detect_geography("456 Market St, San Francisco, CA") is None

    def test_detect_geography_none(self):
        assert detect_geography(None) is None
        assert detect_geography("") is None
