"""Tests for market intelligence API endpoints.

These tests use the async test DB session (via `client` fixture from conftest).
Data is inserted either via API calls or by directly using the async session.
"""

import uuid
from unittest.mock import MagicMock, patch

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.deal import Deal
from app.models.market import MarketData


@pytest_asyncio.fixture
async def test_db_session(test_engine):
    """Provides a raw async session bound to the test DB."""
    factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with factory() as session:
        yield session


class TestTriggerEnrichment:
    async def test_success(self, client, auth_headers, create_test_deal):
        deal = await create_test_deal()
        deal_id = deal["id"]

        # The import is lazy (inside the route handler), so we patch the module it imports from
        mock_task_fn = MagicMock()
        mock_task_result = MagicMock()
        mock_task_result.id = "celery-task-123"
        mock_task_fn.delay.return_value = mock_task_result

        with patch.dict("sys.modules", {
            "app.tasks.market_enrichment": MagicMock(run_market_enrichment=mock_task_fn),
        }):
            resp = await client.post(
                f"/deals/{deal_id}/market/enrich",
                headers=auth_headers,
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "started"
        assert data["task_id"] == "celery-task-123"

    async def test_bad_deal_returns_404(self, client, auth_headers):
        fake_id = uuid.uuid4()
        resp = await client.post(
            f"/deals/{fake_id}/market/enrich",
            headers=auth_headers,
        )
        assert resp.status_code == 404


class TestGetEnrichmentStatus:
    async def test_empty_status(self, client, auth_headers, create_test_deal):
        deal = await create_test_deal()
        deal_id = deal["id"]

        resp = await client.get(
            f"/deals/{deal_id}/market/status",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_records"] == 0
        for src in ["zola", "acris", "dob", "news", "ag_refb"]:
            assert data["fetchers"][src]["status"] == "pending"

    async def test_with_data(self, client, auth_headers, create_test_deal, test_db_session):
        deal = await create_test_deal()
        deal_id = deal["id"]

        # Insert market_data record via async session
        test_db_session.add(MarketData(
            deal_id=uuid.UUID(deal_id),
            data_source="zola",
            data_type="zoning",
            data={"zoning_district": "R8"},
            confidence_score=0.95,
        ))
        await test_db_session.commit()

        resp = await client.get(
            f"/deals/{deal_id}/market/status",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["fetchers"]["zola"]["status"] == "success"
        assert data["fetchers"]["acris"]["status"] == "pending"
        assert data["total_records"] == 1


class TestGetMarketContext:
    async def test_missing_context_returns_404(self, client, auth_headers, create_test_deal):
        deal = await create_test_deal()
        deal_id = deal["id"]

        resp = await client.get(
            f"/deals/{deal_id}/market/context",
            headers=auth_headers,
        )
        assert resp.status_code == 404

    async def test_populated_context(self, client, auth_headers, create_test_deal, test_db_session):
        deal = await create_test_deal()
        deal_id = deal["id"]

        # Set market_context directly on the deal
        from sqlalchemy import update
        await test_db_session.execute(
            update(Deal)
            .where(Deal.id == uuid.UUID(deal_id))
            .values(market_context={"zoning": {"district": "R8"}, "assembled_at": "2024-01-01"})
        )
        await test_db_session.commit()

        resp = await client.get(
            f"/deals/{deal_id}/market/context",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["zoning"]["district"] == "R8"


class TestListMarketData:
    async def test_list_all(self, client, auth_headers, create_test_deal, test_db_session):
        deal = await create_test_deal()
        deal_id = deal["id"]

        for src, dtype in [("acris", "property_history"), ("zola", "zoning"), ("dob", "permits")]:
            test_db_session.add(MarketData(
                deal_id=uuid.UUID(deal_id),
                data_source=src,
                data_type=dtype,
                data={"test": True},
                confidence_score=0.9,
            ))
        await test_db_session.commit()

        resp = await client.get(
            f"/deals/{deal_id}/market/data",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3

    async def test_filter_by_source(self, client, auth_headers, create_test_deal, test_db_session):
        deal = await create_test_deal()
        deal_id = deal["id"]

        test_db_session.add(MarketData(deal_id=uuid.UUID(deal_id), data_source="acris", data_type="property_history", data={}, confidence_score=0.9))
        test_db_session.add(MarketData(deal_id=uuid.UUID(deal_id), data_source="zola", data_type="zoning", data={}, confidence_score=0.9))
        await test_db_session.commit()

        resp = await client.get(
            f"/deals/{deal_id}/market/data?data_source=acris",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["records"][0]["data_source"] == "acris"


class TestImportMarketData:
    async def test_import_costar_csv(self, client, auth_headers, create_test_deal, costar_comp_csv_bytes):
        deal = await create_test_deal()
        deal_id = deal["id"]

        resp = await client.post(
            f"/deals/{deal_id}/market/import",
            headers=auth_headers,
            files={"file": ("costar_comp_export.csv", costar_comp_csv_bytes, "text/csv")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "imported"
        assert data["importer"] == "costar"
        assert data["records_imported"] == 3

    async def test_unknown_format_returns_422(self, client, auth_headers, create_test_deal):
        deal = await create_test_deal()
        deal_id = deal["id"]

        resp = await client.post(
            f"/deals/{deal_id}/market/import",
            headers=auth_headers,
            files={"file": ("random.txt", b"not a real format", "text/plain")},
        )
        assert resp.status_code == 422


class TestGetValidation:
    async def test_missing_context_returns_404(self, client, auth_headers, create_test_deal):
        deal = await create_test_deal()
        resp = await client.get(
            f"/deals/{deal['id']}/market/validation",
            headers=auth_headers,
        )
        assert resp.status_code == 404

    async def test_populated_validation(self, client, auth_headers, create_test_deal, test_db_session):
        deal = await create_test_deal()
        deal_id = deal["id"]

        from sqlalchemy import update
        await test_db_session.execute(
            update(Deal)
            .where(Deal.id == uuid.UUID(deal_id))
            .values(market_context={
                "validation_flags": [
                    {
                        "field": "sellout_ppsf",
                        "borrower_value": "$2,200",
                        "market_value": "$1,800",
                        "severity": "warning",
                        "explanation": "Borrower PPSF 22% above market average",
                    }
                ],
                "overall_assessment": "minor_discrepancies",
                "validation_summary": "One material flag on sellout pricing",
            })
        )
        await test_db_session.commit()

        resp = await client.get(
            f"/deals/{deal_id}/market/validation",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["flags"]) == 1
        assert data["flags"][0]["severity"] == "warning"
        assert data["overall_assessment"] == "minor_discrepancies"


class TestAuthRequired:
    async def test_no_auth_returns_401(self, client, create_test_deal, auth_headers):
        deal = await create_test_deal()
        deal_id = deal["id"]

        endpoints = [
            ("GET", f"/deals/{deal_id}/market/status"),
            ("GET", f"/deals/{deal_id}/market/context"),
            ("GET", f"/deals/{deal_id}/market/data"),
            ("GET", f"/deals/{deal_id}/market/validation"),
            ("POST", f"/deals/{deal_id}/market/enrich"),
        ]
        for method, url in endpoints:
            if method == "GET":
                resp = await client.get(url)
            else:
                resp = await client.post(url)
            assert resp.status_code in (401, 403), f"{method} {url} returned {resp.status_code}"
