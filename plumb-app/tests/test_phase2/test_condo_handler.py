"""Tests for condo sellout market handler."""

from app.market.handlers.condo_sellout import CondoSelloutHandler


class TestBuildMarketAnalysis:
    def setup_method(self):
        self.handler = CondoSelloutHandler()

    def test_full_context(self):
        ctx = {
            "comps": [
                {"property_type": "condo", "price_per_sf": "$1800", "address": "100 W 66th"},
                {"property_type": "condo", "price_per_sf": "$2200", "address": "200 W 66th"},
            ],
            "market_stats": {
                "vacancy_rate": "4.1%",
                "asking_rent": "$72.00",
                "net_absorption": "85000",
                "under_construction_sf": "500000",
            },
            "zoning": {
                "zoning_district": "R8",
                "residential_far": "6.02",
                "lot_area_sf": "15000",
            },
            "permits": {
                "active_permits": [{"permit_type": "NB"}],
                "material_flags": ["Stop work order"],
            },
            "offering_plan": {"status": "accepted"},
            "sponsor_portfolio": {
                "verified_projects": [{"project": "Tower A"}],
                "unverified_claims": ["Tower B"],
                "violation_history": {"total_violations": 3},
            },
            "news": [
                {"relevance": "material", "title": "Lawsuit filed"},
                {"relevance": "contextual", "title": "New tower announced"},
                {"relevance": "irrelevant", "title": "Unrelated"},
            ],
        }

        analysis = self.handler.build_market_analysis(ctx)

        assert analysis["sellout_comps"]["count"] == 2
        assert analysis["sellout_comps"]["avg_ppsf"] == "$2,000"
        assert analysis["market_conditions"]["vacancy_rate"] == "4.1%"
        assert analysis["supply_pipeline"]["under_construction"] == "500000"
        assert analysis["zoning_summary"]["district"] == "R8"
        assert analysis["permit_status"]["active_permits"] == 1
        assert analysis["permit_status"]["material_flags"] == ["Stop work order"]
        assert analysis["offering_plan_status"] == "accepted"
        assert analysis["sponsor_track_record"]["verified_projects"] == 1
        assert analysis["news_summary"]["material_count"] == 1
        assert analysis["news_summary"]["total_count"] == 3

    def test_empty_context(self):
        analysis = self.handler.build_market_analysis({})

        assert analysis["sellout_comps"]["count"] == 0
        # Empty dict {} doesn't have status="unavailable", so _summarize_market returns N/A fields
        assert analysis["market_conditions"]["vacancy_rate"] == "N/A"
        assert analysis["supply_pipeline"]["under_construction"] == "N/A"
        assert analysis["zoning_summary"]["district"] == "N/A"
        assert analysis["permit_status"]["active_permits"] == 0
        assert analysis["offering_plan_status"] == "unknown"
        assert analysis["news_summary"]["material_count"] == 0


class TestFilterSelloutComps:
    def setup_method(self):
        self.handler = CondoSelloutHandler()

    def test_filters_by_property_type(self):
        comps = [
            {"property_type": "condo", "address": "A"},
            {"property_type": "office", "address": "B"},
            {"property_type": "new development", "address": "C"},
        ]
        result = self.handler._filter_sellout_comps(comps)
        assert len(result) == 2
        assert result[0]["address"] == "A"
        assert result[1]["address"] == "C"

    def test_includes_ppsf_without_type(self):
        comps = [
            {"address": "A", "price_per_sf": "$1500"},
            {"address": "B"},
        ]
        result = self.handler._filter_sellout_comps(comps)
        assert len(result) == 1
        assert result[0]["address"] == "A"

    def test_fallback_when_no_match(self):
        comps = [
            {"property_type": "industrial", "address": "A"},
            {"property_type": "retail", "address": "B"},
        ]
        result = self.handler._filter_sellout_comps(comps)
        # Falls back to first 10 comps
        assert len(result) == 2


class TestAvgPPSF:
    def setup_method(self):
        self.handler = CondoSelloutHandler()

    def test_average_calculation(self):
        comps = [
            {"price_per_sf": "$1,500"},
            {"price_per_sf": "$2,000"},
        ]
        assert self.handler._avg_ppsf(comps) == "$1,750"

    def test_empty_returns_none(self):
        assert self.handler._avg_ppsf([]) is None

    def test_unparseable_values_skipped(self):
        comps = [
            {"price_per_sf": "N/A"},
            {"price_per_sf": "$1,000"},
        ]
        assert self.handler._avg_ppsf(comps) == "$1,000"


class TestRangePPSF:
    def setup_method(self):
        self.handler = CondoSelloutHandler()

    def test_range_calculation(self):
        comps = [
            {"price_per_sf": "$1,200"},
            {"price_per_sf": "$1,800"},
            {"price_per_sf": "$2,400"},
        ]
        assert self.handler._range_ppsf(comps) == "$1,200 - $2,400"

    def test_single_value(self):
        comps = [{"price_per_sf": "$1,500"}]
        assert self.handler._range_ppsf(comps) == "$1,500 - $1,500"

    def test_empty_returns_none(self):
        assert self.handler._range_ppsf([]) is None


class TestSummarizeMarket:
    def setup_method(self):
        self.handler = CondoSelloutHandler()

    def test_unavailable(self):
        result = self.handler._summarize_market({"status": "unavailable"})
        assert result == {"status": "unavailable"}

    def test_with_data(self):
        result = self.handler._summarize_market({
            "vacancy_rate": "5%",
            "asking_rent": "$80",
            "net_absorption": "100000",
        })
        assert result["vacancy_rate"] == "5%"
        assert result["asking_rent"] == "$80"
