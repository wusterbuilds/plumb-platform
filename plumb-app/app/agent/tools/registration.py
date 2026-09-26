"""Register all agent tools on import. Import this module at app startup."""

from app.agent.tools.registry import tool_registry

# Extraction tools
from app.agent.tools.extraction_tools import (
    ClassifyDocumentTool,
    ExtractFromExcelTool,
    ExtractFromPDFTool,
    RunCrossReferencesTool,
)

# Market tools
from app.agent.tools.market_tools import (
    FetchACRISTool,
    FetchDOBTool,
    FetchNewsTool,
    FetchZolaTool,
    GeocodeAddressTool,
    InterpretACRISTool,
    InterpretDOBTool,
    InterpretNewsTool,
)

# Financial tools
from app.agent.tools.financial_tools import (
    GenerateExcelTool,
    GetFinancialModelTool,
    UpdateAssumptionsTool,
)

# Memory tools
from app.agent.tools.memory_tools import (
    MatchLendersTool,
    QueryDeveloperTool,
    QueryEpisodesTool,
    QueryLenderTool,
    StoreEpisodeTool,
)

# OM tools
from app.agent.tools.om_tools import (
    GenerateSectionTool,
    PositionDealTool,
    RenderOMPDFTool,
    ReviewOMDraftTool,
)

# Risk Report tools
from app.agent.tools.risk_tools import (
    CompileRiskFindingsTool,
    GenerateRiskNarrativeTool,
    RenderRiskPDFTool,
)


def register_all_tools() -> None:
    """Instantiate and register every tool with the global registry."""
    tools = [
        # Extraction
        ClassifyDocumentTool(),
        ExtractFromPDFTool(),
        ExtractFromExcelTool(),
        RunCrossReferencesTool(),
        # Market
        GeocodeAddressTool(),
        FetchACRISTool(),
        FetchDOBTool(),
        FetchZolaTool(),
        FetchNewsTool(),
        InterpretACRISTool(),
        InterpretDOBTool(),
        InterpretNewsTool(),
        # Financial
        GetFinancialModelTool(),
        UpdateAssumptionsTool(),
        GenerateExcelTool(),
        # Memory
        QueryDeveloperTool(),
        QueryLenderTool(),
        MatchLendersTool(),
        QueryEpisodesTool(),
        StoreEpisodeTool(),
        # OM
        PositionDealTool(),
        GenerateSectionTool(),
        RenderOMPDFTool(),
        ReviewOMDraftTool(),
        # Risk Report
        CompileRiskFindingsTool(),
        GenerateRiskNarrativeTool(),
        RenderRiskPDFTool(),
    ]

    for tool in tools:
        tool_registry.register(tool)


# Auto-register on import
register_all_tools()
