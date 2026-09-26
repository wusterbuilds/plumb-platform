"""API routes for Sprint 4: Agent harness, feature flags, agent runs."""

import asyncio
import json
import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.db.session import get_db, async_session_factory
from app.models.agent import AgentRun, FeatureFlag
from app.models.user import User
from app.agent import feature_flags
from app.agent.progress import ProgressEmitter
from app.agent.tools.registry import tool_registry

router = APIRouter(prefix="/agent", tags=["agent"])


class FlagUpdate(BaseModel):
    flag_name: str
    enabled: bool
    enabled_deal_types: list[str] | None = None
    enabled_deal_ids: list[str] | None = None


# ── Feature Flags ──

@router.get("/flags")
async def list_flags(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    flags = await feature_flags.list_flags(db)
    return [
        {
            "id": str(f.id),
            "flag_name": f.flag_name,
            "enabled": f.enabled,
            "enabled_deal_types": f.enabled_deal_types,
            "enabled_deal_ids": f.enabled_deal_ids,
        }
        for f in flags
    ]


@router.post("/flags")
async def set_flag(
    body: FlagUpdate,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    flag = await feature_flags.set_flag(
        db, flag_name=body.flag_name, enabled=body.enabled,
        enabled_deal_types=body.enabled_deal_types,
        enabled_deal_ids=body.enabled_deal_ids,
    )
    return {"flag_name": flag.flag_name, "enabled": flag.enabled}


# ── Tools ──

@router.get("/tools")
async def list_tools(
    _user: User = Depends(get_current_user),
):
    return tool_registry.list_all()


# ── Agent Runs ──

@router.get("/runs")
async def list_runs(
    deal_id: uuid.UUID | None = None,
    agent_name: str | None = None,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    query = select(AgentRun).order_by(AgentRun.started_at.desc()).limit(50)
    if deal_id:
        query = query.where(AgentRun.deal_id == deal_id)
    if agent_name:
        query = query.where(AgentRun.agent_name == agent_name)

    result = await db.execute(query)
    runs = result.scalars().all()
    return [
        {
            "id": str(r.id),
            "deal_id": str(r.deal_id),
            "agent_name": r.agent_name,
            "status": r.status,
            "iterations": r.iterations,
            "input_tokens": r.input_tokens,
            "output_tokens": r.output_tokens,
            "cost_usd": r.cost_usd,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "completed_at": r.completed_at.isoformat() if r.completed_at else None,
            "error": r.error,
        }
        for r in runs
    ]


class PipelineRunRequest(BaseModel):
    start_from: str | None = None  # Optional: skip to a specific agent phase


@router.post("/run/{deal_id}")
async def run_agent_pipeline(
    deal_id: uuid.UUID,
    body: PipelineRunRequest | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Trigger the agent pipeline for a deal."""
    from app.models.deal import Deal

    result = await db.execute(select(Deal).where(Deal.id == deal_id))
    deal = result.scalar_one_or_none()
    if not deal:
        return {"error": "Deal not found"}, 404

    from app.agent.orchestrator import run_deal_pipeline_agent

    try:
        results = await run_deal_pipeline_agent(db=db, deal_id=deal_id)
        await db.commit()
        return {
            "deal_id": str(deal_id),
            "pipeline_status": results.get("pipeline_status", "unknown"),
            "results": {
                k: v for k, v in results.items()
                if k not in ("pipeline_status",)
            },
        }
    except Exception as exc:
        await db.rollback()
        return {"error": str(exc)}, 500


@router.post("/run/{deal_id}/stream")
async def run_agent_pipeline_stream(
    deal_id: uuid.UUID,
    user: User = Depends(get_current_user),
):
    """SSE streaming endpoint — streams real-time progress events as agents execute."""
    from app.models.deal import Deal

    # Validate deal exists using a quick session
    async with async_session_factory() as check_db:
        result = await check_db.execute(select(Deal).where(Deal.id == deal_id))
        deal = result.scalar_one_or_none()
        if not deal:
            return {"error": "Deal not found"}

    emitter = ProgressEmitter()

    async def _run_pipeline():
        """Run the pipeline in a separate db session, emitting progress along the way."""
        from app.agent.orchestrator import run_deal_pipeline_agent

        async with async_session_factory() as db:
            try:
                results = await run_deal_pipeline_agent(
                    db=db, deal_id=deal_id, progress=emitter,
                )
                await db.commit()
                # Emit final results
                await emitter.emit(
                    "pipeline_result",
                    deal_id=str(deal_id),
                    pipeline_status=results.get("pipeline_status", "unknown"),
                )
            except Exception as exc:
                await db.rollback()
                await emitter.emit("pipeline_error", error=str(exc))
            finally:
                await emitter.close()

    async def _event_stream():
        """Yield SSE events from the emitter."""
        # Start the pipeline as a concurrent task
        task = asyncio.create_task(_run_pipeline())
        try:
            async for event in emitter:
                yield event.to_sse()
        except Exception:
            pass
        finally:
            if not task.done():
                task.cancel()

    return StreamingResponse(
        _event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/runs/{run_id}")
async def get_run(
    run_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    result = await db.execute(select(AgentRun).where(AgentRun.id == run_id))
    run = result.scalar_one_or_none()
    if not run:
        return {"error": "Run not found"}
    return {
        "id": str(run.id),
        "deal_id": str(run.deal_id),
        "agent_name": run.agent_name,
        "goal": run.goal,
        "status": run.status,
        "iterations": run.iterations,
        "reasoning_trace": run.reasoning_trace,
        "result": run.result,
        "error": run.error,
        "input_tokens": run.input_tokens,
        "output_tokens": run.output_tokens,
        "cost_usd": run.cost_usd,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
    }
