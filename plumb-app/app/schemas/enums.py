from enum import Enum


# --- Deal classification ---


class DealType(str, Enum):
    CONSTRUCTION_LOAN = "construction_loan"
    STABILIZED_DEBT = "stabilized_debt"
    VALUE_ADD = "value_add"
    EQUITY_PLACEMENT = "equity_placement"


class DealSubtype(str, Enum):
    GROUND_UP_RESIDENTIAL = "ground_up_residential"
    GROUND_UP_COMMERCIAL = "ground_up_commercial"
    MULTIFAMILY_RENTAL = "multifamily_rental"
    CONDO_SELLOUT = "condo_sellout"
    MIXED_USE = "mixed_use"
    OFFICE = "office"
    INDUSTRIAL = "industrial"
    RETAIL = "retail"


class CapitalAsk(str, Enum):
    DEBT = "debt"
    EQUITY = "equity"
    MEZZ = "mezz"
    PREFERRED_EQUITY = "preferred_equity"


class PropertyType(str, Enum):
    MULTIFAMILY_RENTAL = "multifamily_rental"
    CONDO_SELLOUT = "condo_sellout"
    OFFICE = "office"
    INDUSTRIAL = "industrial"
    RETAIL = "retail"
    MIXED_USE = "mixed_use"


# --- Pipeline states ---


class DealStatus(str, Enum):
    # Forward flow
    DOCS_RECEIVED = "docs_received"
    CLASSIFYING = "classifying"
    EXTRACTING = "extracting"
    EXTRACTION_REVIEW = "extraction_review"
    MARKET_ENRICHMENT = "market_enrichment"
    MODEL_BUILDING = "model_building"
    OM_DRAFTING = "om_drafting"
    OM_REVIEW = "om_review"
    REWORKING = "reworking"
    LENDER_OUTREACH = "lender_outreach"
    TRACKING = "tracking"
    TERM_SHEET_RECEIVED = "term_sheet_received"
    CLOSED = "closed"

    # Special
    ON_HOLD = "on_hold"
    DEAD = "dead"

    # Error
    EXTRACTION_FAILED = "extraction_failed"
    MODEL_ERROR = "model_error"


# --- Documents ---


class DocumentType(str, Enum):
    # Deal documents
    PROJECT_SUMMARY_DECK = "project_summary_deck"
    PRO_FORMA = "pro_forma"
    RENT_ROLL = "rent_roll"
    OPERATING_STATEMENT_T12 = "operating_statement_t12"
    APPRAISAL = "appraisal"
    ENVIRONMENTAL_REPORT = "environmental_report"
    PROPERTY_CONDITION_REPORT = "property_condition_report"
    ZONING_APPROVAL = "zoning_approval"
    PERMIT = "permit"
    SPONSOR_RESUME = "sponsor_resume"
    LEGAL_DOCUMENT = "legal_document"

    # Market intelligence documents
    MARKET_RESEARCH_REPORT = "market_research_report"
    COMP_REPORT = "comp_report"
    SUBMARKET_OVERVIEW = "submarket_overview"
    COSTAR_EXPORT = "costar_export"
    ARGUS_DCF = "argus_dcf"

    OTHER = "other"


class DocumentStatus(str, Enum):
    UPLOADED = "uploaded"
    PARSING = "parsing"
    PARSED = "parsed"
    EXTRACTING = "extracting"
    EXTRACTED = "extracted"
    FAILED = "failed"
    SUPERSEDED = "superseded"


# --- Extraction ---


class ExtractionMethod(str, Enum):
    DOCLING = "docling"
    CLAUDE_VISION = "claude_vision"
    OPENPYXL = "openpyxl"
    MANUAL = "manual"


class FlagColor(str, Enum):
    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"


class ConfidenceSourceType(str, Enum):
    TABLE_CELL = "table_cell"
    LIST_ITEM = "list_item"
    PARAGRAPH = "paragraph"
    FOOTNOTE = "footnote"
    INFERRED = "inferred"


class LabelMatch(str, Enum):
    EXACT = "exact"
    SYNONYM = "synonym"
    CONTEXTUAL = "contextual"


class CrossRefResult(str, Enum):
    MATCH = "match"
    MISMATCH = "mismatch"
    WITHIN_TOLERANCE = "within_tolerance"
    UNABLE_TO_CHECK = "unable_to_check"


class CrossRefResolution(str, Enum):
    FIELD_A_CORRECT = "field_a_correct"
    FIELD_B_CORRECT = "field_b_correct"
    BOTH_WRONG = "both_wrong"


# --- Events ---


class EventType(str, Enum):
    # Document lifecycle
    DOC_UPLOADED = "doc_uploaded"
    DOC_CLASSIFIED = "doc_classified"
    DOC_PARSED = "doc_parsed"
    DOC_SUPERSEDED = "doc_superseded"

    # Extraction
    EXTRACTION_STARTED = "extraction_started"
    EXTRACTION_COMPLETED = "extraction_completed"
    EXTRACTION_FAILED = "extraction_failed"

    # Review
    FIELD_REVIEWED = "field_reviewed"
    FIELD_OVERRIDDEN = "field_overridden"
    CROSS_REF_RESOLVED = "cross_ref_resolved"
    CHECKPOINT_RELEASED = "checkpoint_released"

    # Model
    MODEL_CALCULATED = "model_calculated"
    MODEL_FAILED = "model_failed"

    # Market
    PUBLIC_DATA_FETCHED = "public_data_fetched"
    MARKET_DATA_IMPORTED = "market_data_imported"

    # OM
    OM_GENERATED = "om_generated"
    OM_APPROVED = "om_approved"

    # Lender
    LENDER_CONTACTED = "lender_contacted"
    RESPONSE_RECEIVED = "response_received"
    TERM_SHEET_RECEIVED = "term_sheet_received"

    # LLM
    LLM_CALL = "llm_call"

    # Deal lifecycle
    DEAL_CREATED = "deal_created"
    DEAL_UPDATED = "deal_updated"
    STATE_TRANSITION = "state_transition"
    BACKWARD_TRANSITION = "backward_transition"
    REVISION_STARTED = "revision_started"
    DEAL_ON_HOLD = "deal_on_hold"
    DEAL_RESUMED = "deal_resumed"
    DEAL_KILLED = "deal_killed"


class DeadReason(str, Enum):
    BORROWER_UNRESPONSIVE = "borrower_unresponsive"
    NUMBERS_DONT_WORK = "numbers_dont_work"
    LENDER_PASSED_ALL = "lender_passed_all"
    DUPLICATE = "duplicate"
    OUT_OF_SCOPE = "out_of_scope"
    OTHER = "other"


# --- Auth ---


class UserRole(str, Enum):
    ADMIN = "admin"
    ANALYST = "analyst"
    BROKER = "broker"
