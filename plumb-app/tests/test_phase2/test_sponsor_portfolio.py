"""Tests for sponsor portfolio assembly and cross-referencing."""

from app.market.sponsor_portfolio import (
    _cross_reference_projects,
    _extract_acris_properties,
    _extract_ag_filings,
    _extract_dob_portfolio,
    _extract_news_mentions,
)


class TestExtractACRISProperties:
    def test_ownership_chain_to_properties(self):
        records = [
            {
                "ownership_chain": [
                    {"address": "50 W 66th St", "date": "2024-01-01"},
                    {"address": "100 Broadway", "date": "2023-06-15"},
                ]
            }
        ]
        result = _extract_acris_properties(records)
        assert len(result) == 2
        assert result[0]["address"] == "50 W 66th St"
        assert result[0]["source"] == "acris"

    def test_empty_chain(self):
        records = [{"ownership_chain": []}]
        assert _extract_acris_properties(records) == []

    def test_missing_address_defaults(self):
        records = [{"ownership_chain": [{"date": "2024-01-01"}]}]
        result = _extract_acris_properties(records)
        assert result[0]["address"] == "subject property"


class TestExtractDOBPortfolio:
    def test_aggregates_violations(self):
        records = [
            {
                "sponsor_portfolio_violations": {
                    "total_violations": 5,
                    "open_violations": 2,
                    "properties_with_violations": 3,
                    "total_penalties": "$15,000",
                }
            },
            {
                "sponsor_portfolio_violations": {
                    "total_violations": 3,
                    "open_violations": 1,
                    "properties_with_violations": 2,
                    "total_penalties": "$8,500",
                }
            },
        ]
        result = _extract_dob_portfolio(records)
        assert result["total_violations"] == 8
        assert result["open_violations"] == 3
        assert result["properties_with_violations"] == 5
        assert result["total_penalties"] == "$23,500"

    def test_empty_records(self):
        result = _extract_dob_portfolio([])
        assert result["total_violations"] == 0
        assert result["total_penalties"] == "$0"

    def test_penalty_parsing_formats(self):
        records = [
            {
                "sponsor_portfolio_violations": {
                    "total_violations": 1,
                    "open_violations": 0,
                    "properties_with_violations": 1,
                    "total_penalties": "2500",  # No $ sign
                }
            }
        ]
        result = _extract_dob_portfolio(records)
        assert result["total_penalties"] == "$2,500"


class TestExtractAGFilings:
    def test_merges_plans_and_sponsor_filings(self):
        records = [
            {
                "offering_plans": [
                    {"plan_id": "P001", "status": "accepted"},
                ],
                "sponsor_other_filings": [
                    {"plan_id": "P002", "status": "pending"},
                ],
            }
        ]
        result = _extract_ag_filings(records)
        assert len(result) == 2
        assert result[0]["plan_id"] == "P001"
        assert result[1]["plan_id"] == "P002"

    def test_empty(self):
        assert _extract_ag_filings([]) == []
        assert _extract_ag_filings([{}]) == []


class TestExtractNewsMentions:
    def test_filters_material_and_contextual(self):
        records = [
            {
                "articles": [
                    {"relevance": "material", "title": "Lawsuit"},
                    {"relevance": "contextual", "title": "Announcement"},
                    {"relevance": "irrelevant", "title": "Unrelated"},
                ]
            }
        ]
        result = _extract_news_mentions(records)
        assert len(result) == 2
        assert result[0]["title"] == "Lawsuit"
        assert result[1]["title"] == "Announcement"

    def test_empty(self):
        assert _extract_news_mentions([]) == []
        assert _extract_news_mentions([{"articles": []}]) == []


class TestCrossReferenceProjects:
    def test_match_by_address(self):
        claimed = [{"name": "Tower A", "address": "50 W 66th St"}]
        acris_props = [{"address": "50 w 66th st"}]
        ag_filings = []
        verified, unverified = _cross_reference_projects(claimed, acris_props, ag_filings)
        assert len(verified) == 1
        assert verified[0]["verification"] == "address_match"
        assert unverified == []

    def test_match_by_name(self):
        claimed = [{"name": "harbor point", "address": ""}]
        acris_props = []
        ag_filings = [{"address": "harbor point"}]
        verified, unverified = _cross_reference_projects(claimed, acris_props, ag_filings)
        assert len(verified) == 1
        assert verified[0]["verification"] == "name_match"

    def test_no_match(self):
        claimed = [{"name": "Unknown Project", "address": "999 Nowhere St"}]
        acris_props = [{"address": "50 w 66th st"}]
        ag_filings = []
        verified, unverified = _cross_reference_projects(claimed, acris_props, ag_filings)
        assert verified == []
        assert len(unverified) == 1

    def test_string_claimed_projects(self):
        claimed = ["50 W 66th St Project"]
        acris_props = [{"address": "50 w 66th st project"}]
        ag_filings = []
        verified, unverified = _cross_reference_projects(claimed, acris_props, ag_filings)
        assert len(verified) == 1

    def test_empty_claims(self):
        verified, unverified = _cross_reference_projects([], [], [])
        assert verified == []
        assert unverified == []
