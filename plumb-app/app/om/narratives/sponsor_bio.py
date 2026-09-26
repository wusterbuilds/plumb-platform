"""Sponsor Bio narrative prompt for the OM Development Team Overview."""

from dataclasses import dataclass, field

from app.prompts.base import PromptDefinition

SYSTEM_PROMPT = (
    "You are a senior capital markets analyst writing a sponsor biography "
    "for a confidential financing memorandum for a commercial real estate "
    "construction loan.\n\n"
    "Write 3-4 paragraphs in formal, third-person style about the sponsor's "
    "experience, track record, and qualifications.\n\n"
    "HARD WORD BUDGET: Each paragraph MUST be 55-75 words. Total across all "
    "paragraphs MUST be 200-280 words. Longer text is clipped by the page "
    "layout. Err shorter, never longer. Count your words before returning.\n\n"
    "CRITICAL RULES:\n"
    "- Be SPECIFIC with numbers: name each completed project, cite unit counts, "
    "square footages, and dollar values. Write 'Mr. Lam has developed over 890 "
    "units across 5 projects totaling $1.2B in development value' — not 'the "
    "sponsor has extensive development experience'.\n"
    "- NEVER use vague qualifiers ('significant', 'substantial', 'extensive', "
    "'considerable') when specific data is available.\n"
    "- Reference specific project names and locations from the completed projects "
    "list. If 5 projects are listed, mention them by name.\n"
    "- Do not invent facts — use only what is provided.\n\n"
    "Paragraph 1: Name the sponsor entity and principal(s) by name. State "
    "exact years of experience, geographic focus, and asset class focus.\n\n"
    "Paragraph 2 (if data available): Describe the track record with specific "
    "numbers — total completed projects, total units, total development value. "
    "Name 2-3 notable completed projects with their unit counts and values.\n\n"
    "Paragraph 3 (if data available): Highlight credentials, awards, or "
    "notable achievements. Reference specific items.\n\n"
    "Paragraph 4 (if data available): Describe current pipeline with project "
    "names, unit counts, and expected completion dates.\n\n"
    "Keep the tone professional and factual. This is a debt pitch — "
    "emphasize reliability, execution capability, and local market expertise "
    "over aspirational language."
)

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "paragraphs": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 1,
            "maxItems": 4,
        }
    },
    "required": ["paragraphs"],
}


def _fmt_currency(value) -> str:
    if value is None:
        return "N/A"
    try:
        return f"${float(value):,.0f}"
    except (TypeError, ValueError):
        return str(value)


@dataclass
class SponsorBioPrompt(PromptDefinition):
    name: str = "generate_sponsor_bio"
    version: str = "2.0.0"
    model: str = "claude-sonnet-4-6"
    system_prompt: str = SYSTEM_PROMPT
    max_output_tokens: int = 4096
    temperature: float = 0.3
    output_schema: dict = field(default_factory=lambda: OUTPUT_SCHEMA)

    def build_input(self, deal_context: dict, task_data: dict) -> list[dict]:
        """Build user message with sponsor data.

        The caller passes {"sponsor": <sponsor_dict>} in task_data.
        The sponsor dict comes from deal.sponsor (a list of sponsor dicts,
        each structured per extraction_bridge._resolve_extracted_sponsor).

        Keys in sponsor dict:
            name, sponsor_name, sponsor_entity, principal_names,
            years_experience, completed_projects (list of dicts),
            current_projects (list of dicts), total_units_developed,
            total_sf_developed, total_development_value,
            credentials (list of strings),
            notable_achievements (list of strings),
            background (str)
        """
        # The sponsor dict is nested under "sponsor" key in task_data
        sd = task_data.get("sponsor", task_data)

        lines = [
            "Write a sponsor biography based on the following data.",
            "IMPORTANT: Name every completed project, cite specific unit counts, "
            "dollar values, and years. Never summarize vaguely when specifics exist.",
            "",
            f"Sponsor Name: {sd.get('sponsor_name') or sd.get('name', 'N/A')}",
            f"Entity Name: {sd.get('sponsor_entity', 'N/A')}",
        ]

        # Principals
        principals = sd.get("principal_names")
        if principals:
            if isinstance(principals, list):
                lines.append(f"Principal(s): {', '.join(str(p) for p in principals)}")
            else:
                lines.append(f"Principal(s): {principals}")

        lines.append(f"Years of Experience: {sd.get('years_experience', 'N/A')}")

        # Background
        background = sd.get("background")
        if background:
            lines.append("")
            lines.append("--- Background ---")
            lines.append(str(background))

        # Track record summary
        lines.append("")
        lines.append("--- Track Record Summary ---")
        lines.append(f"Total Units Developed: {sd.get('total_units_developed', 'N/A')}")
        lines.append(f"Total Sq. Ft. Developed: {sd.get('total_sf_developed', 'N/A')}")
        lines.append(f"Total Development Value: {_fmt_currency(sd.get('total_development_value'))}")

        # Completed projects — list every one with full details
        completed = sd.get("completed_projects")
        if completed and isinstance(completed, list):
            lines.append("")
            lines.append(f"--- Completed Projects ({len(completed)} total — name each in the bio) ---")
            for p in completed:
                if isinstance(p, dict):
                    name = p.get("name", p.get("project_name", "Unnamed"))
                    location = p.get("location", "")
                    units = p.get("units", "")
                    sf = p.get("sf", "")
                    value = p.get("value")
                    year = p.get("year_completed", "")
                    asset_type = p.get("type", p.get("asset_type", ""))
                    detail = f"- {name}"
                    if location:
                        detail += f", {location}"
                    if asset_type:
                        detail += f" ({asset_type})"
                    if units:
                        detail += f", {units} units"
                    if sf:
                        detail += f", {sf:,} SF" if isinstance(sf, (int, float)) else f", {sf} SF"
                    if value:
                        detail += f", {_fmt_currency(value)}"
                    if year:
                        detail += f" (completed {year})"
                    lines.append(detail)
                else:
                    lines.append(f"- {p}")

        # Current projects
        current = sd.get("current_projects")
        if current and isinstance(current, list):
            lines.append("")
            lines.append(f"--- Current Projects ({len(current)} total) ---")
            for p in current:
                if isinstance(p, dict):
                    name = p.get("name", p.get("project_name", "Unnamed"))
                    location = p.get("location", "")
                    units = p.get("units", "")
                    status = p.get("status", "")
                    expected = p.get("expected_completion", "")
                    value = p.get("value")
                    detail = f"- {name}"
                    if location:
                        detail += f", {location}"
                    if units:
                        detail += f", {units} units"
                    if value:
                        detail += f", {_fmt_currency(value)}"
                    if status:
                        detail += f" [{status}]"
                    if expected:
                        detail += f" (expected {expected})"
                    lines.append(detail)
                else:
                    lines.append(f"- {p}")

        # Credentials
        credentials = sd.get("credentials")
        if credentials and isinstance(credentials, list):
            lines.append("")
            lines.append("--- Credentials ---")
            for c in credentials:
                lines.append(f"- {c}")

        # Notable achievements
        achievements = sd.get("notable_achievements")
        if achievements and isinstance(achievements, list):
            lines.append("")
            lines.append("--- Notable Achievements ---")
            for a in achievements:
                lines.append(f"- {a}")

        return [{"role": "user", "content": "\n".join(lines)}]

    def validate_output(self, result: dict) -> tuple[bool, list[str]]:
        errors: list[str] = []
        paragraphs = result.get("paragraphs")
        if paragraphs is None:
            errors.append("Missing 'paragraphs' in output")
            return (False, errors)
        if isinstance(paragraphs, str):
            paragraphs = [paragraphs]
            result["paragraphs"] = paragraphs
        if not isinstance(paragraphs, list):
            errors.append("'paragraphs' must be a list")
            return (False, errors)
        if len(paragraphs) < 1 or len(paragraphs) > 4:
            errors.append(f"Expected 1-4 paragraphs, got {len(paragraphs)}")
        total_words = 0
        for i, p in enumerate(paragraphs):
            if not isinstance(p, str) or not p.strip():
                errors.append(f"Paragraph {i + 1} must be a non-empty string")
                continue
            wc = len(p.split())
            total_words += wc
            if wc > 85:
                errors.append(
                    f"Paragraph {i + 1} is {wc} words, exceeds 75-word hard limit (would overflow page). Rewrite shorter."
                )
        if total_words > 300:
            errors.append(
                f"Total sponsor bio {total_words} words exceeds 280-word page budget. Rewrite shorter."
            )
        return (len(errors) == 0, errors)
