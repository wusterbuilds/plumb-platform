"""Interpretation prompt for CRE news search results."""

from dataclasses import dataclass, field

from app.prompts.base import PromptDefinition

SYSTEM_PROMPT = """You are a commercial real estate underwriting analyst reviewing news search results about a property, project, or developer for a construction loan deal.

You will receive a list of web search results (title, URL, description snippet) from CRE trade publications (The Real Deal, Crain's New York, Commercial Observer, Bisnow, and others).

For each result, classify its relevance:
- "material": Directly affects underwriting risk (lawsuits, project delays, financial distress, regulatory issues, construction defects, safety violations)
- "contextual": Provides useful background but doesn't change risk assessment (project announcements, market commentary, developer profiles, awards)
- "irrelevant": Not related to the deal, property, or developer

For material and contextual results, extract key facts. Discard irrelevant results entirely.

Focus on:
1. Litigation or regulatory enforcement involving the developer
2. Project delays, cost overruns, or financing difficulties
3. Developer reputation and track record
4. Market conditions affecting the specific submarket or property type
5. Community opposition or political issues"""

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "articles": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "url": {"type": "string"},
                    "relevance": {
                        "type": "string",
                        "enum": ["material", "contextual", "irrelevant"],
                    },
                    "summary": {"type": "string"},
                    "key_facts": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": ["title", "url", "relevance"],
            },
        },
        "developer_sentiment": {
            "type": "string",
            "enum": ["positive", "neutral", "mixed", "negative", "insufficient_data"],
        },
        "material_findings": {"type": "array", "items": {"type": "string"}},
        "summary": {"type": "string"},
    },
    "required": ["articles", "summary"],
}


@dataclass
class NewsRelevancePrompt(PromptDefinition):
    name: str = "interpret_news"
    version: str = "1.0.0"
    model: str = "claude-sonnet-4-6"
    system_prompt: str = SYSTEM_PROMPT
    max_output_tokens: int = 4096
    temperature: float = 0.0
    output_schema: dict = field(default_factory=lambda: OUTPUT_SCHEMA)

    def build_input(self, deal_context: dict, task_data: dict) -> list[dict]:
        return [
            {
                "role": "user",
                "content": (
                    "Classify and summarize the following news search results "
                    "for underwriting relevance.\n\n"
                    f"Search Results:\n{task_data.get('search_results', '[]')}"
                ),
            }
        ]

    def validate_output(self, result: dict) -> tuple[bool, list[str]]:
        errors = []
        if "articles" not in result:
            errors.append("Missing 'articles' in output")
        if "summary" not in result:
            errors.append("Missing 'summary' in output")
        return (len(errors) == 0, errors)
