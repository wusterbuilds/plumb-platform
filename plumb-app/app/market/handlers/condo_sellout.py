"""Condo sellout market handler — knows which data points matter for condo deals."""

import logging

logger = logging.getLogger(__name__)


class CondoSelloutHandler:
    """Produces a narrative-ready market analysis section for condo sellout deals.

    Knows which market data points are most important:
    - Sellout comps (MarketProof > CoStar > broker PDFs)
    - Absorption rates and pace
    - Supply pipeline (competing new development)
    - Offering plan status (AG REFB)
    """

    def build_market_analysis(self, market_context: dict) -> dict:
        """Build a structured market analysis section for OM consumption."""
        comps = market_context.get("comps", [])
        stats = market_context.get("market_stats", {})
        zoning = market_context.get("zoning", {})
        permits = market_context.get("permits", {})
        offering = market_context.get("offering_plan", {})
        portfolio = market_context.get("sponsor_portfolio", {})
        news = market_context.get("news", [])

        sellout_comps = self._filter_sellout_comps(comps)

        analysis = {
            "sellout_comps": {
                "count": len(sellout_comps),
                "comps": sellout_comps[:10],
                "avg_ppsf": self._avg_ppsf(sellout_comps),
                "range_ppsf": self._range_ppsf(sellout_comps),
            },
            "market_conditions": self._summarize_market(stats),
            "supply_pipeline": self._extract_supply(stats),
            "zoning_summary": {
                "district": zoning.get("zoning_district", "N/A"),
                "far": zoning.get("residential_far", "N/A"),
                "lot_area": zoning.get("lot_area_sf", "N/A"),
            },
            "permit_status": {
                "active_permits": len(permits.get("active_permits", [])) if isinstance(permits, dict) else 0,
                "material_flags": permits.get("material_flags", []) if isinstance(permits, dict) else [],
            },
            "offering_plan_status": offering.get("status", "unknown") if isinstance(offering, dict) else "unavailable",
            "sponsor_track_record": {
                "verified_projects": len(portfolio.get("verified_projects", [])),
                "unverified_claims": len(portfolio.get("unverified_claims", [])),
                "violation_history": portfolio.get("violation_history", {}),
            },
            "news_summary": {
                "material_count": sum(1 for n in news if isinstance(n, dict) and n.get("relevance") == "material"),
                "total_count": len(news),
            },
        }

        return analysis

    def _filter_sellout_comps(self, comps: list) -> list[dict]:
        """Filter comps relevant to condo sellout."""
        sellout = []
        for comp in comps:
            if not isinstance(comp, dict):
                continue
            ptype = comp.get("property_type", "").lower()
            if any(kw in ptype for kw in ("condo", "residential", "new development")):
                sellout.append(comp)
            elif comp.get("price_per_sf") or comp.get("ppsf"):
                sellout.append(comp)
        return sellout if sellout else comps[:10]

    def _avg_ppsf(self, comps: list[dict]) -> str | None:
        """Calculate average price per SF from comps."""
        values = []
        for comp in comps:
            ppsf = comp.get("price_per_sf") or comp.get("ppsf", "")
            try:
                values.append(float(str(ppsf).replace("$", "").replace(",", "")))
            except (ValueError, TypeError):
                continue
        if values:
            return f"${sum(values) / len(values):,.0f}"
        return None

    def _range_ppsf(self, comps: list[dict]) -> str | None:
        """Calculate PPSF range from comps."""
        values = []
        for comp in comps:
            ppsf = comp.get("price_per_sf") or comp.get("ppsf", "")
            try:
                values.append(float(str(ppsf).replace("$", "").replace(",", "")))
            except (ValueError, TypeError):
                continue
        if values:
            return f"${min(values):,.0f} - ${max(values):,.0f}"
        return None

    def _summarize_market(self, stats: dict) -> dict:
        if isinstance(stats, dict) and stats.get("status") != "unavailable":
            return {
                "vacancy_rate": stats.get("vacancy_rate", "N/A"),
                "asking_rent": stats.get("asking_rent", "N/A"),
                "absorption": stats.get("net_absorption", "N/A"),
            }
        return {"status": "unavailable"}

    def _extract_supply(self, stats: dict) -> dict:
        if isinstance(stats, dict):
            return {
                "under_construction": stats.get("under_construction_sf", "N/A"),
                "pipeline": stats.get("supply_pipeline", "N/A"),
            }
        return {"status": "unavailable"}
