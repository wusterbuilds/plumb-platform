"""NYC GeoSearch API utility for address-to-BBL/BIN conversion.

Endpoint: https://geosearch.planninglabs.nyc/v2/search
Verified live April 2026. Returns BBL/BIN under
features[0].properties.addendum.pad.{bbl,bin}.
"""

import logging
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

GEOSEARCH_URL = "https://geosearch.planninglabs.nyc/v2/search"


@dataclass
class GeoResult:
    """Parsed geocoding result with all format variants needed by downstream fetchers."""

    bbl: str            # "1000477501" (raw 10-digit from GeoSearch)
    bbl_numeric: int    # 1000477501 (for PLUTO numeric queries)
    bin: str            # "1001026" (for DOB queries)
    borough: str        # "1"
    block: str          # "00047" (zero-padded to 5 digits, for ACRIS)
    lot: str            # "7501" (zero-padded to 4 digits, for ACRIS)
    latitude: float
    longitude: float
    label: str          # Human-readable address label from GeoSearch


def parse_bbl(raw_bbl: str) -> tuple[str, str, str]:
    """Split a 10-digit BBL into (borough, block, lot) with proper padding."""
    padded = raw_bbl.zfill(10)
    borough = padded[0]
    block = padded[1:6]
    lot = padded[6:10]
    return borough, block, lot


async def geocode_address(address: str, client: httpx.AsyncClient | None = None) -> GeoResult | None:
    """Convert a street address to BBL/BIN via NYC GeoSearch API.

    Returns None if the address cannot be resolved.
    """
    should_close = False
    if client is None:
        client = httpx.AsyncClient(timeout=15.0)
        should_close = True

    try:
        resp = await client.get(
            GEOSEARCH_URL,
            params={"text": address, "size": "1"},
        )
        resp.raise_for_status()
        data = resp.json()

        features = data.get("features", [])
        if not features:
            logger.warning("GeoSearch returned no results for: %s", address)
            return None

        props = features[0]["properties"]
        coords = features[0]["geometry"]["coordinates"]
        pad = props.get("addendum", {}).get("pad", {})

        raw_bbl = pad.get("bbl")
        raw_bin = pad.get("bin")
        if not raw_bbl:
            logger.warning("GeoSearch result missing BBL for: %s", address)
            return None

        borough, block, lot = parse_bbl(raw_bbl)

        return GeoResult(
            bbl=raw_bbl,
            bbl_numeric=int(raw_bbl),
            bin=raw_bin or "",
            borough=borough,
            block=block,
            lot=lot,
            latitude=coords[1],
            longitude=coords[0],
            label=props.get("label", address),
        )
    except httpx.HTTPError as exc:
        logger.error("GeoSearch request failed for '%s': %s", address, exc)
        return None
    finally:
        if should_close:
            await client.aclose()
