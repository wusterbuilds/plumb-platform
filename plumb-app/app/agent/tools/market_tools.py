"""Market tools — real implementations calling NYC public data fetchers and LLM interpretation."""

import json
import logging
import uuid

import httpx

from app.agent.tools.base import PlumbTool, ToolContext, ToolPermission, ToolResult

logger = logging.getLogger(__name__)


class GeocodeAddressTool(PlumbTool):
    name = "geocode_address"
    description = (
        "Convert a NYC property address to BBL and BIN identifiers. "
        "You MUST call this before using fetch_acris, fetch_zola, or fetch_dob, "
        "which require BBL or BIN as input. Returns the BBL (10-digit), BIN, "
        "borough, block, lot, and coordinates."
    )
    permission = ToolPermission.AUTO

    def get_input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "address": {
                    "type": "string",
                    "description": "Street address (e.g., '100 Harbor Way, Example City, NY')",
                },
            },
            "required": ["address"],
        }

    async def execute(self, _ctx: ToolContext | None = None, address: str = "", **kwargs) -> ToolResult:
        from app.fetchers.nyc.geoclient import geocode_address

        if not address:
            return ToolResult(success=False, error="address is required")

        geo = await geocode_address(address)
        if geo is None:
            return ToolResult(
                success=False,
                error=f"Could not geocode address: {address}. Try reformatting or using a nearby intersection.",
            )

        return ToolResult(data={
            "bbl": geo.bbl,
            "bbl_numeric": geo.bbl_numeric,
            "bin": geo.bin,
            "borough": geo.borough,
            "block": geo.block,
            "lot": geo.lot,
            "latitude": geo.latitude,
            "longitude": geo.longitude,
            "label": geo.label,
        })


class FetchACRISTool(PlumbTool):
    name = "fetch_acris"
    description = "Fetch property deed transfers, mortgages, and liens from NYC ACRIS by BBL."
    permission = ToolPermission.AUTO

    def get_input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "bbl": {"type": "string", "description": "Borough-Block-Lot identifier (10-digit)"},
            },
            "required": ["bbl"],
        }

    async def execute(self, _ctx: ToolContext | None = None, bbl: str = "", **kwargs) -> ToolResult:
        from app.fetchers.nyc.acris import ACRISFetcher
        from app.fetchers.nyc.geoclient import GeoResult, parse_bbl

        if not bbl:
            return ToolResult(success=False, error="BBL required")

        borough, block, lot = parse_bbl(bbl)
        geo = GeoResult(
            bbl=bbl, bbl_numeric=int(bbl), bin="",
            borough=borough, block=block, lot=lot,
            latitude=0.0, longitude=0.0, label="",
        )

        fetcher = ACRISFetcher()
        async with httpx.AsyncClient(timeout=30.0) as client:
            result = await fetcher.fetch(client=client, geo=geo)

        if result.error:
            return ToolResult(success=False, error=result.error)

        # Parse raw data for summary
        try:
            data = json.loads(result.raw_data)
            summary = {
                "legals_count": len(data.get("legals", [])),
                "masters_count": len(data.get("masters", [])),
                "parties_count": len(data.get("parties", [])),
            }
        except (json.JSONDecodeError, TypeError):
            summary = {}

        return ToolResult(data={
            "bbl": bbl,
            "raw_data": result.raw_data[:8000],
            "source_url": result.source_url,
            "summary": summary,
        })


class FetchDOBTool(PlumbTool):
    name = "fetch_dob"
    description = "Fetch building permits, violations, and complaints from NYC DOB by BIN."
    permission = ToolPermission.AUTO

    def get_input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "bin": {"type": "string", "description": "Building Identification Number"},
                "sponsor_name": {"type": "string", "description": "Optional sponsor name for portfolio violation search"},
            },
            "required": ["bin"],
        }

    async def execute(self, _ctx: ToolContext | None = None, bin: str = "", sponsor_name: str | None = None, **kwargs) -> ToolResult:
        from app.fetchers.nyc.dob import DOBFetcher
        from app.fetchers.nyc.geoclient import GeoResult

        if not bin:
            return ToolResult(success=False, error="BIN required")

        # DOB fetcher needs a GeoResult with bin populated
        geo = GeoResult(
            bbl="", bbl_numeric=0, bin=bin,
            borough="", block="", lot="",
            latitude=0.0, longitude=0.0, label="",
        )

        fetcher = DOBFetcher()
        async with httpx.AsyncClient(timeout=30.0) as client:
            result = await fetcher.fetch(client=client, geo=geo, sponsor_name=sponsor_name)

        if result.error:
            return ToolResult(success=False, error=result.error)

        try:
            data = json.loads(result.raw_data)
            summary = {
                "job_filings_count": len(data.get("job_filings", [])),
                "violations_count": len(data.get("violations", [])),
                "approved_permits_count": len(data.get("approved_permits", [])),
                "sponsor_violations_count": len(data.get("sponsor_violations", [])),
            }
        except (json.JSONDecodeError, TypeError):
            summary = {}

        return ToolResult(data={
            "bin": bin,
            "raw_data": result.raw_data[:8000],
            "source_url": result.source_url,
            "summary": summary,
        })


class FetchZolaTool(PlumbTool):
    name = "fetch_zola"
    description = "Fetch zoning, FAR, lot coverage from NYC ZoLa/PLUTO by BBL."
    permission = ToolPermission.AUTO

    def get_input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "bbl": {"type": "string", "description": "Borough-Block-Lot identifier (10-digit)"},
            },
            "required": ["bbl"],
        }

    async def execute(self, _ctx: ToolContext | None = None, bbl: str = "", **kwargs) -> ToolResult:
        from app.fetchers.nyc.geoclient import GeoResult, parse_bbl
        from app.fetchers.nyc.zola import ZoLaFetcher

        if not bbl:
            return ToolResult(success=False, error="BBL required")

        borough, block, lot = parse_bbl(bbl)
        geo = GeoResult(
            bbl=bbl, bbl_numeric=int(bbl), bin="",
            borough=borough, block=block, lot=lot,
            latitude=0.0, longitude=0.0, label="",
        )

        fetcher = ZoLaFetcher()
        async with httpx.AsyncClient(timeout=30.0) as client:
            result = await fetcher.fetch(client=client, geo=geo)

        if result.error:
            return ToolResult(success=False, error=result.error)

        # ZoLa uses direct field mapping — no LLM needed
        interpreted = fetcher.interpret(result.raw_data, {})

        return ToolResult(data={
            "bbl": bbl,
            "zoning_data": interpreted,
            "source_url": result.source_url,
        })


class FetchNewsTool(PlumbTool):
    name = "fetch_news"
    description = "Search for news about a property, project, or developer in real estate trade press."
    permission = ToolPermission.AUTO

    def get_input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "property_address": {"type": "string", "description": "Property address to search"},
                "developer_name": {"type": "string", "description": "Developer name to search"},
                "project_name": {"type": "string", "description": "Project name to search"},
            },
        }

    async def execute(self, _ctx: ToolContext | None = None, property_address: str | None = None, developer_name: str | None = None, project_name: str | None = None, **kwargs) -> ToolResult:
        from app.fetchers.nyc.news import NewsSearchFetcher

        if not any([property_address, developer_name, project_name]):
            return ToolResult(success=False, error="At least one search term required (property_address, developer_name, or project_name)")

        fetcher = NewsSearchFetcher()
        async with httpx.AsyncClient(timeout=30.0) as client:
            result = await fetcher.fetch(
                client=client,
                property_address=property_address,
                developer_name=developer_name,
                project_name=project_name,
            )

        if result.error:
            return ToolResult(success=False, error=result.error)

        try:
            articles = json.loads(result.raw_data)
        except (json.JSONDecodeError, TypeError):
            articles = []

        return ToolResult(data={
            "articles": articles[:20],
            "total_results": len(articles),
        })


class InterpretACRISTool(PlumbTool):
    name = "interpret_acris"
    description = "LLM interprets raw ACRIS records to extract underwriting-relevant facts."
    permission = ToolPermission.AUTO

    def get_input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "records": {"type": "string", "description": "Raw ACRIS records JSON text"},
            },
            "required": ["records"],
        }

    async def execute(self, _ctx: ToolContext | None = None, records: str = "", **kwargs) -> ToolResult:
        if not _ctx or not _ctx.llm_client or not _ctx.db:
            return ToolResult(success=False, error="ToolContext with llm_client and db required")
        if not records:
            return ToolResult(success=False, error="No records provided")

        deal_context = {}
        if _ctx.deal_id:
            from app.services.context_engine import build_l1_context
            deal_context = await build_l1_context(_ctx.db, _ctx.deal_id)

        result = await _ctx.llm_client.execute(
            "interpret_acris", deal_context,
            {"acris_records": records[:6000]},
            db=_ctx.db, deal_id=_ctx.deal_id,
        )

        return ToolResult(data=result)


class InterpretDOBTool(PlumbTool):
    name = "interpret_dob"
    description = "LLM interprets raw DOB permit/violation records to flag material issues."
    permission = ToolPermission.AUTO

    def get_input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "records": {"type": "string", "description": "Raw DOB records JSON text"},
            },
            "required": ["records"],
        }

    async def execute(self, _ctx: ToolContext | None = None, records: str = "", **kwargs) -> ToolResult:
        if not _ctx or not _ctx.llm_client or not _ctx.db:
            return ToolResult(success=False, error="ToolContext with llm_client and db required")
        if not records:
            return ToolResult(success=False, error="No records provided")

        deal_context = {}
        if _ctx.deal_id:
            from app.services.context_engine import build_l1_context
            deal_context = await build_l1_context(_ctx.db, _ctx.deal_id)

        result = await _ctx.llm_client.execute(
            "interpret_dob", deal_context,
            {"dob_records": records[:6000]},
            db=_ctx.db, deal_id=_ctx.deal_id,
        )

        return ToolResult(data=result)


class InterpretNewsTool(PlumbTool):
    name = "interpret_news"
    description = "LLM classifies news results as material/contextual/irrelevant and extracts key facts."
    permission = ToolPermission.AUTO

    def get_input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "articles": {"type": "string", "description": "News article summaries JSON"},
            },
            "required": ["articles"],
        }

    async def execute(self, _ctx: ToolContext | None = None, articles: str = "", **kwargs) -> ToolResult:
        if not _ctx or not _ctx.llm_client or not _ctx.db:
            return ToolResult(success=False, error="ToolContext with llm_client and db required")
        if not articles:
            return ToolResult(success=False, error="No articles provided")

        deal_context = {}
        if _ctx.deal_id:
            from app.services.context_engine import build_l1_context
            deal_context = await build_l1_context(_ctx.db, _ctx.deal_id)

        result = await _ctx.llm_client.execute(
            "interpret_news", deal_context,
            {"search_results": articles[:6000]},
            db=_ctx.db, deal_id=_ctx.deal_id,
        )

        return ToolResult(data=result)
