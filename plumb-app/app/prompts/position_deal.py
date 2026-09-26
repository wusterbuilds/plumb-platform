"""Position Deal prompt — identify the deal story, selling points, and positioning strategy."""

import json
from dataclasses import dataclass, field

from app.prompts.base import PromptDefinition

SYSTEM_PROMPT = (
    "You are a senior capital markets advisor positioning a commercial real estate "
    "deal for lender outreach. Your job is to identify the strongest selling points, "
    "key risks to address proactively, and the overall deal narrative.\n\n"
    "Based on the deal data, market context, and target lender profiles provided, "
    "produce a positioning strategy that will resonate with the target lenders.\n\n"
    "Be specific and factual. Reference actual numbers from the deal data. "
    "Do not invent figures."
)

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "deal_story": {
            "type": "string",
            "description": "2-3 sentence elevator pitch for the deal",
        },
        "selling_points": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "point": {"type": "string"},
                    "supporting_data": {"type": "string"},
                },
                "required": ["point", "supporting_data"],
            },
            "description": "Top 3-5 selling points with supporting data",
        },
        "risk_mitigants": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "risk": {"type": "string"},
                    "mitigant": {"type": "string"},
                },
                "required": ["risk", "mitigant"],
            },
            "description": "Key risks and how to address them proactively",
        },
        "positioning_angle": {
            "type": "string",
            "description": "Overall recommended positioning angle for the OM narrative",
        },
        "lender_specific_notes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "lender_type": {"type": "string"},
                    "tailored_pitch": {"type": "string"},
                },
                "required": ["lender_type", "tailored_pitch"],
            },
            "description": "Positioning adjustments by lender type",
        },
    },
    "required": ["deal_story", "selling_points", "risk_mitigants", "positioning_angle"],
}


@dataclass
class PositionDealPrompt(PromptDefinition):
    name: str = "position_deal"
    version: str = "1.0.0"
    model: str = "claude-sonnet-4-6"
    system_prompt: str = SYSTEM_PROMPT
    max_output_tokens: int = 4096
    temperature: float = 0.3
    output_schema: dict = field(default_factory=lambda: OUTPUT_SCHEMA)

    def build_input(self, deal_context: dict, task_data: dict) -> list[dict]:
        lines = ["Analyze the following deal and produce a positioning strategy:", ""]

        # Deal context
        if deal_context:
            lines.append("## Deal Data")
            lines.append(json.dumps(deal_context, indent=2, default=str)[:6000])
            lines.append("")

        # Target lenders
        target_lenders = task_data.get("target_lenders", [])
        if target_lenders:
            lines.append("## Target Lenders")
            lines.append(json.dumps(target_lenders, indent=2, default=str)[:3000])
            lines.append("")

        return [{"role": "user", "content": "\n".join(lines)}]

    def validate_output(self, result: dict) -> tuple[bool, list[str]]:
        errors: list[str] = []
        if not result.get("deal_story"):
            errors.append("Missing 'deal_story'")
        if not result.get("selling_points"):
            errors.append("Missing 'selling_points'")
        if not result.get("positioning_angle"):
            errors.append("Missing 'positioning_angle'")
        return (len(errors) == 0, errors)
