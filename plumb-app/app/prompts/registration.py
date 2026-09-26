"""Register all prompts with the global prompt registry.

Import this module on startup to populate the registry.
"""

from app.prompts.classify import ClassifyDocumentPrompt
from app.prompts.extract_appraisal import ExtractAppraisalPrompt
from app.prompts.extract_legal import ExtractLegalPrompt
from app.prompts.extract_pro_forma import ExtractProFormaPrompt
from app.prompts.extract_project_summary import ExtractProjectSummaryPrompt
from app.prompts.extract_sponsor import ExtractSponsorPrompt
from app.prompts.extract_zoning import ExtractZoningPrompt
from app.prompts.extract_comp_report import CompReportExtractionPrompt
from app.prompts.extract_market_research import MarketResearchExtractionPrompt
from app.prompts.extract_submarket_overview import SubmarketOverviewExtractionPrompt
from app.prompts.validate_assumptions import BorrowerAssumptionValidationPrompt
from app.prompts.interpret_acris import ACRISInterpretationPrompt
from app.prompts.interpret_ag_refb import AGREFBInterpretationPrompt
from app.prompts.interpret_dob import DOBInterpretationPrompt
from app.prompts.interpret_news import NewsRelevancePrompt
from app.om.narratives.investment_highlights import InvestmentHighlightsPrompt
from app.om.narratives.market_narrative import MarketNarrativePrompt
from app.om.narratives.sponsor_bio import SponsorBioPrompt
from app.om.narratives.transaction_overview import TransactionOverviewPrompt
from app.prompts.position_deal import PositionDealPrompt
from app.prompts.registry import prompt_registry

# Classification
prompt_registry.register(ClassifyDocumentPrompt())

# Extraction (Phase 1)
prompt_registry.register(ExtractProjectSummaryPrompt())
prompt_registry.register(ExtractProFormaPrompt())
prompt_registry.register(ExtractAppraisalPrompt())
prompt_registry.register(ExtractSponsorPrompt())
prompt_registry.register(ExtractZoningPrompt())
prompt_registry.register(ExtractLegalPrompt())

# Market research extraction (Phase 2)
prompt_registry.register(MarketResearchExtractionPrompt())
prompt_registry.register(CompReportExtractionPrompt())
prompt_registry.register(SubmarketOverviewExtractionPrompt())

# Market intelligence interpretation (Phase 2)
prompt_registry.register(ACRISInterpretationPrompt())
prompt_registry.register(DOBInterpretationPrompt())
prompt_registry.register(NewsRelevancePrompt())
prompt_registry.register(AGREFBInterpretationPrompt())

# Borrower assumption validation (Phase 2)
prompt_registry.register(BorrowerAssumptionValidationPrompt())

# OM narrative generation (Phase 3)
prompt_registry.register(TransactionOverviewPrompt())
prompt_registry.register(InvestmentHighlightsPrompt())
prompt_registry.register(MarketNarrativePrompt())
prompt_registry.register(SponsorBioPrompt())

# Deal positioning (Sprint 4 — Agent)
prompt_registry.register(PositionDealPrompt())
