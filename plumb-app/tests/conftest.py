import os
import uuid
from unittest.mock import patch

import asyncpg
import pytest
import httpx
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.session import get_db
from app.main import app

DB_USER = os.getenv("PLUMB_TEST_DB_USER", "plumb")
DB_PASSWORD = os.getenv("PLUMB_TEST_DB_PASSWORD", "plumb_dev")
DB_HOST = os.getenv("PLUMB_TEST_DB_HOST", "localhost")
DB_PORT = int(os.getenv("PLUMB_TEST_DB_PORT", "5432"))
DB_NAME = os.getenv("PLUMB_TEST_DB_NAME", "plumb")
TEST_DB_NAME = os.getenv("PLUMB_TEST_DATABASE", "plumb_test")
TEST_DATABASE_URL = (
    f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{TEST_DB_NAME}"
)


@pytest.fixture(autouse=True)
def disable_background_jobs():
    """Keep API and task tests deterministic; workers are integration concerns."""
    with (
        patch("app.tasks.pipeline.run_deal_pipeline.delay"),
        patch("app.tasks.market_enrichment.run_market_enrichment.delay"),
        patch("app.tasks.model_building.run_model_building.delay"),
    ):
        yield


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def test_engine():
    # Create test database if it doesn't exist
    conn = await asyncpg.connect(
        user=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
    )
    exists = await conn.fetchval(
        "SELECT 1 FROM pg_database WHERE datname = $1", TEST_DB_NAME
    )
    if not exists:
        safe_name = TEST_DB_NAME.replace('"', '""')
        await conn.execute(f'CREATE DATABASE "{safe_name}"')
    await conn.close()

    engine = create_async_engine(TEST_DATABASE_URL, echo=False, pool_size=5)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture(autouse=True)
async def cleanup_db(test_engine):
    """Truncate all tables after each test."""
    yield
    # Use a raw asyncpg connection for cleanup to avoid SQLAlchemy session state issues
    conn = await asyncpg.connect(
        user=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT,
        database=TEST_DB_NAME,
    )
    try:
        table_names = ", ".join(f'"{t.name}"' for t in reversed(Base.metadata.sorted_tables))
        if table_names:
            await conn.execute(f"TRUNCATE {table_names} CASCADE")
    finally:
        await conn.close()


@pytest_asyncio.fixture
async def client(test_engine):
    test_session_factory = async_sessionmaker(test_engine, expire_on_commit=False)

    async def override_get_db():
        async with test_session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def auth_headers(client: httpx.AsyncClient) -> dict:
    """Register a test user and return Bearer token headers."""
    email = f"test_{uuid.uuid4().hex[:8]}@example.com"
    await client.post(
        "/auth/register",
        json={"email": email, "name": "Test User", "password": "testpassword123"},
    )
    resp = await client.post(
        "/auth/login",
        json={"email": email, "password": "testpassword123"},
    )
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def create_test_deal(client: httpx.AsyncClient, auth_headers: dict):
    """Factory fixture to create test deals via API."""

    async def _create(**kwargs):
        data = {
            "deal_type": "construction_loan",
            "property_address": "123 Test St, New York, NY",
            **kwargs,
        }
        resp = await client.post("/deals", json=data, headers=auth_headers)
        assert resp.status_code == 201
        return resp.json()

    return _create
