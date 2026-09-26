"""Field definitions per document type for construction loan extraction."""

from dataclasses import dataclass


@dataclass
class FieldSpec:
    name: str
    description: str
    required: bool = True
    field_type: str = "string"  # string, number, list, object


# --- Project Summary Deck ---
PROJECT_SUMMARY_FIELDS = [
    FieldSpec("property_address", "Full property address"),
    FieldSpec("project_name", "Project name or title", required=False),
    FieldSpec("total_units", "Total number of residential units", field_type="number"),
    FieldSpec("market_rate_units", "Number of market-rate units", field_type="number", required=False),
    FieldSpec("affordable_units", "Number of affordable/income-restricted units", field_type="number", required=False),
    FieldSpec("total_gsf", "Total gross square footage", field_type="number", required=False),
    FieldSpec("residential_sf", "Residential square footage", field_type="number", required=False),
    FieldSpec("commercial_sf", "Commercial/retail square footage", field_type="number", required=False),
    FieldSpec("community_facility_sf", "Community facility square footage", field_type="number", required=False),
    FieldSpec("parking_spaces", "Number of parking spaces", field_type="number", required=False),
    FieldSpec("floors", "Number of floors/stories", field_type="number", required=False),
    FieldSpec("zoning_district", "Zoning district designation", required=False),
    FieldSpec("far", "Floor area ratio", field_type="number", required=False),
    FieldSpec("lot_area", "Lot area in square feet", field_type="number", required=False),
    FieldSpec("building_class", "Building class or type description", required=False),
    FieldSpec("construction_type", "Construction type (e.g., concrete, steel frame)", required=False),
    FieldSpec("unit_mix", "Unit mix breakdown by type (studio, 1BR, 2BR, etc.)", field_type="list", required=False),
    FieldSpec("amenities", "Building amenities list", field_type="list", required=False),
    FieldSpec("completion_date", "Expected completion or delivery date", required=False),
    FieldSpec("construction_start_date", "Construction start date", required=False),
    FieldSpec("project_timeline", "Project development timeline description", required=False),
    FieldSpec("total_development_cost", "Total development cost", field_type="number", required=False),
    FieldSpec("borough", "NYC borough", required=False),
    FieldSpec("neighborhood", "Neighborhood name", required=False),
    FieldSpec("block", "Tax block number", required=False),
    FieldSpec("lot", "Tax lot number", required=False),
]

# --- Pro Forma ---
PRO_FORMA_FIELDS = [
    FieldSpec("total_development_cost", "Total development cost / total project cost", field_type="number"),
    FieldSpec("land_cost", "Land acquisition cost", field_type="number"),
    FieldSpec("hard_costs", "Total hard construction costs", field_type="number"),
    FieldSpec("soft_costs", "Total soft costs (design, legal, financing, etc.)", field_type="number"),
    FieldSpec("financing_costs", "Financing/interest costs during construction", field_type="number", required=False),
    FieldSpec("contingency", "Contingency amount", field_type="number", required=False),
    FieldSpec("equity_contribution", "Total equity contribution", field_type="number"),
    FieldSpec("loan_amount", "Loan amount / debt amount", field_type="number"),
    FieldSpec("ltc_requested", "Loan-to-cost ratio requested", field_type="number", required=False),
    FieldSpec("gross_sellout", "Total gross sellout / gross sales revenue", field_type="number"),
    FieldSpec("net_sellout", "Net sellout after costs", field_type="number", required=False),
    FieldSpec("profit", "Developer profit / net profit", field_type="number", required=False),
    FieldSpec("profit_margin", "Profit margin on cost (%)", field_type="number", required=False),
    FieldSpec("per_unit_cost", "Cost per unit", field_type="number", required=False),
    FieldSpec("per_sf_cost", "Cost per square foot", field_type="number", required=False),
    FieldSpec("per_unit_sellout", "Sellout per unit", field_type="number", required=False),
    FieldSpec("per_sf_sellout", "Sellout per square foot", field_type="number", required=False),
    FieldSpec("unit_mix", "Unit mix with pricing (type, count, avg price, total)", field_type="list", required=False),
    FieldSpec("sources_and_uses", "Sources and uses of funds summary", field_type="object", required=False),
    FieldSpec("comparable_sales", "Comparable sales transactions referenced", field_type="list", required=False),
    FieldSpec("total_units", "Total number of units from pro forma", field_type="number", required=False),
]

# --- Appraisal ---
APPRAISAL_FIELDS = [
    FieldSpec("as_is_value", "As-is appraised value", field_type="number", required=False),
    FieldSpec("as_complete_value", "As-complete / prospective value", field_type="number", required=False),
    FieldSpec("as_stabilized_value", "As-stabilized value", field_type="number", required=False),
    FieldSpec("gross_sellout", "Total projected sellout from appraisal", field_type="number"),
    FieldSpec("net_sellout", "Net sellout after selling costs", field_type="number", required=False),
    FieldSpec("total_units", "Total unit count per appraisal", field_type="number"),
    FieldSpec("unit_mix", "Unit mix per appraisal", field_type="list", required=False),
    FieldSpec("total_gsf", "Gross square footage per appraisal", field_type="number", required=False),
    FieldSpec("net_sellable_sf", "Net sellable square footage", field_type="number", required=False),
    FieldSpec("market_conditions", "Appraiser's market conditions assessment", required=False),
    FieldSpec("absorption_rate", "Projected absorption rate", required=False),
    FieldSpec("discount_rate", "Discount rate used in DCF", field_type="number", required=False),
    FieldSpec("effective_date", "Appraisal effective date", required=False),
    FieldSpec("appraiser_name", "Appraiser or appraisal firm name", required=False),
    FieldSpec("comparable_sales", "Comparable sales used in valuation", field_type="list", required=False),
]

# --- Sponsor ---
SPONSOR_FIELDS = [
    FieldSpec("sponsor_name", "Primary sponsor / developer name"),
    FieldSpec("sponsor_entity", "Legal entity name", required=False),
    FieldSpec("principal_names", "Names of key principals", field_type="list", required=False),
    FieldSpec("years_experience", "Years of development experience", field_type="number", required=False),
    FieldSpec("completed_projects", "List of completed projects with details", field_type="list"),
    FieldSpec("current_projects", "List of current/in-progress projects", field_type="list", required=False),
    FieldSpec("total_units_developed", "Total units developed to date", field_type="number", required=False),
    FieldSpec("total_sf_developed", "Total SF developed to date", field_type="number", required=False),
    FieldSpec("total_development_value", "Total development value to date", field_type="number", required=False),
    FieldSpec("credentials", "Professional credentials, licenses, certifications", field_type="list", required=False),
    FieldSpec("notable_achievements", "Awards, recognitions, notable accomplishments", field_type="list", required=False),
]

# --- Zoning Approval ---
ZONING_FIELDS = [
    FieldSpec("zoning_district", "Zoning district (e.g., R7A, C4-4A)"),
    FieldSpec("special_district", "Special district overlay if any", required=False),
    FieldSpec("ulurp_numbers", "ULURP application numbers", field_type="list", required=False),
    FieldSpec("approval_date", "Date of zoning approval", required=False),
    FieldSpec("approved_units", "Number of units approved", field_type="number", required=False),
    FieldSpec("affordable_units", "Number of affordable units required/approved", field_type="number", required=False),
    FieldSpec("affordable_percentage", "Affordable housing percentage", field_type="number", required=False),
    FieldSpec("mih_option", "Mandatory Inclusionary Housing option selected", required=False),
    FieldSpec("approved_far", "Approved floor area ratio", field_type="number", required=False),
    FieldSpec("approved_height", "Approved building height", required=False),
    FieldSpec("conditions", "Conditions or restrictions on approval", field_type="list", required=False),
    FieldSpec("variance_granted", "Whether a variance was granted", required=False),
    FieldSpec("community_board", "Community board district", required=False),
    FieldSpec("environmental_review", "Environmental review status (EAS, EIS)", required=False),
]

# --- Legal Document (Title Report focus) ---
LEGAL_FIELDS = [
    FieldSpec("property_owner", "Current property owner / title holder"),
    FieldSpec("buyer_entity", "Buyer / acquiring entity name", required=False),
    FieldSpec("deed_type", "Type of deed", required=False),
    FieldSpec("deed_date", "Date of most recent deed", required=False),
    FieldSpec("purchase_price", "Purchase price from deed", field_type="number", required=False),
    FieldSpec("mortgages", "List of existing mortgages with amounts and lenders", field_type="list"),
    FieldSpec("liens", "List of liens and encumbrances", field_type="list", required=False),
    FieldSpec("lis_pendens", "Any lis pendens filings", field_type="list", required=False),
    FieldSpec("easements", "Easements and restrictions", field_type="list", required=False),
    FieldSpec("title_exceptions", "Schedule B exceptions", field_type="list", required=False),
    FieldSpec("title_policy_amount", "Title insurance policy amount", field_type="number", required=False),
    FieldSpec("title_company", "Title insurance company name", required=False),
    FieldSpec("survey_notes", "Key survey findings if included", required=False),
    FieldSpec("tax_lot_info", "Block/lot and tax information", required=False),
]


# Map document types to their field specs
FIELD_SPECS_BY_DOC_TYPE = {
    "project_summary_deck": PROJECT_SUMMARY_FIELDS,
    "pro_forma": PRO_FORMA_FIELDS,
    "appraisal": APPRAISAL_FIELDS,
    "sponsor_resume": SPONSOR_FIELDS,
    "zoning_approval": ZONING_FIELDS,
    "legal_document": LEGAL_FIELDS,
}


def get_field_specs(document_type: str) -> list[FieldSpec] | None:
    """Get field specifications for a document type. Returns None if no extraction defined."""
    return FIELD_SPECS_BY_DOC_TYPE.get(document_type)


def get_extractable_doc_types() -> list[str]:
    """Return document types that have extraction prompts."""
    return list(FIELD_SPECS_BY_DOC_TYPE.keys())
