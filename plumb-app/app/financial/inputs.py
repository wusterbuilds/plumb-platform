"""Resolve extracted values into a clean dict for the financial engine.

Handles override precedence, confidence ranking, and numeric parsing.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.financial.schemas import ResolvedField
from app.models.document import Document
from app.models.extraction import ExtractedValue

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Field-specific source-document priority
# ---------------------------------------------------------------------------
#
# Multiple documents may extract the same field_name (e.g., ``total_units``
# appears in the project_summary_deck, the pro_forma, and the appraisal).
# Historically we picked the record with the highest confidence score, which
# meant a high-confidence value from the wrong document type could overwrite
# the correct one from the authoritative source.
#
# For critical canonical fields we now prefer values from authoritative doc
# types. Lower index == higher priority. Candidates whose source document
# type is not listed fall back to pure confidence-based ranking.

FIELD_SOURCE_PRIORITY: dict[str, list[str]] = {
    # Project definition — always trust the project summary / deck first,
    # then the appraisal (independent third-party verification), then the
    # pro forma (can be a working model with stale numbers).
    "total_units": ["project_summary_deck", "appraisal", "pro_forma"],
    "units": ["project_summary_deck", "appraisal", "pro_forma"],
    "market_rate_units": ["project_summary_deck", "appraisal", "pro_forma"],
    "affordable_units": ["project_summary_deck", "zoning_approval", "appraisal"],
    "total_gsf": ["project_summary_deck", "appraisal", "pro_forma"],
    "gross_sf": ["project_summary_deck", "appraisal", "pro_forma"],
    "residential_sf": ["project_summary_deck", "appraisal", "pro_forma"],
    "commercial_sf": ["project_summary_deck", "appraisal", "pro_forma"],
    "parking_spaces": ["project_summary_deck", "appraisal", "zoning_approval"],
    "floors": ["project_summary_deck", "appraisal"],
    "unit_mix": ["project_summary_deck", "appraisal", "pro_forma"],
    # Financial metrics — the pro forma is the primary source. Appraisal is a
    # reasonable backup because it often summarizes sponsor pro forma numbers.
    "total_development_cost": ["pro_forma", "project_summary_deck", "appraisal"],
    "loan_amount": ["pro_forma", "project_summary_deck"],
    "equity_contribution": ["pro_forma", "project_summary_deck"],
    "hard_costs": ["pro_forma"],
    "soft_costs": ["pro_forma"],
    "land_cost": ["pro_forma", "appraisal"],
    # Sellout / valuation — pro forma and appraisal both speak here. The
    # appraisal is the more conservative number and is preferred for lender
    # sizing; pro forma is preferred for sponsor return metrics.
    "gross_sellout": ["appraisal", "pro_forma"],
    "projected_sellout": ["appraisal", "pro_forma"],
    "appraised_value": ["appraisal"],
    "as_complete_value": ["appraisal"],
    "as_stabilized_value": ["appraisal"],
    # Zoning — zoning approval is authoritative; project summary is a copy.
    "zoning_district": ["zoning_approval", "project_summary_deck", "appraisal"],
    "far": ["zoning_approval", "project_summary_deck"],
    "mih_option": ["zoning_approval", "project_summary_deck"],
    # Abatement — pro forma states what the sponsor wants, appraisal verifies.
    "abatement_program": ["zoning_approval", "pro_forma", "project_summary_deck"],
}

# Default priority when a field is not in the map above — simply fall back to
# confidence-only ranking by giving every doc type an equal rank.
_DEFAULT_RANK = 10_000


def _priority_rank(field_name: str, doc_type: str | None) -> int:
    """Return a sort-friendly priority rank for a (field, doc_type) pair.

    Lower is better. Unknown/missing doc types get ``_DEFAULT_RANK``.
    """
    priorities = FIELD_SOURCE_PRIORITY.get(field_name)
    if not priorities or not doc_type:
        return _DEFAULT_RANK
    try:
        return priorities.index(doc_type)
    except ValueError:
        return _DEFAULT_RANK


# ---------------------------------------------------------------------------
# Numeric parsing
# ---------------------------------------------------------------------------

_STRIP_RE = re.compile(r"[,$%\s]")
_NUMBER_RE = re.compile(r"-?[\d,]+(?:\.[\d]+)?")


def _parse_numeric(raw: str | None) -> float | None:
    """Try to extract a numeric value from a string.

    Handles "$1,234,567", "5.25%", "1 234 567", negative values, etc.
    Returns None if parsing fails.
    """
    if raw is None:
        return None
    cleaned = _STRIP_RE.sub("", str(raw))
    if not cleaned:
        return None
    # Handle parenthesized negatives like (1,234)
    neg = False
    s = str(raw).strip()
    if s.startswith("(") and s.endswith(")"):
        neg = True
        s = s[1:-1]
        cleaned = _STRIP_RE.sub("", s)
    try:
        val = float(cleaned)
        return -val if neg else val
    except ValueError:
        pass
    # Fall back to regex extraction
    m = _NUMBER_RE.search(str(raw))
    if m:
        try:
            val = float(m.group().replace(",", ""))
            return -val if neg else val
        except ValueError:
            pass
    return None


# ---------------------------------------------------------------------------
# Resolve inputs
# ---------------------------------------------------------------------------

def resolve_inputs(
    deal_id: UUID,
    db: Session,
) -> tuple[dict[str, ResolvedField], list[str]]:
    """Query all ExtractedValue records for *deal_id* and pick the best value
    for each field_name.

    Resolution order:
      1. If override_value is set, use it (was_overridden=True).
      2. Else, for fields listed in ``FIELD_SOURCE_PRIORITY``, prefer the
         extracted value from the highest-priority source document type.
      3. Within a priority tier, pick the row with the highest confidence_score.
      4. Ties broken by preferring flag='green'.

    Returns (resolved_dict, warnings).
    """
    # Pull ExtractedValue and its source Document's document_type in one go so
    # we can apply doc-type-aware priority without N+1 queries.
    stmt = (
        select(ExtractedValue, Document.document_type)
        .outerjoin(Document, ExtractedValue.source_doc_id == Document.id)
        .where(ExtractedValue.deal_id == deal_id)
    )
    rows: list[tuple[ExtractedValue, str | None]] = list(db.execute(stmt).all())

    # Group candidates by field_name, carrying the doc_type alongside.
    by_field: dict[str, list[tuple[ExtractedValue, str | None]]] = {}
    for ev, doc_type in rows:
        by_field.setdefault(ev.field_name, []).append((ev, doc_type))

    resolved: dict[str, ResolvedField] = {}
    warnings: list[str] = []
    flag_priority = {"green": 2, "yellow": 1, "red": 0}

    for field_name, candidates in by_field.items():
        chosen: ExtractedValue | None = None
        chosen_doc_type: str | None = None
        was_overridden = False

        # 1. Overrides always win; still rank by confidence within the group.
        overridden = [(c, dt) for (c, dt) in candidates if c.override_value is not None]
        if overridden:
            overridden.sort(
                key=lambda pair: (pair[0].confidence_score or 0.0),
                reverse=True,
            )
            chosen, chosen_doc_type = overridden[0]
            was_overridden = True
        else:
            # 2. Sort by (priority_rank asc, confidence desc, flag desc).
            #    Using -confidence and -flag so a single sort(reverse=False) works.
            def _sort_key(
                pair: tuple[ExtractedValue, str | None],
            ) -> tuple[int, float, int]:
                ev, dt = pair
                return (
                    _priority_rank(field_name, dt),
                    -(ev.confidence_score or 0.0),
                    -(flag_priority.get(ev.flag, 0)),
                )

            candidates.sort(key=_sort_key)
            chosen, chosen_doc_type = candidates[0]

            # Log when priority resolution overrode the pure-confidence winner
            # so we can audit disambiguations.
            top_by_conf = max(
                candidates,
                key=lambda pair: (
                    pair[0].confidence_score or 0.0,
                    flag_priority.get(pair[0].flag, 0),
                ),
            )
            if top_by_conf[0].id != chosen.id:
                warnings.append(
                    f"Field '{field_name}': preferred value from "
                    f"{chosen_doc_type or 'unknown'} (conf {chosen.confidence_score or 0:.2f}) "
                    f"over {top_by_conf[1] or 'unknown'} (conf {top_by_conf[0].confidence_score or 0:.2f}) "
                    f"via FIELD_SOURCE_PRIORITY."
                )
                logger.info(
                    "resolve_inputs: deal=%s field=%s preferred %s over %s",
                    deal_id, field_name,
                    chosen_doc_type, top_by_conf[1],
                )

        raw_value: Any
        if was_overridden and chosen is not None:
            raw_value = chosen.override_value
        else:
            raw_value = chosen.value if chosen else None

        # Try numeric parsing
        numeric = _parse_numeric(str(raw_value)) if raw_value is not None else None
        final_value: Any = numeric if numeric is not None else raw_value

        # Try JSON parsing for structured values (lists/dicts)
        if isinstance(final_value, str):
            stripped = final_value.strip()
            if (stripped.startswith("[") or stripped.startswith("{")):
                try:
                    final_value = json.loads(stripped)
                except (json.JSONDecodeError, ValueError):
                    pass

        resolved[field_name] = ResolvedField(
            field_name=field_name,
            value=final_value,
            source_doc_id=str(chosen.source_doc_id) if chosen and chosen.source_doc_id else None,
            source_page=chosen.source_page if chosen else None,
            source_text_snippet=chosen.source_text_snippet if chosen else None,
            confidence_score=chosen.confidence_score if chosen else None,
            was_overridden=was_overridden,
        )

        # Warn on low confidence or red flags
        if chosen and not was_overridden:
            if chosen.flag == "red":
                warnings.append(f"Field '{field_name}' has a red flag — value may be unreliable.")
            elif (chosen.confidence_score or 0) < 0.5:
                warnings.append(
                    f"Field '{field_name}' has low confidence ({chosen.confidence_score:.2f})."
                )

    return resolved, warnings


# ---------------------------------------------------------------------------
# Convenience accessors
# ---------------------------------------------------------------------------

def get_float(
    resolved: dict[str, ResolvedField],
    field_name: str,
    default: float | None = None,
) -> float | None:
    """Safely extract a numeric value from the resolved dict."""
    rf = resolved.get(field_name)
    if rf is None:
        return default
    if isinstance(rf.value, (int, float)):
        return float(rf.value)
    parsed = _parse_numeric(str(rf.value))
    return parsed if parsed is not None else default


def get_str(
    resolved: dict[str, ResolvedField],
    field_name: str,
    default: str | None = None,
) -> str | None:
    """Safely extract a string value from the resolved dict."""
    rf = resolved.get(field_name)
    if rf is None:
        return default
    if rf.value is None:
        return default
    return str(rf.value)


def get_list(
    resolved: dict[str, ResolvedField],
    field_name: str,
) -> list:
    """Extract a list value from the resolved dict, parsing JSON if needed."""
    rf = resolved.get(field_name)
    if rf is None:
        return []
    val = rf.value
    if isinstance(val, list):
        return val
    if isinstance(val, str):
        stripped = val.strip()
        if stripped.startswith("["):
            try:
                return json.loads(stripped)
            except (json.JSONDecodeError, ValueError):
                return []
    return []
