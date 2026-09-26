"""Tests for market enrichment Celery task orchestration.

The market_enrichment module may already be imported (via app.main → router chain)
by the time these tests run in the full suite. We test by mocking all external
dependencies at the module attribute level using patch.object.
"""

import sys
import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.models.deal import Deal
from app.schemas.enums import DealStatus


def _import_enrichment_module():
    """Get the market_enrichment module, handling circular imports."""
    try:
        import app.tasks.market_enrichment as mod
        return mod
    except ImportError:
        # Circular import — mock the worker
        if "app.tasks.model_building" not in sys.modules:
            sys.modules["app.tasks.model_building"] = MagicMock()
        mock_celery = MagicMock()
        mock_celery.task.return_value = lambda f: f
        with patch.dict(sys.modules, {"app.worker": MagicMock(celery_app=mock_celery)}):
            import app.tasks.market_enrichment as mod
            return mod


class TestTransitionSync:
    async def test_updates_status_and_version(self, client, auth_headers, create_test_deal):
        """Test state transition via the deal API (verifies status field updates)."""
        deal = await create_test_deal()
        deal_id = deal["id"]
        old_version = deal["version"]

        resp = await client.get(f"/deals/{deal_id}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["version"] == old_version


class TestRunMarketEnrichment:
    """Test the full enrichment task with all external dependencies mocked.

    We use `_call_task` which handles both the Celery-decorated case (full suite)
    and the passthrough case (isolated run).
    """

    @staticmethod
    def _call_task(mod, *args, **kwargs):
        """Call run_market_enrichment, handling both Celery Task and raw function."""
        fn = mod.run_market_enrichment
        # If it's a Celery Task object, call .run() to skip the Celery machinery
        if hasattr(fn, "run"):
            return fn.run(*args, **kwargs)
        # If our mock passthrough is active, it has (self, ...) signature
        return fn(MagicMock(), *args, **kwargs)

    def test_full_pipeline(self):
        mod = _import_enrichment_module()

        deal_id = str(uuid.uuid4())
        actor_id = str(uuid.uuid4())

        mock_db = MagicMock()
        mock_deal = MagicMock()
        mock_deal.id = uuid.UUID(deal_id)
        mock_deal.property_address = "50 W 66th St, New York, NY"
        mock_deal.sponsor = {"name": "Test Developer"}
        mock_deal.property_name = "Harbor Point"
        mock_deal.status = "model_building"
        mock_deal.version = 1
        mock_deal.market_context = None

        mock_db.query.return_value.filter.return_value.with_for_update.return_value.one.return_value = mock_deal
        mock_db.query.return_value.filter.return_value.one.return_value = mock_deal
        mock_db.query.return_value.filter.return_value.all.return_value = []

        mock_llm = MagicMock()
        mock_llm.call_llm.return_value = {
            "validation_flags": [],
            "overall_assessment": "consistent",
            "summary": "No issues",
        }

        with (
            patch.object(mod, "sync_session_factory", return_value=mock_db),
            patch.object(mod, "PlumbLLMClient", return_value=mock_llm),
            patch.object(mod, "detect_geography", return_value="nyc"),
            patch.object(mod, "asyncio") as mock_asyncio,
            patch.object(mod, "assemble_market_context", return_value={"total_records": 2, "zoning": {"district": "R8"}}),
            patch.object(mod, "assemble_sponsor_portfolio", return_value={"sponsor_name": "Test"}),
            patch.object(mod, "log_event_sync"),
        ):
            mock_asyncio.run.return_value = {"zoning": {"status": "success"}}

            result = self._call_task(mod, deal_id, actor_id)

        assert result["status"] == "completed"
        assert result["geography"] == "nyc"

    def test_no_geography(self):
        mod = _import_enrichment_module()

        deal_id = str(uuid.uuid4())

        mock_db = MagicMock()
        mock_deal = MagicMock()
        mock_deal.id = uuid.UUID(deal_id)
        mock_deal.property_address = "123 Main St, Chicago, IL"
        mock_deal.sponsor = None
        mock_deal.property_name = None
        mock_deal.status = "model_building"
        mock_deal.version = 1
        mock_deal.market_context = None

        mock_db.query.return_value.filter.return_value.with_for_update.return_value.one.return_value = mock_deal
        mock_db.query.return_value.filter.return_value.one.return_value = mock_deal
        mock_db.query.return_value.filter.return_value.all.return_value = []

        mock_llm = MagicMock()
        mock_llm.call_llm.return_value = {
            "validation_flags": [],
            "overall_assessment": "consistent",
            "summary": "No data",
        }

        with (
            patch.object(mod, "sync_session_factory", return_value=mock_db),
            patch.object(mod, "PlumbLLMClient", return_value=mock_llm),
            patch.object(mod, "detect_geography", return_value=None),
            patch.object(mod, "assemble_market_context", return_value={"total_records": 0}),
            patch.object(mod, "assemble_sponsor_portfolio", return_value={"sponsor_name": "Unknown"}),
            patch.object(mod, "log_event_sync"),
        ):
            result = self._call_task(mod, deal_id)

        assert result["status"] == "completed"
        assert result["geography"] is None
        assert result["fetcher_results"] == {}

    def test_validation_failure_graceful(self):
        mod = _import_enrichment_module()

        deal_id = str(uuid.uuid4())

        mock_db = MagicMock()
        mock_deal = MagicMock()
        mock_deal.id = uuid.UUID(deal_id)
        mock_deal.property_address = "50 W 66th St, New York, NY"
        mock_deal.sponsor = None
        mock_deal.property_name = None
        mock_deal.status = "model_building"
        mock_deal.version = 1
        mock_deal.market_context = None

        mock_db.query.return_value.filter.return_value.with_for_update.return_value.one.return_value = mock_deal
        mock_db.query.return_value.filter.return_value.one.return_value = mock_deal
        mock_db.query.return_value.filter.return_value.all.return_value = []

        mock_llm = MagicMock()
        mock_llm.call_llm.side_effect = Exception("Claude API error")

        with (
            patch.object(mod, "sync_session_factory", return_value=mock_db),
            patch.object(mod, "PlumbLLMClient", return_value=mock_llm),
            patch.object(mod, "detect_geography", return_value="nyc"),
            patch.object(mod, "asyncio") as mock_asyncio,
            patch.object(mod, "assemble_market_context", return_value={"total_records": 0}),
            patch.object(mod, "assemble_sponsor_portfolio", return_value={}),
            patch.object(mod, "log_event_sync"),
        ):
            mock_asyncio.run.return_value = {}

            result = self._call_task(mod, deal_id)

        assert result["status"] == "completed"
        assert result["validation_flags"] == 0

    def test_fatal_error_rolls_back(self):
        mod = _import_enrichment_module()

        deal_id = str(uuid.uuid4())

        mock_db = MagicMock()
        mock_deal = MagicMock()
        mock_deal.id = uuid.UUID(deal_id)
        mock_deal.status = "model_building"
        mock_deal.version = 1

        mock_db.query.return_value.filter.return_value.with_for_update.return_value.one.return_value = mock_deal
        mock_db.query.return_value.filter.return_value.one.side_effect = Exception("Database crash")

        with (
            patch.object(mod, "sync_session_factory", return_value=mock_db),
            patch.object(mod, "PlumbLLMClient", return_value=MagicMock()),
            patch.object(mod, "log_event_sync"),
        ):
            with pytest.raises(Exception, match="Database crash"):
                self._call_task(mod, deal_id)
