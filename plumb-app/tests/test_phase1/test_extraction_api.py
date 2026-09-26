"""Tests for extraction API endpoints.

These tests use mocked dependencies — no real DB or LLM calls needed.
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
def mock_user():
    user = MagicMock()
    user.id = uuid.uuid4()
    user.email = "test@plumb.com"
    user.name = "Test User"
    user.role = "analyst"
    return user


@pytest.fixture
def mock_db():
    db = AsyncMock()
    return db


@pytest.fixture
async def client(mock_user, mock_db):
    from app.auth.deps import get_current_user
    from app.db.session import get_db

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_db] = lambda: mock_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as c:
        yield c

    app.dependency_overrides.clear()


class TestStartExtraction:
    async def test_start_returns_202(self, client, mock_db):
        deal_id = uuid.uuid4()

        # Mock deal lookup
        mock_deal = MagicMock()
        mock_deal.id = deal_id
        mock_deal.status = "docs_received"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_deal
        mock_db.execute = AsyncMock(side_effect=[
            mock_result,  # deal lookup
            MagicMock(scalar=MagicMock(return_value=3)),  # doc count
        ])

        with (
            patch("app.agent.feature_flags.is_enabled", return_value=False),
            patch("app.tasks.pipeline.run_deal_pipeline") as mock_pipeline,
        ):
            mock_task = MagicMock()
            mock_task.id = "task-123"
            mock_pipeline.delay.return_value = mock_task

            response = await client.post(f"/deals/{deal_id}/extraction/start")

        assert response.status_code == 202
        data = response.json()
        assert data["task_id"] == "task-123"
        assert data["deal_id"] == str(deal_id)

    async def test_start_rejects_wrong_state(self, client, mock_db):
        deal_id = uuid.uuid4()

        mock_deal = MagicMock()
        mock_deal.id = deal_id
        mock_deal.status = "extraction_review"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_deal
        mock_db.execute = AsyncMock(return_value=mock_result)

        response = await client.post(f"/deals/{deal_id}/extraction/start")
        assert response.status_code == 422

    async def test_start_rejects_no_docs(self, client, mock_db):
        deal_id = uuid.uuid4()

        mock_deal = MagicMock()
        mock_deal.id = deal_id
        mock_deal.status = "docs_received"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_deal
        mock_db.execute = AsyncMock(side_effect=[
            mock_result,
            MagicMock(scalar=MagicMock(return_value=0)),
        ])

        response = await client.post(f"/deals/{deal_id}/extraction/start")
        assert response.status_code == 422
        assert "No documents" in response.json()["detail"]

    async def test_start_404_missing_deal(self, client, mock_db):
        deal_id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        response = await client.post(f"/deals/{deal_id}/extraction/start")
        assert response.status_code == 404
