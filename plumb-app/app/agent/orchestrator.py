"""Sprint 4: Lead Orchestrator — dispatches specialized agents in the right order."""

import asyncio
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.agents.deal_screening_agent import DealScreeningAgent
from app.agent.agents.extraction_agent import ExtractionAgent
from app.agent.agents.lender_targeting_agent import LenderTargetingAgent
from app.agent.agents.om_writer_agent import OMWriterAgent
from app.agent.agents.risk_report_agent import RiskReportAgent
from app.agent.agents.research_agent import ResearchAgent
from app.agent.agents.underwriting_review_agent import UnderwritingReviewAgent
from app.agent import feature_flags
from app.agent.harness import AgentResult
from app.agent.progress import NULL_EMITTER, ProgressEmitter
from app.db.events import log_event
from app.models.agent import AgentRun
from app.models.deal import Deal
from app.schemas.enums import EventType
from app.services.context_engine import build_deal_context
from app.services.extraction_bridge import (
    bridge_extraction_market_context,
    bridge_extraction_to_deal,
    bridge_research_to_deal,
)

logger = logging.getLogger(__name__)


async def _transition_deal(
    db: AsyncSession,
    deal_id: uuid.UUID,
    to_status: str,
    from_status: str | None = None,
) -> None:
    """Transition a deal's status and log the event."""
    result = await db.execute(select(Deal).where(Deal.id == deal_id))
    deal = result.scalar_one_or_none()
    if not deal:
        return

    actual_from = deal.status
    deal.status = to_status
    deal.version += 1

    await log_event(
        db=db,
        deal_id=deal_id,
        event_type=EventType.STATE_TRANSITION.value,
        payload={
            "from_status": from_status or actual_from,
            "to_status": to_status,
            "transition_type": "agent_auto",
        },
    )
    await db.flush()


async def run_deal_pipeline_agent(
    db: AsyncSession,
    deal_id: uuid.UUID,
    progress: ProgressEmitter | None = None,
) -> dict:
    """Orchestrate the full agent pipeline for a deal."""
    p = progress or NULL_EMITTER
    results = {}

    await p.emit("pipeline_started", deal_id=str(deal_id))

    # Load deal for type info used in feature flag checks
    deal_result = await db.execute(select(Deal).where(Deal.id == deal_id))
    deal_obj = deal_result.scalar_one_or_none()
    deal_type = deal_obj.deal_type if deal_obj else None

    # Build context
    context = await build_deal_context(db, deal_id, tags=["construction_loan"])

    # Transition to classifying so UI shows progress
    await _transition_deal(db, deal_id, "classifying")
    await db.commit()

    # 1. Deal Screening
    if await feature_flags.is_enabled(db, "agent.deal_screening", deal_id=deal_id, deal_type=deal_type):
        screening = DealScreeningAgent()
        screening_goal = "Screen this deal for viability."
        await p.emit("agent_starting", agent=screening.name, goal=screening_goal)
        screening_result = await _run_agent(db, deal_id, screening, screening_goal, context, progress=p)
        results["screening"] = screening_result.data
        run = await _log_agent_run(db, deal_id, screening, screening_result, goal=screening_goal)
        await p.emit(
            "agent_completed", agent=screening.name,
            status="completed" if screening_result.success else "failed",
            iterations=screening_result.iterations,
            input_tokens=screening_result.input_tokens,
            output_tokens=screening_result.output_tokens,
            cost_usd=run.cost_usd,
            error=screening_result.error,
        )

        recommendation = (screening_result.data or {}).get("recommendation", "proceed")
        if recommendation == "decline":
            await _transition_deal(db, deal_id, "dead", "docs_received")
            results["pipeline_status"] = "declined_at_screening"
            await p.emit("pipeline_completed", status="declined_at_screening")
            return results

    # Transition to extracting
    await _transition_deal(db, deal_id, "extracting")
    await db.commit()

    # 2. Extraction + Research (run in parallel — no dependency between them)
    extraction_enabled = await feature_flags.is_enabled(db, "agent.extraction", deal_id=deal_id, deal_type=deal_type)
    research_enabled = await feature_flags.is_enabled(db, "agent.research", deal_id=deal_id, deal_type=deal_type)

    extraction_result = None
    research_result = None

    if extraction_enabled:
        extraction = ExtractionAgent()
        extraction_goal = "Extract all fields from the deal package documents."
        await p.emit("agent_starting", agent=extraction.name, goal=extraction_goal)
    if research_enabled:
        research = ResearchAgent()
        research_goal = "Gather market intelligence for this deal."
        await p.emit("agent_starting", agent=research.name, goal=research_goal)

    if extraction_enabled and research_enabled:
        extraction_result, research_result = await asyncio.gather(
            _run_agent(db, deal_id, extraction, extraction_goal, context, progress=p),
            _run_agent(db, deal_id, research, research_goal, context, progress=p),
        )
    elif extraction_enabled:
        extraction_result = await _run_agent(
            db, deal_id, extraction, extraction_goal, context, progress=p,
        )
    elif research_enabled:
        research_result = await _run_agent(
            db, deal_id, research, research_goal, context, progress=p,
        )

    if extraction_enabled:
        results["extraction"] = extraction_result.data
        run = await _log_agent_run(db, deal_id, extraction, extraction_result, goal=extraction_goal)
        await p.emit(
            "agent_completed", agent=extraction.name,
            status="completed" if extraction_result.success else "failed",
            iterations=extraction_result.iterations,
            input_tokens=extraction_result.input_tokens,
            output_tokens=extraction_result.output_tokens,
            cost_usd=run.cost_usd,
            error=extraction_result.error,
        )
    if research_enabled:
        results["research"] = research_result.data
        run = await _log_agent_run(db, deal_id, research, research_result, goal=research_goal)
        await p.emit(
            "agent_completed", agent=research.name,
            status="completed" if research_result.success else "failed",
            iterations=research_result.iterations,
            input_tokens=research_result.input_tokens,
            output_tokens=research_result.output_tokens,
            cost_usd=run.cost_usd,
            error=research_result.error,
        )

    # Fail fast if extraction failed — downstream agents need extracted data
    if extraction_enabled and extraction_result and not extraction_result.success:
        await _transition_deal(db, deal_id, "extraction_failed")
        results["pipeline_status"] = "extraction_failed"
        await p.emit("pipeline_completed", status="extraction_failed")
        return results

    # 2b. Bridge extracted data → Deal model (typed_extension, sponsor, market_context)
    # This ensures downstream agents and the OM renderer find data on the Deal row.
    # Commit first so the sync financial engine can see extracted values.
    await db.commit()
    try:
        await p.emit("bridge_starting", step="extraction_bridge")
        bridge_result = await bridge_extraction_to_deal(db, deal_id)
        results["extraction_bridge"] = bridge_result
        await p.emit("bridge_completed", step="extraction_bridge", result=bridge_result)
    except Exception as e:
        logger.warning("Extraction bridge failed for deal %s: %s", deal_id, e)
        results["extraction_bridge"] = {"error": str(e)}

    # Bridge market-relevant extracted fields (comparable_sales, transit_access,
    # market_conditions) into deal.market_context so OM comps pages render.
    # Runs before the research bridge so research can overwrite/augment values.
    try:
        await p.emit("bridge_starting", step="extraction_market_bridge")
        market_bridge = await bridge_extraction_market_context(db, deal_id)
        results["extraction_market_bridge"] = market_bridge
        await p.emit("bridge_completed", step="extraction_market_bridge", result=market_bridge)
    except Exception as e:
        logger.warning("Extraction market bridge failed for deal %s: %s", deal_id, e)
        results["extraction_market_bridge"] = {"error": str(e)}

    if research_enabled and research_result and research_result.success:
        try:
            await p.emit("bridge_starting", step="research_bridge")
            research_bridge = await bridge_research_to_deal(db, deal_id, research_result.data)
            results["research_bridge"] = research_bridge
            await p.emit("bridge_completed", step="research_bridge", result=research_bridge)
        except Exception as e:
            logger.warning("Research bridge failed for deal %s: %s", deal_id, e)
            results["research_bridge"] = {"error": str(e)}

    # Commit bridge results so downstream agents see updated deal data
    await db.commit()

    # 3. Transition to extraction_review (human gate)
    await _transition_deal(db, deal_id, "extraction_review")
    results["awaiting_extraction_review"] = True
    await p.emit("state_transition", to_status="extraction_review")

    # Transition to model_building
    await _transition_deal(db, deal_id, "model_building")
    await db.commit()

    # 4. Underwriting Review (after extraction review)
    if await feature_flags.is_enabled(db, "agent.underwriting", deal_id=deal_id, deal_type=deal_type):
        underwriting = UnderwritingReviewAgent()
        context = await build_deal_context(db, deal_id, tags=["construction_loan"])
        underwriting_goal = "Build the financial model and identify underwriting concerns."
        await p.emit("agent_starting", agent=underwriting.name, goal=underwriting_goal)
        underwriting_result = await _run_agent(
            db, deal_id, underwriting, underwriting_goal, context, progress=p,
        )
        results["underwriting"] = underwriting_result.data
        run = await _log_agent_run(db, deal_id, underwriting, underwriting_result, goal=underwriting_goal)
        await p.emit(
            "agent_completed", agent=underwriting.name,
            status="completed" if underwriting_result.success else "failed",
            iterations=underwriting_result.iterations,
            input_tokens=underwriting_result.input_tokens,
            output_tokens=underwriting_result.output_tokens,
            cost_usd=run.cost_usd,
            error=underwriting_result.error,
        )

    # 5. Lender Targeting — rebuild context so the financial_model committed
    # by the underwriting agent (loan_amount, LTC, TDC) is visible.
    if await feature_flags.is_enabled(db, "agent.lender_targeting", deal_id=deal_id, deal_type=deal_type):
        await db.commit()
        targeting = LenderTargetingAgent()
        targeting_context = await build_deal_context(db, deal_id, tags=["construction_loan"])
        targeting_goal = "Select and rank target lenders for this deal."
        await p.emit("agent_starting", agent=targeting.name, goal=targeting_goal)
        targeting_result = await _run_agent(
            db, deal_id, targeting, targeting_goal, targeting_context, progress=p,
        )
        results["lender_targeting"] = targeting_result.data
        run = await _log_agent_run(db, deal_id, targeting, targeting_result, goal=targeting_goal)
        await p.emit(
            "agent_completed", agent=targeting.name,
            status="completed" if targeting_result.success else "failed",
            iterations=targeting_result.iterations,
            input_tokens=targeting_result.input_tokens,
            output_tokens=targeting_result.output_tokens,
            cost_usd=run.cost_usd,
            error=targeting_result.error,
        )

    # Transition to om_drafting
    await _transition_deal(db, deal_id, "om_drafting")
    await p.emit("state_transition", to_status="om_drafting")

    # 6. OM Writing + Risk Report (run in parallel — both read from deal model)
    context = await build_deal_context(db, deal_id, tags=["construction_loan"])

    om_enabled = await feature_flags.is_enabled(db, "agent.om_writer", deal_id=deal_id, deal_type=deal_type)
    risk_enabled = await feature_flags.is_enabled(db, "agent.risk_report", deal_id=deal_id, deal_type=deal_type)

    om_result = None
    risk_result = None

    if om_enabled:
        om_writer = OMWriterAgent()
        om_goal = "Draft the Offering Memorandum for this deal."
        await p.emit("agent_starting", agent=om_writer.name, goal=om_goal)
    if risk_enabled:
        risk_reporter = RiskReportAgent()
        risk_goal = "Compile all findings and produce a Risk Assessment Report for this deal."
        await p.emit("agent_starting", agent=risk_reporter.name, goal=risk_goal)

    if om_enabled and risk_enabled:
        om_result, risk_result = await asyncio.gather(
            _run_agent(db, deal_id, om_writer, om_goal, context, progress=p),
            _run_agent(db, deal_id, risk_reporter, risk_goal, context, progress=p),
        )
    elif om_enabled:
        om_result = await _run_agent(db, deal_id, om_writer, om_goal, context, progress=p)
    elif risk_enabled:
        risk_result = await _run_agent(db, deal_id, risk_reporter, risk_goal, context, progress=p)

    if om_enabled and om_result:
        results["om"] = om_result.data
        run = await _log_agent_run(db, deal_id, om_writer, om_result, goal=om_goal)
        await p.emit(
            "agent_completed", agent=om_writer.name,
            status="completed" if om_result.success else "failed",
            iterations=om_result.iterations,
            input_tokens=om_result.input_tokens,
            output_tokens=om_result.output_tokens,
            cost_usd=run.cost_usd,
            error=om_result.error,
        )
    if risk_enabled and risk_result:
        results["risk_report"] = risk_result.data
        run = await _log_agent_run(db, deal_id, risk_reporter, risk_result, goal=risk_goal)
        await p.emit(
            "agent_completed", agent=risk_reporter.name,
            status="completed" if risk_result.success else "failed",
            iterations=risk_result.iterations,
            input_tokens=risk_result.input_tokens,
            output_tokens=risk_result.output_tokens,
            cost_usd=run.cost_usd,
            error=risk_result.error,
        )

    # 7. Transition to om_review (human gate)
    await _transition_deal(db, deal_id, "om_review")
    await p.emit("state_transition", to_status="om_review")
    results["awaiting_om_review"] = True
    results["pipeline_status"] = "complete"
    await p.emit("pipeline_completed", status="complete")
    return results


async def _run_agent(
    db: AsyncSession,
    deal_id: uuid.UUID,
    agent: object,
    goal: str,
    context: dict,
    progress: ProgressEmitter | None = None,
) -> AgentResult:
    try:
        return await agent.run(
            goal=goal, deal_context=context, db=db, deal_id=deal_id,
            progress=progress or NULL_EMITTER,
        )
    except Exception as e:
        logger.exception("Agent %s failed for deal %s", getattr(agent, "name", "unknown"), deal_id)
        return AgentResult(
            success=False,
            error=str(e),
            reasoning_trace=getattr(agent, "_last_trace", []),
        )


async def _log_agent_run(
    db: AsyncSession,
    deal_id: uuid.UUID,
    agent: object,
    result: AgentResult,
    goal: str = "",
) -> AgentRun:
    run = AgentRun(
        deal_id=deal_id,
        agent_name=agent.name,
        goal=goal,
        status="completed" if result.success else "failed",
        iterations=result.iterations,
        reasoning_trace=result.reasoning_trace,
        result=result.data if isinstance(result.data, dict) else {"data": str(result.data)},
        error=result.error,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        cost_usd=_estimate_cost(agent.model, result.input_tokens, result.output_tokens),
        completed_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    db.add(run)
    await db.flush()
    return run


def _estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    prices = {
        "claude-opus-4-6": (15.0, 75.0),
        "claude-sonnet-4-6": (3.0, 15.0),
        "claude-haiku-4-5-20251001": (0.80, 4.0),
    }
    input_price, output_price = prices.get(model, (3.0, 15.0))
    return round(
        (input_tokens * input_price / 1_000_000) + (output_tokens * output_price / 1_000_000),
        6,
    )
