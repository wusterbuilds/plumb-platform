"""DOB fetcher — permits, violations, and complaints via Socrata SODA API.

All queries use BIN (from GeoSearch), not BBL.
Also searches by developer/respondent name for portfolio-wide history.
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

DOB_JOB_FILINGS = "https://data.cityofnewyork.us/resource/w9ak-ipjd.json"
DOB_APPROVED_PERMITS = "https://data.cityofnewyork.us/resource/rbx6-tga4.json"
DOB_ECB_VIOLATIONS = "https://data.cityofnewyork.us/resource/6bgk-3dad.json"
DOB_PERMIT_ISSUANCE = "https://data.cityofnewyork.us/resource/ipu4-2q9a.json"


class DOBFetcher(PublicDataFetcher):
    geography = "nyc"
    data_source = "dob"
    data_type = "permits"
    cache_ttl_days = 7

    async def fetch(
        self,
        client: httpx.AsyncClient,
        geo: GeoResult | None = None,
        sponsor_name: str | None = None,
        **kwargs,
    ) -> PublicDataResult:
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
            job_filings_resp = await client.get(
                DOB_JOB_FILINGS,
                params={
                    "$where": f"bin='{geo.bin}'",
                    "$order": "filing_date DESC" if "filing_date" in "" else "",
                    "$limit": "50",
                },
                headers=headers,
            )
            job_filings_resp.raise_for_status()
            job_filings = job_filings_resp.json()

            violations_resp = await client.get(
                DOB_ECB_VIOLATIONS,
                params={
                    "$where": f"bin='{geo.bin}'",
                    "$limit": "100",
                },
                headers=headers,
            )
            violations_resp.raise_for_status()
            violations = violations_resp.json()

            permits_resp = await client.get(
                DOB_APPROVED_PERMITS,
                params={
                    "$where": f"bin='{geo.bin}'",
                    "$limit": "50",
                },
                headers=headers,
            )
            permits_resp.raise_for_status()
            permits = permits_resp.json()

            sponsor_violations = []
            if sponsor_name:
                escaped = sponsor_name.replace("'", "''")
                sv_resp = await client.get(
                    DOB_ECB_VIOLATIONS,
                    params={
                        "$where": f"upper(respondent_name) like upper('%{escaped}%')",
                        "$limit": "50",
                    },
                    headers=headers,
                )
                if sv_resp.status_code == 200:
                    sponsor_violations = sv_resp.json()

            combined = {
                "job_filings": job_filings,
                "violations": violations,
                "approved_permits": permits,
                "sponsor_violations": sponsor_violations,
            }
            raw = json.dumps(combined, indent=2)

            return PublicDataResult(
                data_source=self.data_source,
                data_type=self.data_type,
                raw_data=raw,
                source_url=f"{DOB_ECB_VIOLATIONS}?$where=bin='{geo.bin}'",
            )

        except httpx.HTTPError as exc:
            logger.error("DOB fetch failed for BIN %s: %s", geo.bin, exc)
            return PublicDataResult(
                data_source=self.data_source,
                data_type=self.data_type,
                raw_data="",
                error=str(exc),
            )

    def interpret(self, raw_data: str, deal_context: dict, llm_client=None, db: Session | None = None, deal_id: uuid.UUID | None = None) -> dict:
        """LLM interprets raw DOB records, flags material issues."""
        if not raw_data:
            return {}

        if llm_client is None:
            data = json.loads(raw_data)
            return {
                "job_filings_count": len(data.get("job_filings", [])),
                "violations_count": len(data.get("violations", [])),
                "permits_count": len(data.get("approved_permits", [])),
            }

        result = llm_client.call_llm(
            "interpret_dob",
            deal_context,
            {"dob_records": raw_data},
            db=db,
            deal_id=deal_id,
        )
        return result
