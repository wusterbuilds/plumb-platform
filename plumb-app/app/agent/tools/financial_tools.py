"""Sprint 4 → Sprint 5: Financial tools for agent-driven underwriting review.

The underwriting agent is an analyst, not a calculator. Deterministic math lives
in app.financial.engine; these tools let the agent read, adjust, and export the
model, then focus on judgment-level flags.
"""

import asyncio
import logging
import uuid

from app.agent.tools.base import PlumbTool, ToolContext, ToolPermission, ToolResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helper: run the deterministic engine (sync) from an async tool
# ---------------------------------------------------------------------------

def _build_model_sync(deal_uuid: uuid.UUID, assumptions_dict: dict | None = None):
    """Call build_financial_model with a sync session. Runs in a thread."""
    from app.db.session import sync_session_factory
    from app.financial.engine import build_financial_model
    from app.financial.schemas import ModelAssumptions

    assumptions = ModelAssumptions(**(assumptions_dict or {})) if assumptions_dict else None
    db = sync_session_factory()
    try:
        return build_financial_model(deal_uuid, db, assumptions)
    finally:
        db.close()


def _summarize_model(model) -> dict:
    """Return a concise dict the agent can reason over (not 200+ fields)."""
    v = model.valuation
    p = model.proforma
    a = model.assumptions
    return {
        "total_development_cost": model.total_development_cost,
        "loan_amount": model.loan_amount,
        "equity": model.equity,
        "ltc": round(model.ltc, 4),
        "total_units": model.total_units,
        "total_gsf": model.total_gsf,
        "nra": model.nra,
        "zfa": model.zfa,
        "assumptions": {
            "cap_rate": a.cap_rate,
            "vacancy_fm": a.vacancy_fm,
            "vacancy_affordable": a.vacancy_affordable,
            "vacancy_retail": a.vacancy_retail,
            "mgmt_fee_pct": a.mgmt_fee_pct,
            "discount_rate": a.discount_rate,
        },
        "sources_uses_summary": {
            "total_sources": model.sources_uses.total_sources.total,
            "total_uses": model.sources_uses.total_uses.total,
            "source_count": len(model.sources_uses.sources),
            "use_count": len(model.sources_uses.uses),
        },
        "budget_summary": {
            "categories": list({item.category for item in model.budget_detail}),
            "line_count": len(model.budget_detail),
            "total": sum(item.total_cost for item in model.budget_detail),
        },
        "unit_mix_summary": {
            "fm_units": sum(r.units for r in model.unit_mix.fm),
            "affordable_421a_units": sum(r.units for r in model.unit_mix.affordable_421a),
            "mih_units": sum(r.units for r in model.unit_mix.mih),
            "commercial_units": sum(r.units for r in model.unit_mix.commercial),
        },
        "proforma": {
            "egi": p.egi.total,
            "total_expenses": p.total_expenses.total,
            "noi": p.noi.total,
        },
        "valuation": {
            "yield_on_cost": v.yield_on_cost,
            "estimated_value_a": v.estimated_value_a,
            "abatement_value_b": v.abatement_value_b,
            "total_asset_value": v.total_asset_value,
            "stabilized_ltv": v.stabilized_ltv,
            "debt_yield": v.debt_yield,
            "value_per_unit": v.value_per_unit,
            "debt_per_unit": v.debt_per_unit,
        },
        "sensitivity_base": {
            "cap_rates": model.sensitivity.cap_rates,
            "rent_growth_rates": model.sensitivity.rent_growth_rates,
            "base_cell": {
                "asset_value": model.sensitivity.cells[model.sensitivity.base_row][model.sensitivity.base_col].asset_value,
                "ltv": model.sensitivity.cells[model.sensitivity.base_row][model.sensitivity.base_col].ltv,
                "debt_yield": model.sensitivity.cells[model.sensitivity.base_row][model.sensitivity.base_col].debt_yield,
            } if model.sensitivity.cells else None,
        },
        "has_abatement": model.abatement is not None,
        "abatement_npv": model.abatement.npv_of_tax_savings if model.abatement else None,
        "condo_sellout": {
            "projected_sellout": model.condo_sellout.projected_sellout,
            "profit": model.condo_sellout.profit,
            "profit_margin_on_cost": round(model.condo_sellout.profit_margin_on_cost, 4),
            "per_unit_sellout": round(model.condo_sellout.per_unit_sellout, 0),
            "per_unit_cost": round(model.condo_sellout.per_unit_cost, 0),
            "per_sf_sellout": round(model.condo_sellout.per_sf_sellout, 2),
            "per_sf_cost": round(model.condo_sellout.per_sf_cost, 2),
            "return_on_equity": round(model.condo_sellout.return_on_equity, 4),
            "appraised_value": model.condo_sellout.appraised_value,
            "ltv": round(model.condo_sellout.ltv, 4),
        } if model.condo_sellout else None,
        "errors": model.errors,
    }


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

class GetFinancialModelTool(PlumbTool):
    name = "get_financial_model"
    description = (
        "Build the financial model from extracted deal data using the deterministic engine, "
        "then return a summary of key metrics for your review. Use this FIRST to understand "
        "the deal's financial position before making judgments."
    )
    permission = ToolPermission.AUTO

    def get_input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "deal_id": {"type": "string", "description": "The deal UUID"},
            },
            "required": ["deal_id"],
        }

    async def execute(self, _ctx: ToolContext | None = None, deal_id: str = "", **kwargs) -> ToolResult:
        deal_uuid = uuid.UUID(deal_id) if deal_id else (_ctx.deal_id if _ctx else None)
        if not deal_uuid:
            return ToolResult(success=False, error="deal_id required")

        try:
            model = await asyncio.to_thread(_build_model_sync, deal_uuid)
            return ToolResult(data=_summarize_model(model))
        except Exception as e:
            logger.exception("get_financial_model failed for deal %s", deal_uuid)
            return ToolResult(success=False, error=f"Financial model build failed: {e}")


class UpdateAssumptionsTool(PlumbTool):
    name = "update_assumptions"
    description = (
        "Re-run the financial model with adjusted assumptions. Use this when you identify "
        "that an assumption should be changed (e.g., cap rate is too aggressive). Returns "
        "the updated model summary so you can see the impact."
    )
    permission = ToolPermission.AUTO

    def get_input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "deal_id": {"type": "string"},
                "assumptions": {
                    "type": "object",
                    "description": "Assumption overrides. Only include fields you want to change.",
                    "properties": {
                        "cap_rate": {"type": "number", "description": "Exit cap rate (e.g., 0.045 for 4.5%)"},
                        "vacancy_fm": {"type": "number", "description": "Free market vacancy (e.g., 0.05 for 5%)"},
                        "vacancy_affordable": {"type": "number", "description": "Affordable vacancy rate"},
                        "vacancy_retail": {"type": "number", "description": "Retail vacancy rate"},
                        "mgmt_fee_pct": {"type": "number", "description": "Management fee percentage"},
                        "discount_rate": {"type": "number", "description": "Discount rate for NPV"},
                    },
                },
            },
            "required": ["deal_id", "assumptions"],
        }

    async def execute(self, _ctx: ToolContext | None = None, deal_id: str = "", assumptions: dict | None = None, **kwargs) -> ToolResult:
        deal_uuid = uuid.UUID(deal_id) if deal_id else (_ctx.deal_id if _ctx else None)
        if not deal_uuid:
            return ToolResult(success=False, error="deal_id required")
        if not assumptions:
            return ToolResult(success=False, error="assumptions dict required")

        try:
            model = await asyncio.to_thread(_build_model_sync, deal_uuid, assumptions)
            summary = _summarize_model(model)
            summary["assumptions_applied"] = assumptions
            return ToolResult(data=summary)
        except Exception as e:
            logger.exception("update_assumptions failed for deal %s", deal_uuid)
            return ToolResult(success=False, error=f"Model rebuild failed: {e}")


class GenerateExcelTool(PlumbTool):
    name = "generate_excel"
    description = (
        "Generate the Excel workbook from the deterministic financial model and upload to S3. "
        "Call this after you have reviewed the model and finalized assumptions."
    )
    permission = ToolPermission.AUTO

    def get_input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "deal_id": {"type": "string", "description": "The deal UUID"},
                "assumptions": {
                    "type": "object",
                    "description": "Optional final assumption overrides for the Excel output.",
                    "properties": {
                        "cap_rate": {"type": "number"},
                        "vacancy_fm": {"type": "number"},
                        "vacancy_affordable": {"type": "number"},
                        "vacancy_retail": {"type": "number"},
                        "mgmt_fee_pct": {"type": "number"},
                        "discount_rate": {"type": "number"},
                    },
                },
            },
            "required": ["deal_id"],
        }

    async def execute(self, _ctx: ToolContext | None = None, deal_id: str = "", assumptions: dict | None = None, **kwargs) -> ToolResult:
        if not _ctx or not _ctx.db:
            return ToolResult(success=False, error="ToolContext with db required")

        from app.config import settings
        from app.financial.excel_builder import build_excel
        from app.storage.s3 import _get_client

        deal_uuid = uuid.UUID(deal_id) if deal_id else _ctx.deal_id
        if not deal_uuid:
            return ToolResult(success=False, error="deal_id required")

        # Get deal name for the workbook
        from sqlalchemy import select
        from app.models.deal import Deal

        result = await _ctx.db.execute(select(Deal).where(Deal.id == deal_uuid))
        deal = result.scalar_one_or_none()
        deal_name = deal.property_name or deal.property_address or "Deal" if deal else "Deal"

        # Build model via deterministic engine, then generate Excel
        try:
            model = await asyncio.to_thread(_build_model_sync, deal_uuid, assumptions)
        except Exception as e:
            logger.exception("generate_excel: model build failed for deal %s", deal_uuid)
            return ToolResult(success=False, error=f"Financial model build failed: {e}")

        excel_bytes = await asyncio.to_thread(build_excel, model, deal_name)

        # Upload to S3
        s3_client = _get_client()
        s3_key = f"deals/{deal_uuid}/financial/model.xlsx"

        def _upload():
            s3_client.put_object(
                Bucket=settings.S3_BUCKET_NAME,
                Key=s3_key,
                Body=excel_bytes,
                ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

        await asyncio.to_thread(_upload)

        summary = _summarize_model(model)
        return ToolResult(data={
            "deal_id": str(deal_uuid),
            "s3_key": s3_key,
            "file_size": len(excel_bytes),
            "model_summary": summary,
        })
