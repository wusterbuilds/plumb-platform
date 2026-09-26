"""Base class for all public data fetchers with built-in caching."""

import json
import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy.orm import Session

from app.models.market import MarketData, PublicDataCache

logger = logging.getLogger(__name__)


@dataclass
class PublicDataResult:
    """Result from a public data fetch operation."""
    data_source: str
    data_type: str
    raw_data: str
    interpreted_data: dict | None = None
    source_url: str | None = None
    confidence_score: float = 1.0
    from_cache: bool = False
    error: str | None = None


class PublicDataFetcher(ABC):
    """Abstract base class for public data fetchers.

    All fetchers are async because they run concurrently via asyncio.gather()
    inside the market enrichment Celery task.
    """

    geography: str
    data_source: str
    data_type: str
    cache_ttl_days: int

    async def fetch_with_cache(
        self,
        cache_key: str,
        db: Session,
        client: httpx.AsyncClient,
        **kwargs,
    ) -> PublicDataResult:
        """Check cache first, then fetch if expired or missing."""
        now = datetime.now(timezone.utc)

        cached = (
            db.query(PublicDataCache)
            .filter(PublicDataCache.cache_key == cache_key)
            .first()
        )

        if cached and cached.expires_at.replace(tzinfo=timezone.utc) > now:
            logger.info("Cache hit for %s", cache_key)
            return PublicDataResult(
                data_source=self.data_source,
                data_type=self.data_type,
                raw_data=cached.raw_response or "",
                source_url=None,
                from_cache=True,
            )

        logger.info("Cache miss for %s, fetching live", cache_key)
        result = await self.fetch(client=client, **kwargs)

        if result.error is None:
            expires_at = now + timedelta(days=self.cache_ttl_days)
            if cached:
                cached.raw_response = result.raw_data
                cached.fetched_at = now
                cached.expires_at = expires_at
            else:
                db.add(PublicDataCache(
                    cache_key=cache_key,
                    data_source=self.data_source,
                    raw_response=result.raw_data,
                    fetched_at=now,
                    expires_at=expires_at,
                ))
            db.flush()

        return result

    @abstractmethod
    async def fetch(self, client: httpx.AsyncClient, **kwargs) -> PublicDataResult:
        """Fetch raw data from the external source."""
        ...

    @abstractmethod
    def interpret(self, raw_data: str, deal_context: dict, llm_client=None, db: Session | None = None, deal_id: uuid.UUID | None = None) -> dict:
        """Interpret raw fetched data into structured underwriting-relevant facts.

        For fetchers that don't need LLM (e.g. ZoLa/PLUTO), this is direct
        field mapping. For others, it calls an LLM interpretation prompt.
        """
        ...

    def save_market_data(
        self,
        db: Session,
        deal_id: uuid.UUID,
        result: PublicDataResult,
    ) -> MarketData:
        """Persist a fetcher result as a MarketData record."""
        now = datetime.now(timezone.utc)
        record = MarketData(
            deal_id=deal_id,
            data_source=result.data_source,
            data_type=result.data_type,
            data=result.interpreted_data,
            raw_data=result.raw_data,
            source_url=result.source_url,
            confidence_score=result.confidence_score,
            fetch_date=now,
            cache_expires_at=now + timedelta(days=self.cache_ttl_days) if self.cache_ttl_days else None,
        )
        db.add(record)
        db.flush()
        return record
