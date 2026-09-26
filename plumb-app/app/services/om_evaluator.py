"""Sprint 5: LLM-as-Judge for OM quality — automated quality scoring on 4 dimensions."""

import anthropic

from app.config import settings


async def evaluate_om(
    om_sections: dict,
    financial_model: dict,
    deal_context: dict,
) -> dict:
    """Score an OM draft on factual accuracy, narrative quality, completeness, and lender-readiness."""
    client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

    evaluation_prompt = f"""You are evaluating an Offering Memorandum for a commercial real estate deal.

## OM Sections:
{_format_sections(om_sections)}

## Financial Model (source of truth for numbers):
{_format_dict(financial_model)}

## Deal Context:
{_format_dict(deal_context)}

## Evaluate on these 4 dimensions (score 1-10 each):

1. **Factual Accuracy**: Do all numbers in the OM match the financial model? Are market claims supported?
2. **Narrative Quality**: Does it read naturally with professional tone? Is it compelling without being salesy?
3. **Completeness**: Are all required sections present? Sufficient detail in each?
4. **Lender-Readiness**: Would a lender take this seriously? Is it presentation-quality?

For each dimension, provide:
- Score (1-10)
- Specific issues found (if any)
- Suggestions for improvement
"""

    response = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        temperature=0,
        system="You are an expert CRE OM quality evaluator. Return your evaluation as structured JSON.",
        messages=[{"role": "user", "content": evaluation_prompt}],
        tools=[{
            "name": "om_evaluation",
            "description": "Structured OM quality evaluation",
            "input_schema": {
                "type": "object",
                "properties": {
                    "factual_accuracy": {
                        "type": "object",
                        "properties": {
                            "score": {"type": "integer", "minimum": 1, "maximum": 10},
                            "issues": {"type": "array", "items": {"type": "string"}},
                            "suggestions": {"type": "array", "items": {"type": "string"}},
                        },
                    },
                    "narrative_quality": {
                        "type": "object",
                        "properties": {
                            "score": {"type": "integer", "minimum": 1, "maximum": 10},
                            "issues": {"type": "array", "items": {"type": "string"}},
                            "suggestions": {"type": "array", "items": {"type": "string"}},
                        },
                    },
                    "completeness": {
                        "type": "object",
                        "properties": {
                            "score": {"type": "integer", "minimum": 1, "maximum": 10},
                            "issues": {"type": "array", "items": {"type": "string"}},
                            "suggestions": {"type": "array", "items": {"type": "string"}},
                        },
                    },
                    "lender_readiness": {
                        "type": "object",
                        "properties": {
                            "score": {"type": "integer", "minimum": 1, "maximum": 10},
                            "issues": {"type": "array", "items": {"type": "string"}},
                            "suggestions": {"type": "array", "items": {"type": "string"}},
                        },
                    },
                    "overall_score": {"type": "number"},
                    "overall_assessment": {"type": "string"},
                },
                "required": ["factual_accuracy", "narrative_quality", "completeness", "lender_readiness", "overall_score"],
            },
        }],
        tool_choice={"type": "tool", "name": "om_evaluation"},
    )

    for block in response.content:
        if block.type == "tool_use":
            return block.input
    return {"error": "No evaluation generated"}


def _format_sections(sections: dict) -> str:
    parts = []
    for name, content in sections.items():
        parts.append(f"### {name}\n{content}\n")
    return "\n".join(parts)


def _format_dict(d: dict) -> str:
    import json
    return json.dumps(d, indent=2, default=str)[:4000]
