"""ZoLa/PLUTO fetcher — structured zoning data via Socrata SODA API.

No LLM needed: direct field mapping from PLUTO columns.
BBL must be queried as numeric ($where=bbl=1000477501), not string.
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

PLUTO_ENDPOINT = "https://data.cityofnewyork.us/resource/64uk-42ks.json"

PLUTO_FIELD_MAP = {
    "zonedist1": "zoning_district",
    "zonedist2": "zoning_district_2",
    "overlay1": "overlay_1",
    "overlay2": "overlay_2",
    "spdist1": "special_district_1",
    "spdist2": "special_district_2",
    "splitzone": "split_zone",
    "residfar": "residential_far",
    "commfar": "commercial_far",
    "facilfar": "facility_far",
    "lotarea": "lot_area_sf",
    "bldgarea": "building_area_sf",
    "bldgclass": "building_class",
    "landuse": "land_use_code",
    "ownername": "owner_name",
    "yearbuilt": "year_built",
    "yearalter1": "year_altered_1",
    "yearalter2": "year_altered_2",
    "numfloors": "num_floors",
    "unitsres": "residential_units",
    "unitstotal": "total_units",
    "lotfront": "lot_frontage",
    "lotdepth": "lot_depth",
    "assessland": "assessed_land_value",
    "assesstot": "assessed_total_value",
    "borocode": "borough_code",
    "cd": "community_district",
    "ct2010": "census_tract",
    "zipcode": "zip_code",
    "firecomp": "fire_company",
    "policeprct": "police_precinct",
    "sanitboro": "sanitation_borough",
}


class ZoLaFetcher(PublicDataFetcher):
    geography = "nyc"
    data_source = "zola"
    data_type = "zoning"
    cache_ttl_days = 90

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
            resp = await client.get(
                PLUTO_ENDPOINT,
                params={"$where": f"bbl={geo.bbl_numeric}", "$limit": "1"},
                headers=headers,
            )
            resp.raise_for_status()
            records = resp.json()

            if not records:
                return PublicDataResult(
                    data_source=self.data_source,
                    data_type=self.data_type,
                    raw_data="[]",
                    source_url=f"{PLUTO_ENDPOINT}?$where=bbl={geo.bbl_numeric}",
                    error=f"No PLUTO record found for BBL {geo.bbl}",
                )

            raw = json.dumps(records, indent=2)
            return PublicDataResult(
                data_source=self.data_source,
                data_type=self.data_type,
                raw_data=raw,
                source_url=f"{PLUTO_ENDPOINT}?$where=bbl={geo.bbl_numeric}",
            )

        except httpx.HTTPError as exc:
            logger.error("PLUTO fetch failed for BBL %s: %s", geo.bbl, exc)
            return PublicDataResult(
                data_source=self.data_source,
                data_type=self.data_type,
                raw_data="",
                error=str(exc),
            )

    def interpret(self, raw_data: str, deal_context: dict, **kwargs) -> dict:
        """Direct field mapping — no LLM needed."""
        records = json.loads(raw_data) if raw_data else []
        if not records:
            return {}

        row = records[0]
        result = {}
        for pluto_key, our_key in PLUTO_FIELD_MAP.items():
            val = row.get(pluto_key)
            if val is not None:
                result[our_key] = val

        return result
