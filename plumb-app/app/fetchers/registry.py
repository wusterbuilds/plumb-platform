"""Geography-keyed registry of public data fetchers."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.fetchers.base import PublicDataFetcher


def get_fetchers(geography: str) -> dict[str, PublicDataFetcher]:
    """Return instantiated fetchers for a given geography.

    Lazy imports avoid circular dependencies and keep startup fast.
    """
    if geography == "nyc":
        from app.fetchers.nyc.acris import ACRISFetcher
        from app.fetchers.nyc.ag_refb import AGREFBFetcher
        from app.fetchers.nyc.dob import DOBFetcher
        from app.fetchers.nyc.news import NewsSearchFetcher
        from app.fetchers.nyc.zola import ZoLaFetcher

        return {
            "zoning": ZoLaFetcher(),
            "property_records": ACRISFetcher(),
            "permits": DOBFetcher(),
            "news": NewsSearchFetcher(),
            "offering_plan": AGREFBFetcher(),
        }

    return {}


def detect_geography(property_address: str | None) -> str | None:
    """Detect geography from property address. MVP: NYC only."""
    if not property_address:
        return None
    addr_lower = property_address.lower()
    nyc_signals = [
        "new york", "ny ", "nyc", "manhattan", "brooklyn",
        "queens", "bronx", "staten island",
    ]
    if any(signal in addr_lower for signal in nyc_signals):
        return "nyc"
    return None
