"""Shared fixtures for Phase 2 market intelligence tests."""

import io
import uuid

import pytest
import pytest_asyncio

from app.fetchers.nyc.geoclient import GeoResult


@pytest.fixture
def mock_geo_result() -> GeoResult:
    """Canned GeoResult for 50 West 66th Street, Manhattan."""
    return GeoResult(
        bbl="1011230001",
        bbl_numeric=1011230001,
        bin="1022571",
        borough="1",
        block="01123",
        lot="0001",
        latitude=40.7747,
        longitude=-73.9810,
        label="50 West 66th Street, New York, NY",
    )


@pytest.fixture
def sample_deal_id() -> uuid.UUID:
    return uuid.uuid4()


# ---------------------------------------------------------------------------
# Synthetic CSV/XLSX fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def costar_comp_csv_bytes() -> bytes:
    """Valid CoStar comparable transactions CSV."""
    csv_text = (
        "Property Name,Property Address,Sale Price,Price/Unit,Price/SF,Cap Rate,Sale Date,Buyer,Seller\n"
        "One Manhattan West,401 9th Ave,150000000,500000,1200,4.5%,2024-01-15,Brookfield,Seller A\n"
        "Hudson Yards Tower,500 W 33rd St,200000000,600000,1500,4.2%,2024-03-20,Related,Seller B\n"
        "Riverside Center,21 W End Ave,80000000,400000,950,5.1%,2023-11-10,Extell,Seller C\n"
    )
    return csv_text.encode("utf-8")


@pytest.fixture
def costar_market_csv_bytes() -> bytes:
    """Valid CoStar market statistics CSV."""
    csv_text = (
        "Submarket,Vacancy Rate,Asking Rent,Effective Rent,Net Absorption,Under Construction SF\n"
        "Midtown West,8.2%,$85.50,$82.00,150000,2500000\n"
        "Upper West Side,4.1%,$72.00,$69.50,85000,500000\n"
    )
    return csv_text.encode("utf-8")


@pytest.fixture
def marketproof_csv_bytes() -> bytes:
    """Valid MarketProof new development CSV."""
    csv_text = (
        "Building Name,Address,Unit,Price,PPSF,Closing Date,Floor,Bedrooms,Sqft,Status\n"
        "The Emerson,500 W 66th St,12A,$2100000,$1850,2024-02-15,12,2,1135,Closed\n"
        "Waterline Square,10 Riverside Blvd,8B,$3500000,$2100,2024-04-01,8,3,1667,Closed\n"
        "One West End,1 West End Ave,15C,$1650000,$1700,2023-12-20,15,1,970,Closed\n"
    )
    return csv_text.encode("utf-8")


@pytest.fixture
def argus_dcf_xlsx_bytes() -> bytes:
    """Minimal Argus DCF workbook with Cash Flow sheet."""
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Cash Flow"
    ws.append(["Year", "1", "2", "3", "4", "5"])
    ws.append(["Net Operating Income", "500000", "520000", "540000", "560000", "580000"])
    ws.append(["Exit Cap Rate", "5.5%"])
    ws.append(["Discount Rate", "8.0%"])
    ws.append(["NPV", "4500000"])
    ws.append(["IRR", "12.5%"])

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Canned Socrata API responses
# ---------------------------------------------------------------------------


CANNED_GEOSEARCH_RESPONSE = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [-73.9810, 40.7747]},
            "properties": {
                "label": "50 West 66th Street, New York, NY",
                "addendum": {
                    "pad": {
                        "bbl": "1011230001",
                        "bin": "1022571",
                    }
                },
            },
        }
    ],
}


CANNED_ACRIS_LEGALS = [
    {
        "document_id": "DOC001",
        "borough": "1",
        "block": "01123",
        "lot": "0001",
        "good_through_date": "2024-01-01",
    },
    {
        "document_id": "DOC002",
        "borough": "1",
        "block": "01123",
        "lot": "0001",
        "good_through_date": "2023-06-15",
    },
]


CANNED_ACRIS_MASTERS = [
    {
        "document_id": "DOC001",
        "doc_type": "DEED",
        "doc_amount": "15000000",
        "recorded_datetime": "2024-01-01",
    },
    {
        "document_id": "DOC002",
        "doc_type": "MTGE",
        "doc_amount": "10000000",
        "recorded_datetime": "2023-06-15",
    },
]


CANNED_ACRIS_PARTIES = [
    {"document_id": "DOC001", "party_type": "1", "name": "SELLER LLC"},
    {"document_id": "DOC001", "party_type": "2", "name": "BUYER LLC"},
    {"document_id": "DOC002", "party_type": "1", "name": "BUYER LLC"},
    {"document_id": "DOC002", "party_type": "2", "name": "BANK OF NY"},
]


CANNED_PLUTO_RESPONSE = [
    {
        "zonedist1": "R8",
        "zonedist2": None,
        "overlay1": "C1-5",
        "overlay2": None,
        "spdist1": "LM",
        "spdist2": None,
        "splitzone": "N",
        "residfar": "6.02",
        "commfar": "2.0",
        "facilfar": "6.5",
        "lotarea": "15000",
        "bldgarea": "85000",
        "bldgclass": "R4",
        "landuse": "02",
        "ownername": "TEST OWNER LLC",
        "yearbuilt": "1965",
        "numfloors": "15",
        "unitsres": "120",
        "unitstotal": "125",
        "lotfront": "100",
        "lotdepth": "150",
        "assessland": "5000000",
        "assesstot": "25000000",
        "borocode": "1",
        "cd": "107",
        "ct2010": "123456",
        "zipcode": "10023",
        "firecomp": "E40",
        "policeprct": "20",
        "sanitboro": "1",
    }
]


CANNED_DOB_JOB_FILINGS = [
    {"bin": "1022571", "job_type": "NB", "filing_status": "APPROVED", "filing_date": "2024-01-10"},
]

CANNED_DOB_VIOLATIONS = [
    {"bin": "1022571", "violation_type": "LL6291", "penalty_applied": "1500", "violation_date": "2023-08-01"},
]

CANNED_DOB_PERMITS = [
    {"bin": "1022571", "permit_type": "NB", "permit_status": "ISSUED", "issuance_date": "2024-03-01"},
]

CANNED_BRAVE_RESULTS = {
    "web": {
        "results": [
            {
                "title": "New Condo Tower Planned for Upper West Side",
                "url": "https://therealdeal.com/article1",
                "description": "Developer plans 40-story condo at 50 West 66th Street",
                "age": "2 months",
            },
            {
                "title": "UWS Development Faces Community Opposition",
                "url": "https://commercialobserver.com/article2",
                "description": "Community board votes against proposed tower",
                "age": "1 month",
            },
        ]
    }
}
