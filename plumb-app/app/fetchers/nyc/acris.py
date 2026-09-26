"""ACRIS fetcher — property transaction history via Socrata SODA API.

Three-table join: Legals (by BBL) -> Master (document details) -> Parties.
Queries use separate borough/block/lot columns with zero-padding.
Covers Manhattan, Queens, Bronx, Brooklyn (not Staten Island).
"""

import json
import logging
import uuid

import httpx
from sqlalchemy.orm import Session

from app.config import settings
from app.fetchers.base import PublicDataFetcher, PublicDataResult
from app.fetchers.nyc.geoclient import GeoResult

logger = logging.getLogger(__name__)

ACRIS_LEGALS = "https://data.cityofnewyork.us/resource/8h5j-fqxa.json"
ACRIS_MASTER = "https://data.cityofnewyork.us/resource/bnx9-e6tj.json"
ACRIS_PARTIES = "https://data.cityofnewyork.us/resource/636b-3b5g.json"

DOC_TYPE_FILTER = "DEED', 'MTGE', 'AGMT', 'RPTT', 'ASST', 'SAT"


class ACRISFetcher(PublicDataFetcher):
    geography = "nyc"
    data_source = "acris"
    data_type = "property_history"
    cache_ttl_days = 30

    async def fetch(self, client: httpx.AsyncClient, geo: GeoResult | None = None, **kwargs) -> PublicDataResult:
        if geo is None:
            return PublicDataResult(
                data_source=self.data_source,
                data_type=self.data_type,
                raw_data="",
                error="No GeoResult provided",
            )

        headers = {}
        if settings.SOCRATA_APP_TOKEN:
            headers["X-App-Token"] = settings.SOCRATA_APP_TOKEN

        try:
            legals_where = (
                f"borough={geo.borough} AND block='{geo.block}' AND lot='{geo.lot}'"
            )
            resp_legals = await client.get(
                ACRIS_LEGALS,
                params={
                    "$where": legals_where,
                    "$order": "good_through_date DESC",
                    "$limit": "50",
                },
                headers=headers,
            )
            resp_legals.raise_for_status()
            legals = resp_legals.json()

            if not legals:
                return PublicDataResult(
                    data_source=self.data_source,
                    data_type=self.data_type,
                    raw_data="[]",
                    source_url=f"{ACRIS_LEGALS}?$where={legals_where}",
                    error=f"No ACRIS legals found for BBL {geo.bbl}",
                )

            doc_ids = list({r["document_id"] for r in legals if "document_id" in r})

            masters = []
            parties = []
            batch_size = 20
            for i in range(0, len(doc_ids), batch_size):
                batch = doc_ids[i : i + batch_size]
                id_list = ", ".join(f"'{d}'" for d in batch)

                master_resp = await client.get(
                    ACRIS_MASTER,
                    params={
                        "$where": f"document_id in ({id_list})",
                        "$limit": "200",
                    },
                    headers=headers,
                )
                master_resp.raise_for_status()
                masters.extend(master_resp.json())

                party_resp = await client.get(
                    ACRIS_PARTIES,
                    params={
                        "$where": f"document_id in ({id_list})",
                        "$limit": "500",
                    },
                    headers=headers,
                )
                party_resp.raise_for_status()
                parties.extend(party_resp.json())

            combined = {
                "legals": legals,
                "masters": masters,
                "parties": parties,
            }
            raw = json.dumps(combined, indent=2)

            return PublicDataResult(
                data_source=self.data_source,
                data_type=self.data_type,
                raw_data=raw,
                source_url=f"{ACRIS_LEGALS}?$where={legals_where}",
            )

        except httpx.HTTPError as exc:
            logger.error("ACRIS fetch failed for BBL %s: %s", geo.bbl, exc)
            return PublicDataResult(
                data_source=self.data_source,
                data_type=self.data_type,
                raw_data="",
                error=str(exc),
            )

    def interpret(self, raw_data: str, deal_context: dict, llm_client=None, db: Session | None = None, deal_id: uuid.UUID | None = None) -> dict:
        """LLM interprets raw ACRIS records into underwriting-relevant facts."""
        if not raw_data or raw_data == "[]":
            return {}

        if llm_client is None:
            return {"raw_record_count": len(json.loads(raw_data).get("legals", []))}

        result = llm_client.call_llm(
            "interpret_acris",
            deal_context,
            {"acris_records": raw_data},
            db=db,
            deal_id=deal_id,
        )
        return result
