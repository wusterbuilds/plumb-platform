"""Tests for unified market context assembly."""

import uuid

from app.market.context import _build_section, _list_sources, assemble_market_context
from app.models.market import MarketData


# ===========================================================================
# _build_section unit tests (no DB)
# ===========================================================================


class TestBuildSection:
    def _make_record(self, data_source="test", data_type="test", data=None, confidence=0.9):
        rec = MarketData()
        rec.data_source = data_source
        rec.data_type = data_type
        rec.data = data or {}
        rec.confidence_score = confidence
        return rec

    def test_unavailable_when_missing(self):
        result = _build_section({}, "zoning")
        assert result == {"status": "unavailable"}

    def test_list_type_empty(self):
        result = _build_section({}, "news", as_list=True)
        assert result == []

    def test_single_record(self):
        rec = self._make_record(data={"key": "value"})
        result = _build_section({"test": [rec]}, "test")
        assert result["key"] == "value"
        assert result["_source"] == "test"
        assert result["_confidence"] == 0.9

    def test_merge_multiple(self):
        rec1 = self._make_record(data={"key1": "a"}, data_source="src1")
        rec2 = self._make_record(data={"key2": "b"}, data_source="src2")
        result = _build_section({"test": [rec1, rec2]}, "test")
        # Both keys should be present after merge
        assert "key1" in result
        assert "key2" in result

    def test_list_with_comparables(self):
        rec = self._make_record(data={
            "comparables": [
                {"address": "A", "price": 100},
                {"address": "B", "price": 200},
            ]
        }, data_source="costar")
        result = _build_section({"comps": [rec]}, "comps", as_list=True)
        assert len(result) == 2
        assert result[0]["_source"] == "costar"

    def test_list_with_articles(self):
        rec = self._make_record(data={
            "articles": [
                {"title": "News 1"},
                {"title": "News 2"},
            ]
        }, data_source="news")
        result = _build_section({"news": [rec]}, "news", as_list=True)
        assert len(result) == 2
        assert result[0]["_source"] == "news"


# ===========================================================================
# _list_sources unit tests (no DB)
# ===========================================================================


class TestListSources:
    def test_distinct_sources(self):
        rec1 = MarketData()
        rec1.data_source = "acris"
        rec1.data_type = "property_history"
        rec1.confidence_score = 0.9
        rec1.fetch_date = None
        rec1.source_url = "http://acris"

        rec2 = MarketData()
        rec2.data_source = "zola"
        rec2.data_type = "zoning"
        rec2.confidence_score = 0.95
        rec2.fetch_date = None
        rec2.source_url = "http://zola"

        result = _list_sources([rec1, rec2])
        assert len(result) == 2
        sources = {r["data_source"] for r in result}
        assert sources == {"acris", "zola"}

    def test_dedupes_same_source_type(self):
        rec1 = MarketData()
        rec1.data_source = "costar"
        rec1.data_type = "comps"
        rec1.confidence_score = 0.9
        rec1.fetch_date = None
        rec1.source_url = None

        rec2 = MarketData()
        rec2.data_source = "costar"
        rec2.data_type = "comps"
        rec2.confidence_score = 0.85
        rec2.fetch_date = None
        rec2.source_url = None

        result = _list_sources([rec1, rec2])
        assert len(result) == 1


# ===========================================================================
# assemble_market_context integration tests (real DB via API test session)
# ===========================================================================


class TestAssembleMarketContextDB:
    async def test_empty_deal(self, client, auth_headers, create_test_deal):
        """No market_data records → all sections unavailable/empty."""
        deal = await create_test_deal()
        deal_id = uuid.UUID(deal["id"])

        # Insert market data via API client to use test DB session
        # We don't insert any — just check the context
        resp = await client.get(f"/deals/{deal['id']}/market/status", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_records"] == 0
        for src in ["zola", "acris", "dob", "news", "ag_refb"]:
            assert data["fetchers"][src]["status"] == "pending"
