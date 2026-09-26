"""Memory tools — real implementations calling developer, lender, and episode services."""

import logging
import uuid

from app.agent.tools.base import PlumbTool, ToolContext, ToolPermission, ToolResult

logger = logging.getLogger(__name__)


class QueryDeveloperTool(PlumbTool):
    name = "query_developer"
    description = "Query developer profile including entity structure, track record, and known correction patterns."
    permission = ToolPermission.AUTO

    def get_input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "developer_name": {"type": "string", "description": "Developer/sponsor name to look up"},
            },
            "required": ["developer_name"],
        }

    async def execute(self, _ctx: ToolContext | None = None, developer_name: str = "", **kwargs) -> ToolResult:
        if not _ctx or not _ctx.db:
            return ToolResult(success=False, error="ToolContext with db required")

        from app.services.developer_service import get_correction_patterns, list_developers

        developers = await list_developers(_ctx.db, search=developer_name)
        if not developers:
            return ToolResult(data={
                "found": False,
                "name": developer_name,
                "message": f"No developer found matching '{developer_name}'",
            })

        dev = developers[0]
        corrections = await get_correction_patterns(_ctx.db, dev.id)

        return ToolResult(data={
            "found": True,
            "developer_id": str(dev.id),
            "name": dev.name,
            "entity_structure": dev.entity_structure,
            "track_record": dev.track_record,
            "known_patterns": dev.known_patterns,
            "deal_count": dev.deal_count,
            "correction_patterns": corrections,
        })


class QueryLenderTool(PlumbTool):
    name = "query_lender"
    description = "Query lender profile including preferences, credit committee notes, and appetite history."
    permission = ToolPermission.AUTO

    def get_input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "lender_name": {"type": "string", "description": "Lender name to look up"},
            },
            "required": ["lender_name"],
        }

    async def execute(self, _ctx: ToolContext | None = None, lender_name: str = "", **kwargs) -> ToolResult:
        if not _ctx or not _ctx.db:
            return ToolResult(success=False, error="ToolContext with db required")

        from app.services.lender_service import (
            get_latest_appetite,
            get_transactions,
            list_lenders,
        )

        lenders = await list_lenders(_ctx.db, search=lender_name)
        if not lenders:
            return ToolResult(data={
                "found": False,
                "name": lender_name,
                "message": f"No lender found matching '{lender_name}'",
            })

        lender = lenders[0]
        appetite = await get_latest_appetite(_ctx.db, lender.id)
        transactions = await get_transactions(_ctx.db, lender.id)

        appetite_data = None
        if appetite:
            appetite_data = {
                "signal": appetite.appetite_signal,
                "property_types": appetite.property_types,
                "geographies": appetite.geographies,
                "deal_size_min": appetite.deal_size_min,
                "deal_size_max": appetite.deal_size_max,
                "ltc_max": appetite.ltc_max,
                "rate_indication": appetite.rate_indication,
                "recorded_at": str(appetite.recorded_at) if appetite.recorded_at else None,
            }

        txn_summary = []
        for txn in transactions[:10]:
            txn_summary.append({
                "deal_type": txn.deal_type,
                "outcome": txn.outcome,
                "amount": txn.amount,
                "recorded_at": str(txn.recorded_at) if txn.recorded_at else None,
            })

        return ToolResult(data={
            "found": True,
            "lender_id": str(lender.id),
            "name": lender.name,
            "lender_type": lender.lender_type,
            "notes": lender.notes,
            "latest_appetite": appetite_data,
            "recent_transactions": txn_summary,
        })


class MatchLendersTool(PlumbTool):
    name = "match_lenders"
    description = "Get ranked list of matching lenders for a deal based on appetite, history, and fit."
    permission = ToolPermission.AUTO

    def get_input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "deal_id": {"type": "string"},
                "property_type": {"type": "string"},
                "geography": {"type": "string"},
                "deal_size": {"type": "number"},
                "ltc_requested": {"type": "number"},
            },
            "required": ["deal_id"],
        }

    async def execute(self, _ctx: ToolContext | None = None, deal_id: str = "", property_type: str | None = None, geography: str | None = None, deal_size: float | None = None, ltc_requested: float | None = None, **kwargs) -> ToolResult:
        if not _ctx or not _ctx.db:
            return ToolResult(success=False, error="ToolContext with db required")

        from app.services.lender_service import match_lenders_for_deal

        matches = await match_lenders_for_deal(
            _ctx.db,
            property_type=property_type,
            geography=geography,
            deal_size=deal_size,
            ltc_requested=ltc_requested,
        )

        return ToolResult(data={
            "deal_id": deal_id,
            "matches": matches,
            "total_matched": len(matches),
        })


class QueryEpisodesTool(PlumbTool):
    name = "query_episodes"
    description = "Retrieve relevant episodic memories (lessons from past deals) matching given tags."
    permission = ToolPermission.AUTO

    def get_input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "tags": {"type": "array", "items": {"type": "string"}, "description": "Relevance tags to search"},
            },
            "required": ["tags"],
        }

    async def execute(self, _ctx: ToolContext | None = None, tags: list | None = None, **kwargs) -> ToolResult:
        if not _ctx or not _ctx.db:
            return ToolResult(success=False, error="ToolContext with db required")

        from app.services.episode_service import query_episodes_by_tags

        if not tags:
            return ToolResult(data={"episodes": [], "message": "No tags provided"})

        episodes = await query_episodes_by_tags(_ctx.db, tags)

        episode_data = []
        for ep in episodes[:15]:
            episode_data.append({
                "id": str(ep.id),
                "event_type": ep.event_type,
                "lesson": ep.lesson,
                "confidence": ep.confidence,
                "occurrence_count": ep.occurrence_count,
                "relevance_tags": ep.relevance_tags,
            })

        return ToolResult(data={
            "tags": tags,
            "episodes": episode_data,
            "total_matched": len(episodes),
        })


class StoreEpisodeTool(PlumbTool):
    name = "store_episode"
    description = "Store a new episodic memory (lesson learned from current deal processing)."
    permission = ToolPermission.AUTO

    def get_input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "event_type": {"type": "string", "enum": ["correction", "lender_insight", "data_quality", "workflow"]},
                "lesson": {"type": "string"},
                "tags": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["event_type", "lesson"],
        }

    async def execute(self, _ctx: ToolContext | None = None, event_type: str = "", lesson: str = "", tags: list | None = None, **kwargs) -> ToolResult:
        if not _ctx or not _ctx.db:
            return ToolResult(success=False, error="ToolContext with db required")

        from app.services.episode_service import create_episode

        episode = await create_episode(
            _ctx.db,
            event_type=event_type,
            lesson=lesson,
            deal_id=_ctx.deal_id,
            relevance_tags=tags or [],
        )

        return ToolResult(data={
            "episode_id": str(episode.id),
            "event_type": episode.event_type,
            "lesson": episode.lesson,
            "confidence": episode.confidence,
        })
