"""Sponsor portfolio assembly — cross-references ACRIS, DOB, AG REFB, and sponsor resume."""

import logging
import uuid

from sqlalchemy.orm import Session

from app.models.extraction import ExtractedValue
from app.models.market import MarketData

logger = logging.getLogger(__name__)


def assemble_sponsor_portfolio(deal_id: uuid.UUID, db: Session) -> dict:
    """Cross-reference multiple sources to build a verified sponsor profile.

    Sources:
    1. Extracted sponsor resume (from extracted_values)
    2. ACRIS entity search (market_data, data_source=acris)
    3. DOB developer name search (market_data, data_source=dob)
    4. AG REFB sponsor search (market_data, data_source=ag_refb)
    5. News mentions (market_data, data_source=news)
    """
    sponsor_data = _get_sponsor_from_extraction(deal_id, db)
    acris_data = _get_market_data(deal_id, db, "acris")
    dob_data = _get_market_data(deal_id, db, "dob")
    ag_data = _get_market_data(deal_id, db, "ag_refb")
    news_data = _get_market_data(deal_id, db, "news")

    sponsor_name = sponsor_data.get("sponsor_name", "Unknown")
    sponsor_entities = sponsor_data.get("entities", [])
    claimed_projects = sponsor_data.get("completed_projects", [])

    acris_properties = _extract_acris_properties(acris_data)
    dob_violations = _extract_dob_portfolio(dob_data)
    ag_filings = _extract_ag_filings(ag_data)
    news_mentions = _extract_news_mentions(news_data)

    verified, unverified = _cross_reference_projects(
        claimed_projects, acris_properties, ag_filings
    )

    litigation_flags = []
    for article in news_mentions:
        if article.get("relevance") == "material":
            litigation_flags.append(article.get("summary", ""))
    for filing in ag_filings:
        if filing.get("enforcement_actions"):
            litigation_flags.extend(filing["enforcement_actions"])

    return {
        "sponsor_name": sponsor_name,
        "sponsor_entities": sponsor_entities,
        "verified_projects": verified,
        "unverified_claims": unverified,
        "violation_history": dob_violations,
        "offering_plan_history": ag_filings,
        "litigation_flags": litigation_flags,
    }


def _get_sponsor_from_extraction(deal_id: uuid.UUID, db: Session) -> dict:
    """Pull sponsor fields from extracted_values."""
    sponsor_fields = (
        db.query(ExtractedValue)
        .filter(
            ExtractedValue.deal_id == deal_id,
            ExtractedValue.field_name.like("sponsor_%"),
        )
        .all()
    )
    result = {}
    for ev in sponsor_fields:
        val = ev.override_value if ev.override_value else ev.value
        result[ev.field_name.replace("sponsor_", "")] = val
    return result


def _get_market_data(deal_id: uuid.UUID, db: Session, data_source: str) -> list[dict]:
    """Get interpreted market data for a specific source."""
    records = (
        db.query(MarketData)
        .filter(
            MarketData.deal_id == deal_id,
            MarketData.data_source == data_source,
        )
        .all()
    )
    return [r.data for r in records if r.data]


def _extract_acris_properties(acris_records: list[dict]) -> list[dict]:
    """Extract property list from ACRIS interpretation results."""
    properties = []
    for rec in acris_records:
        chain = rec.get("ownership_chain", [])
        for entry in chain:
            properties.append({
                "address": entry.get("address", "subject property"),
                "role": "owner/borrower",
                "date": entry.get("date", ""),
                "source": "acris",
            })
    return properties


def _extract_dob_portfolio(dob_records: list[dict]) -> dict:
    """Summarize DOB violation history across portfolio."""
    total_violations = 0
    open_violations = 0
    total_penalties = 0.0
    properties_count = 0

    for rec in dob_records:
        sponsor_violations = rec.get("sponsor_portfolio_violations", {})
        total_violations += sponsor_violations.get("total_violations", 0)
        open_violations += sponsor_violations.get("open_violations", 0)
        properties_count += sponsor_violations.get("properties_with_violations", 0)

        penalty_str = sponsor_violations.get("total_penalties", "0")
        try:
            total_penalties += float(str(penalty_str).replace("$", "").replace(",", ""))
        except (ValueError, TypeError):
            pass

    return {
        "total_violations": total_violations,
        "open_violations": open_violations,
        "total_penalties": f"${total_penalties:,.0f}",
        "properties_with_violations": properties_count,
    }


def _extract_ag_filings(ag_records: list[dict]) -> list[dict]:
    """Extract offering plan filings from AG REFB data."""
    filings = []
    for rec in ag_records:
        for plan in rec.get("offering_plans", []):
            filings.append(plan)
        for plan in rec.get("sponsor_other_filings", []):
            filings.append(plan)
    return filings


def _extract_news_mentions(news_records: list[dict]) -> list[dict]:
    """Extract relevant news articles."""
    articles = []
    for rec in news_records:
        for article in rec.get("articles", []):
            if article.get("relevance") in ("material", "contextual"):
                articles.append(article)
    return articles


def _cross_reference_projects(
    claimed: list, acris_properties: list[dict], ag_filings: list[dict]
) -> tuple[list[dict], list[str]]:
    """Match claimed projects against public records."""
    verified = []
    unverified = []

    public_addresses = set()
    for prop in acris_properties:
        addr = prop.get("address", "").lower()
        if addr:
            public_addresses.add(addr)
    for filing in ag_filings:
        addr = filing.get("address", "").lower()
        if addr:
            public_addresses.add(addr)

    if isinstance(claimed, list):
        for project in claimed:
            if isinstance(project, str):
                if any(project.lower() in addr for addr in public_addresses):
                    verified.append({"project": project, "verification": "address_match"})
                else:
                    unverified.append(project)
            elif isinstance(project, dict):
                name = project.get("name", project.get("project_name", ""))
                addr = project.get("address", "").lower()
                if addr and any(addr in pa for pa in public_addresses):
                    verified.append({**project, "verification": "address_match"})
                elif name and any(name.lower() in pa for pa in public_addresses):
                    verified.append({**project, "verification": "name_match"})
                else:
                    unverified.append(name or str(project))

    return verified, unverified
