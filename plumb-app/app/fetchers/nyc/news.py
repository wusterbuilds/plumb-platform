"""News search fetcher — Brave Search API for CRE trade press.

Runs multiple search queries in parallel targeting TRD, Crain's,
Commercial Observer, and Bisnow.
"""

import json
import logging
import uuid

import httpx
from sqlalchemy.orm import Session

from app.config import settings
from app.fetchers.base import PublicDataFetcher, PublicDataResult

logger = logging.getLogger(__name__)

BRAVE_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"

CRE_SITES = "site:therealdeal.com OR site:commercialobserver.com OR site:crainsnewyork.com OR site:bisnow.com"


class NewsSearchFetcher(PublicDataFetcher):
    geography = "nyc"
    data_source = "news"
    data_type = "news"
    cache_ttl_days = 7

    async def fetch(
        self,
        client: httpx.AsyncClient,
        property_address: str | None = None,
        developer_name: str | None = None,
        project_name: str | None = None,
        **kwargs,
    ) -> PublicDataResult:
        if not settings.BRAVE_API_KEY:
            return PublicDataResult(
                data_source=self.data_source,
                data_type=self.data_type,
                raw_data="",
                error="BRAVE_API_KEY not configured",
            )

        queries = []
        if property_address:
            queries.append(f'"{property_address}" {CRE_SITES}')
        if developer_name:
            queries.append(f'"{developer_name}" real estate NYC developer')
        if project_name:
            queries.append(f'"{project_name}" construction condo')

        if not queries:
            return PublicDataResult(
                data_source=self.data_source,
                data_type=self.data_type,
                raw_data="[]",
                error="No search terms provided",
            )

        headers = {
            "X-Subscription-Token": settings.BRAVE_API_KEY,
            "Accept": "application/json",
        }

        all_results = []
        for query in queries:
            try:
                resp = await client.get(
                    BRAVE_SEARCH_URL,
                    params={"q": query, "count": 10},
                    headers=headers,
                )
                resp.raise_for_status()
                data = resp.json()
                web_results = data.get("web", {}).get("results", [])
                for r in web_results:
                    all_results.append({
                        "title": r.get("title", ""),
                        "url": r.get("url", ""),
                        "description": r.get("description", ""),
                        "age": r.get("age", ""),
                        "query": query,
                    })
            except httpx.HTTPError as exc:
                logger.error("Brave Search failed for query '%s': %s", query, exc)

        seen_urls: set[str] = set()
        deduped = []
        for r in all_results:
            if r["url"] not in seen_urls:
                seen_urls.add(r["url"])
                deduped.append(r)

        raw = json.dumps(deduped, indent=2)
        return PublicDataResult(
            data_source=self.data_source,
            data_type=self.data_type,
            raw_data=raw,
            source_url=BRAVE_SEARCH_URL,
        )

    def interpret(self, raw_data: str, deal_context: dict, llm_client=None, db: Session | None = None, deal_id: uuid.UUID | None = None) -> dict:
        """LLM classifies each result as material/contextual/irrelevant."""
        if not raw_data or raw_data == "[]":
            return {"articles": []}

        if llm_client is None:
            results = json.loads(raw_data)
            return {"articles": results, "total_results": len(results)}

        result = llm_client.call_llm(
            "interpret_news",
            deal_context,
            {"search_results": raw_data},
            db=db,
            deal_id=deal_id,
        )
        return result
