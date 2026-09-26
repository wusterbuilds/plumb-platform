"""OM narrative prompts — register all prompts with the global registry."""

from app.om.narratives.investment_highlights import InvestmentHighlightsPrompt
from app.om.narratives.market_narrative import MarketNarrativePrompt
from app.om.narratives.sponsor_bio import SponsorBioPrompt
from app.om.narratives.transaction_overview import TransactionOverviewPrompt
from app.prompts.registry import prompt_registry

prompt_registry.register(TransactionOverviewPrompt())
prompt_registry.register(InvestmentHighlightsPrompt())
prompt_registry.register(MarketNarrativePrompt())
prompt_registry.register(SponsorBioPrompt())
