"""Seed lender universe for NYC condo construction

Revision ID: 007
Revises: 006
Create Date: 2026-04-10
"""

import uuid
from datetime import datetime, timedelta, timezone

from alembic import op
import sqlalchemy as sa

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


# Construction/condo lender universe — NYC focused, mix of bank / debt fund / insurance /
# private credit. Numbers are demo values; calibrate against real appetite data in prod.
LENDERS = [
    # ---- Money-center / regional banks ----
    {
        "name": "Signature Bank CRE",
        "lender_type": "bank",
        "general_preferences": {"product": "construction", "recourse": "partial"},
        "credit_committee_notes": "Committee focused on sponsor liquidity coverage (1.25x min) and absorption underwriting vs comps trailing 6 months.",
        "relationship_contacts": [{"name": "M. Rosen", "role": "Head of NYC CRE"}],
        "notes": "Active NYC lender; prefers Brooklyn and Manhattan core submarkets.",
        "appetite": {
            "property_types": ["condo", "multifamily"],
            "geographies": ["NYC", "Brooklyn", "Manhattan", "Queens"],
            "deal_size_min": 20_000_000,
            "deal_size_max": 150_000_000,
            "ltc_max": 0.65,
            "rate_indication": "SOFR + 325-375",
            "term_range": "24-30 mo + ext",
            "recourse_preference": "partial",
            "appetite_signal": "active",
        },
    },
    {
        "name": "Valley National Bank",
        "lender_type": "bank",
        "credit_committee_notes": "Conservative underwriter; wants 25% sponsor equity and 1.20x completion guaranty.",
        "notes": "Balance-sheet lender; strong in outer borough multifamily and mixed-use.",
        "appetite": {
            "property_types": ["multifamily", "condo", "mixed-use"],
            "geographies": ["NYC", "Brooklyn", "Bronx", "Queens"],
            "deal_size_min": 15_000_000,
            "deal_size_max": 100_000_000,
            "ltc_max": 0.60,
            "rate_indication": "SOFR + 300-350",
            "term_range": "24 mo + 2x6",
            "recourse_preference": "full",
            "appetite_signal": "selective",
        },
    },
    {
        "name": "Dime Community Bank",
        "lender_type": "bank",
        "credit_committee_notes": "Focus on repeat sponsors; strong Brooklyn/Queens relationship book.",
        "notes": "Relationship-driven; decisions by loan committee on Thursdays.",
        "appetite": {
            "property_types": ["multifamily", "condo"],
            "geographies": ["Brooklyn", "Queens"],
            "deal_size_min": 10_000_000,
            "deal_size_max": 80_000_000,
            "ltc_max": 0.60,
            "rate_indication": "SOFR + 325",
            "term_range": "24-30 mo",
            "recourse_preference": "partial",
            "appetite_signal": "active",
        },
    },
    {
        "name": "Webster Bank CRE",
        "lender_type": "bank",
        "credit_committee_notes": "Requires experienced GC (5+ comparable deliveries); underwrites at 50 bps above in-place rates.",
        "notes": "Tri-state regional bank; active in NYC condo construction.",
        "appetite": {
            "property_types": ["condo", "multifamily", "mixed-use"],
            "geographies": ["NYC", "Manhattan", "Brooklyn"],
            "deal_size_min": 25_000_000,
            "deal_size_max": 120_000_000,
            "ltc_max": 0.625,
            "rate_indication": "SOFR + 350",
            "term_range": "24 mo + 2x6",
            "recourse_preference": "partial",
            "appetite_signal": "active",
        },
    },
    {
        "name": "M&T Realty Capital",
        "lender_type": "bank",
        "credit_committee_notes": "Tight on SOFR volatility; asks for a 50 bps rate lock fee.",
        "notes": "Institutional balance-sheet lender with strong NYC coverage.",
        "appetite": {
            "property_types": ["condo", "multifamily"],
            "geographies": ["NYC", "Manhattan", "Brooklyn"],
            "deal_size_min": 30_000_000,
            "deal_size_max": 200_000_000,
            "ltc_max": 0.60,
            "rate_indication": "SOFR + 300-350",
            "term_range": "24-30 mo",
            "recourse_preference": "partial",
            "appetite_signal": "selective",
        },
    },
    # ---- Debt funds / private credit ----
    {
        "name": "Madison Realty Capital",
        "lender_type": "debt_fund",
        "credit_committee_notes": "Aggressive on leverage; wants 18%+ developer margin on cost; prefers markup-to-market on absorption.",
        "notes": "NYC-based debt fund; closes fast, 70% LTC available for strong sponsors.",
        "appetite": {
            "property_types": ["condo", "multifamily", "mixed-use", "hotel"],
            "geographies": ["NYC", "Manhattan", "Brooklyn", "Queens"],
            "deal_size_min": 40_000_000,
            "deal_size_max": 400_000_000,
            "ltc_max": 0.70,
            "rate_indication": "SOFR + 550-700",
            "term_range": "24-36 mo",
            "recourse_preference": "non-recourse",
            "appetite_signal": "hungry",
        },
    },
    {
        "name": "G4 Capital Partners",
        "lender_type": "debt_fund",
        "credit_committee_notes": "Likes bridge-to-construction; higher coupon but flexible on milestones.",
        "notes": "Active bridge/construction lender in NYC; open to GP co-invest structures.",
        "appetite": {
            "property_types": ["condo", "multifamily"],
            "geographies": ["NYC", "Brooklyn", "Manhattan"],
            "deal_size_min": 25_000_000,
            "deal_size_max": 200_000_000,
            "ltc_max": 0.70,
            "rate_indication": "SOFR + 600-750",
            "term_range": "24 mo",
            "recourse_preference": "non-recourse",
            "appetite_signal": "active",
        },
    },
    {
        "name": "Silverstein Capital Partners",
        "lender_type": "debt_fund",
        "credit_committee_notes": "Will stretch to 75% LTC on trophy assets with recognized sponsors.",
        "notes": "High-leverage construction debt for marquee NYC projects.",
        "appetite": {
            "property_types": ["condo", "mixed-use", "office"],
            "geographies": ["Manhattan", "Brooklyn"],
            "deal_size_min": 100_000_000,
            "deal_size_max": 600_000_000,
            "ltc_max": 0.75,
            "rate_indication": "SOFR + 550-650",
            "term_range": "30-42 mo",
            "recourse_preference": "non-recourse",
            "appetite_signal": "selective",
        },
    },
    {
        "name": "RXR Realty Debt",
        "lender_type": "debt_fund",
        "credit_committee_notes": "Credit committee sensitive to submarket absorption; wants updated comp set <90 days old.",
        "notes": "Opportunistic construction debt; NYC focused.",
        "appetite": {
            "property_types": ["condo", "multifamily"],
            "geographies": ["NYC", "Manhattan", "Brooklyn"],
            "deal_size_min": 50_000_000,
            "deal_size_max": 300_000_000,
            "ltc_max": 0.68,
            "rate_indication": "SOFR + 500-600",
            "term_range": "24-30 mo",
            "recourse_preference": "non-recourse",
            "appetite_signal": "active",
        },
    },
    {
        "name": "Bain Capital Real Estate Credit",
        "lender_type": "debt_fund",
        "credit_committee_notes": "Institutional-quality sponsors only; prefers 60-65% LTC.",
        "notes": "Large-cap debt fund; likes high-rise condo with absorbing submarkets.",
        "appetite": {
            "property_types": ["condo", "multifamily", "mixed-use"],
            "geographies": ["NYC", "Manhattan"],
            "deal_size_min": 75_000_000,
            "deal_size_max": 500_000_000,
            "ltc_max": 0.65,
            "rate_indication": "SOFR + 475-550",
            "term_range": "30-36 mo",
            "recourse_preference": "non-recourse",
            "appetite_signal": "active",
        },
    },
    {
        "name": "Blackstone Real Estate Debt Strategies",
        "lender_type": "debt_fund",
        "credit_committee_notes": "Underwrites to trough rents; requires 25% equity and recognized sponsor.",
        "notes": "Institutional construction debt; closes with large commitments.",
        "appetite": {
            "property_types": ["condo", "multifamily", "office", "industrial"],
            "geographies": ["NYC", "Manhattan", "Brooklyn"],
            "deal_size_min": 100_000_000,
            "deal_size_max": 750_000_000,
            "ltc_max": 0.65,
            "rate_indication": "SOFR + 450-525",
            "term_range": "30-42 mo",
            "recourse_preference": "non-recourse",
            "appetite_signal": "selective",
        },
    },
    # ---- Insurance co / pension ----
    {
        "name": "MetLife Investment Management",
        "lender_type": "insurance",
        "credit_committee_notes": "Long-dated capital; prefers completion-to-perm with takeout.",
        "notes": "Insurance balance sheet; very selective but attractive pricing.",
        "appetite": {
            "property_types": ["condo", "multifamily", "office"],
            "geographies": ["NYC", "Manhattan"],
            "deal_size_min": 75_000_000,
            "deal_size_max": 400_000_000,
            "ltc_max": 0.60,
            "rate_indication": "SOFR + 275-325",
            "term_range": "36-48 mo",
            "recourse_preference": "partial",
            "appetite_signal": "selective",
        },
    },
    {
        "name": "Pacific Life Real Estate Finance",
        "lender_type": "insurance",
        "credit_committee_notes": "Very selective on construction; requires 1.35x DSCR at takeout.",
        "notes": "Insurance company; stretches on pricing for low-LTC deals.",
        "appetite": {
            "property_types": ["condo", "multifamily"],
            "geographies": ["NYC", "Manhattan", "Brooklyn"],
            "deal_size_min": 50_000_000,
            "deal_size_max": 250_000_000,
            "ltc_max": 0.55,
            "rate_indication": "SOFR + 250-300",
            "term_range": "36 mo",
            "recourse_preference": "partial",
            "appetite_signal": "selective",
        },
    },
    # ---- Family office / specialty ----
    {
        "name": "Kohl Partners",
        "lender_type": "family_office",
        "credit_committee_notes": "Prefers relationship sponsors; flexible on structure, rigid on sponsor equity.",
        "notes": "NYC family office active in small-to-mid construction checks.",
        "appetite": {
            "property_types": ["condo", "multifamily", "mixed-use"],
            "geographies": ["Brooklyn", "Queens", "Manhattan"],
            "deal_size_min": 15_000_000,
            "deal_size_max": 75_000_000,
            "ltc_max": 0.65,
            "rate_indication": "SOFR + 500-600",
            "term_range": "24-30 mo",
            "recourse_preference": "partial",
            "appetite_signal": "active",
        },
    },
    {
        "name": "Related Fund Management",
        "lender_type": "debt_fund",
        "credit_committee_notes": "Selective; prefers trophy Manhattan assets and repeat sponsors.",
        "notes": "Related Companies' debt arm; very active in NYC condo construction.",
        "appetite": {
            "property_types": ["condo", "mixed-use"],
            "geographies": ["Manhattan", "Brooklyn"],
            "deal_size_min": 75_000_000,
            "deal_size_max": 500_000_000,
            "ltc_max": 0.68,
            "rate_indication": "SOFR + 475-575",
            "term_range": "30-36 mo",
            "recourse_preference": "non-recourse",
            "appetite_signal": "active",
        },
    },
]


def upgrade() -> None:
    lenders_tbl = sa.table(
        "lenders",
        sa.column("id", sa.UUID),
        sa.column("name", sa.String),
        sa.column("lender_type", sa.String),
        sa.column("general_preferences", sa.JSON),
        sa.column("credit_committee_notes", sa.Text),
        sa.column("relationship_contacts", sa.JSON),
        sa.column("notes", sa.Text),
    )
    appetite_tbl = sa.table(
        "lender_appetite",
        sa.column("id", sa.UUID),
        sa.column("lender_id", sa.UUID),
        sa.column("property_types", sa.JSON),
        sa.column("geographies", sa.JSON),
        sa.column("deal_size_min", sa.Float),
        sa.column("deal_size_max", sa.Float),
        sa.column("ltc_max", sa.Float),
        sa.column("rate_indication", sa.String),
        sa.column("term_range", sa.String),
        sa.column("recourse_preference", sa.String),
        sa.column("appetite_signal", sa.String),
        sa.column("source", sa.String),
        sa.column("recorded_at", sa.DateTime),
        sa.column("expires_at", sa.DateTime),
        sa.column("is_stale", sa.Boolean),
    )

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    lender_rows = []
    appetite_rows = []

    for entry in LENDERS:
        lender_id = uuid.uuid4()
        lender_rows.append({
            "id": lender_id,
            "name": entry["name"],
            "lender_type": entry["lender_type"],
            "general_preferences": entry.get("general_preferences"),
            "credit_committee_notes": entry.get("credit_committee_notes"),
            "relationship_contacts": entry.get("relationship_contacts", []),
            "notes": entry.get("notes"),
        })
        a = entry["appetite"]
        appetite_rows.append({
            "id": uuid.uuid4(),
            "lender_id": lender_id,
            "property_types": a.get("property_types"),
            "geographies": a.get("geographies"),
            "deal_size_min": a.get("deal_size_min"),
            "deal_size_max": a.get("deal_size_max"),
            "ltc_max": a.get("ltc_max"),
            "rate_indication": a.get("rate_indication"),
            "term_range": a.get("term_range"),
            "recourse_preference": a.get("recourse_preference"),
            "appetite_signal": a.get("appetite_signal", "active"),
            "source": "seed",
            "recorded_at": now,
            "expires_at": now + timedelta(days=90),
            "is_stale": False,
        })

    op.bulk_insert(lenders_tbl, lender_rows)
    op.bulk_insert(appetite_tbl, appetite_rows)


def downgrade() -> None:
    names = [l["name"] for l in LENDERS]
    op.execute(
        sa.text("DELETE FROM lender_appetite WHERE lender_id IN (SELECT id FROM lenders WHERE name = ANY(:names))")
        .bindparams(sa.bindparam("names", names, expanding=True))
    )
    op.execute(
        sa.text("DELETE FROM lenders WHERE name = ANY(:names)")
        .bindparams(sa.bindparam("names", names, expanding=True))
    )
