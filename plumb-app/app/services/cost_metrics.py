"""Sprint 1: Cost attribution — token usage aggregation by deal, module, prompt."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event import Event


async def get_aggregate_cost(db: AsyncSession) -> dict:
    result = await db.execute(
        select(
            func.sum(Event.payload["input_tokens"].as_integer()).label("total_input"),
            func.sum(Event.payload["output_tokens"].as_integer()).label("total_output"),
            func.sum(Event.payload["cost_usd"].as_float()).label("total_cost"),
            func.count(Event.id).label("call_count"),
        )
        .where(Event.event_type == "llm_call")
    )
    row = result.one()
    return {
        "total_input_tokens": row.total_input or 0,
        "total_output_tokens": row.total_output or 0,
        "total_cost_usd": round(float(row.total_cost or 0), 4),
        "total_calls": row.call_count or 0,
    }


async def get_deal_cost(db: AsyncSession, deal_id: uuid.UUID) -> dict:
    result = await db.execute(
        select(
            Event.payload["prompt_name"].as_string().label("prompt_name"),
            Event.payload["model"].as_string().label("model"),
            func.sum(Event.payload["input_tokens"].as_integer()).label("input_tokens"),
            func.sum(Event.payload["output_tokens"].as_integer()).label("output_tokens"),
            func.sum(Event.payload["cost_usd"].as_float()).label("cost"),
            func.count(Event.id).label("calls"),
        )
        .where(Event.deal_id == deal_id, Event.event_type == "llm_call")
        .group_by(
            Event.payload["prompt_name"].as_string(),
            Event.payload["model"].as_string(),
        )
    )
    rows = result.all()
    total_cost = sum(float(r.cost or 0) for r in rows)
    return {
        "deal_id": str(deal_id),
        "total_cost_usd": round(total_cost, 4),
        "by_prompt": [
            {
                "prompt_name": r.prompt_name,
                "model": r.model,
                "input_tokens": r.input_tokens or 0,
                "output_tokens": r.output_tokens or 0,
                "cost_usd": round(float(r.cost or 0), 4),
                "calls": r.calls,
            }
            for r in rows
        ],
    }


async def get_prompt_costs(db: AsyncSession) -> dict:
    result = await db.execute(
        select(
            Event.payload["prompt_name"].as_string().label("prompt_name"),
            func.sum(Event.payload["cost_usd"].as_float()).label("total_cost"),
            func.count(Event.id).label("calls"),
            func.avg(Event.payload["input_tokens"].as_integer()).label("avg_input"),
            func.avg(Event.payload["output_tokens"].as_integer()).label("avg_output"),
        )
        .where(Event.event_type == "llm_call")
        .group_by(Event.payload["prompt_name"].as_string())
        .order_by(func.sum(Event.payload["cost_usd"].as_float()).desc())
    )
    rows = result.all()
    return {
        "prompts": [
            {
                "prompt_name": r.prompt_name,
                "total_cost_usd": round(float(r.total_cost or 0), 4),
                "calls": r.calls,
                "avg_input_tokens": round(float(r.avg_input or 0)),
                "avg_output_tokens": round(float(r.avg_output or 0)),
            }
            for r in rows
        ]
    }
