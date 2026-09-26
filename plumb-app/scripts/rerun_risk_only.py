"""One-off: re-run the risk_report_agent for a specified deal via the real
agent harness path (same as the orchestrator uses).

Critically imports `app.agent.tools.registration` so the tool registry is
populated — without this, the registry is empty, the harness passes `tools=[]`
to the Anthropic API, and Claude writes prose imitating tool calls.

Usage:
    PYTHONPATH=. python scripts/rerun_risk_only.py <deal_id>
"""

import asyncio
import sys
import uuid
from datetime import datetime, timezone

from sqlalchemy import select

# MUST run before any agent instantiation — populates tool_registry.
import app.agent.tools.registration  # noqa: F401

from app.agent.agents.risk_report_agent import RiskReportAgent
from app.agent.orchestrator import _estimate_cost
from app.agent.progress import NULL_EMITTER
from app.db.session import async_session_factory
from app.models.agent import AgentRun
from app.models.deal import Deal
from app.services.context_engine import build_deal_context


async def main(deal_id_str: str) -> None:
    deal_id = uuid.UUID(deal_id_str)
    async with async_session_factory() as db:
        deal = (await db.execute(select(Deal).where(Deal.id == deal_id))).scalar_one_or_none()
        if not deal:
            print(f"Deal {deal_id} not found")
            sys.exit(1)
        print(f"Loaded: {deal.property_name} ({deal.status})")

        context = await build_deal_context(db, deal_id, tags=["construction_loan"])
        agent = RiskReportAgent()
        goal = "Compile all findings and produce a Risk Assessment Report for this deal."
        print(f"Running {agent.name} via real harness path…")

        result = await agent.run(
            goal=goal, deal_context=context, db=db, deal_id=deal_id,
            progress=NULL_EMITTER,
        )

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
        await db.commit()

        print()
        print(f"success={result.success} iters={result.iterations} "
              f"in={result.input_tokens} out={result.output_tokens} "
              f"cost=${run.cost_usd}")
        if result.error:
            print(f"ERROR: {result.error}")
        print()
        print("=== reasoning_trace (tool calls only) ===")
        for step in result.reasoning_trace:
            if step.get("type") == "tool_call":
                print(f"  → {step['tool']}({list(step.get('input', {}).keys())})")
            elif step.get("type") == "tool_result":
                print(f"  ← {step['tool']} success={step['success']}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: rerun_risk_only.py <deal_id>")
        sys.exit(1)
    asyncio.run(main(sys.argv[1]))
