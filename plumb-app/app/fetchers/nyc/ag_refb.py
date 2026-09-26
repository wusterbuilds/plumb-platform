"""NY Attorney General Real Estate Finance Bureau fetcher.

Scrapes the AG's offering plan database at
offeringplandatasearch.ag.ny.gov. Falls back to a manual verification
link if scraping fails (session-based JSP app, inherently fragile).
"""

import json
import logging
import uuid
from urllib.parse import urljoin

import httpx
from sqlalchemy.orm import Session

from app.fetchers.base import PublicDataFetcher, PublicDataResult

logger = logging.getLogger(__name__)

AG_REFB_BASE = "https://offeringplandatasearch.ag.ny.gov"
AG_REFB_WELCOME = f"{AG_REFB_BASE}/REF/welcome.jsp"
AG_REFB_SEARCH_NAME = f"{AG_REFB_BASE}/REF/planSearchName.jsp"
AG_REFB_SEARCH_SPONSOR = f"{AG_REFB_BASE}/REF/planSearchSponsor.jsp"


class AGREFBFetcher(PublicDataFetcher):
    geography = "nyc"
    data_source = "ag_refb"
    data_type = "offering_plan"
    cache_ttl_days = 30

    async def fetch(
        self,
        client: httpx.AsyncClient,
        property_address: str | None = None,
        sponsor_name: str | None = None,
        **kwargs,
    ) -> PublicDataResult:
        results = {
            "address_search": None,
            "sponsor_search": None,
            "manual_verification_url": AG_REFB_WELCOME,
        }

        try:
            session_resp = await client.get(AG_REFB_WELCOME, follow_redirects=True)
            session_resp.raise_for_status()
            cookies = session_resp.cookies

            if property_address:
                try:
                    addr_resp = await client.post(
                        AG_REFB_SEARCH_NAME,
                        data={"planName": property_address},
                        cookies=cookies,
                        follow_redirects=True,
                    )
                    addr_resp.raise_for_status()
                    results["address_search"] = self._parse_results_html(addr_resp.text)
                except Exception as exc:
                    logger.warning("AG REFB address search failed: %s", exc)
                    results["address_search_error"] = str(exc)

            if sponsor_name:
                try:
                    sponsor_resp = await client.post(
                        AG_REFB_SEARCH_SPONSOR,
                        data={"sponsorName": sponsor_name},
                        cookies=cookies,
                        follow_redirects=True,
                    )
                    sponsor_resp.raise_for_status()
                    results["sponsor_search"] = self._parse_results_html(sponsor_resp.text)
                except Exception as exc:
                    logger.warning("AG REFB sponsor search failed: %s", exc)
                    results["sponsor_search_error"] = str(exc)

            raw = json.dumps(results, indent=2)
            has_data = results["address_search"] or results["sponsor_search"]
            return PublicDataResult(
                data_source=self.data_source,
                data_type=self.data_type,
                raw_data=raw,
                source_url=AG_REFB_WELCOME,
                error=None if has_data else "No results from AG REFB scraping",
            )

        except Exception as exc:
            logger.error("AG REFB session/fetch failed: %s", exc)
            fallback = {
                "status": "manual_verification_needed",
                "search_url": AG_REFB_WELCOME,
                "search_instructions": (
                    f"Search for sponsor '{sponsor_name or 'N/A'}' "
                    f"or address '{property_address or 'N/A'}'"
                ),
            }
            return PublicDataResult(
                data_source=self.data_source,
                data_type=self.data_type,
                raw_data=json.dumps(fallback),
                source_url=AG_REFB_WELCOME,
                error=f"Scraping failed, manual verification needed: {exc}",
            )

    def _parse_results_html(self, html: str) -> list[dict]:
        """Parse AG REFB search results HTML into structured records.

        Uses BeautifulSoup if available, falls back to basic extraction.
        """
        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(html, "html.parser")
            rows = soup.select("table tr")
            records = []
            headers = []

            for row in rows:
                cells = row.find_all(["th", "td"])
                if not cells:
                    continue
                if row.find("th"):
                    headers = [c.get_text(strip=True).lower().replace(" ", "_") for c in cells]
                    continue
                if headers:
                    record = {}
                    for i, cell in enumerate(cells):
                        if i < len(headers):
                            record[headers[i]] = cell.get_text(strip=True)
                    if record:
                        records.append(record)

            return records
        except ImportError:
            logger.warning("beautifulsoup4 not installed, returning raw HTML length")
            return [{"raw_html_length": len(html), "parse_error": "beautifulsoup4 not installed"}]

    def interpret(self, raw_data: str, deal_context: dict, llm_client=None, db: Session | None = None, deal_id: uuid.UUID | None = None) -> dict:
        """LLM interprets AG REFB results for underwriting relevance."""
        if not raw_data:
            return {}

        parsed = json.loads(raw_data)
        if parsed.get("status") == "manual_verification_needed":
            return parsed

        if llm_client is None:
            return {
                "address_results": parsed.get("address_search") or [],
                "sponsor_results": parsed.get("sponsor_search") or [],
                "manual_verification_url": parsed.get("manual_verification_url"),
            }

        result = llm_client.call_llm(
            "interpret_ag_refb",
            deal_context,
            {"ag_refb_data": raw_data},
            db=db,
            deal_id=deal_id,
        )
        result["manual_verification_url"] = parsed.get("manual_verification_url")
        return result
