"""Tests for Phase 2 prompt registration and output schema validation."""

import app.prompts.registration  # noqa: F401 — triggers registration
from app.prompts.registry import prompt_registry


class TestPhase2PromptRegistration:
    def test_all_phase2_prompts_registered(self):
        prompts = prompt_registry.list_all()
        phase2_prompts = [
            "extract_market_research",
            "extract_comp_report",
            "extract_submarket_overview",
            "interpret_acris",
            "interpret_dob",
            "interpret_news",
            "interpret_ag_refb",
            "validate_assumptions",
        ]
        for name in phase2_prompts:
            assert name in prompts, f"Phase 2 prompt '{name}' not registered"
            assert prompts[name] == "1.0.0", f"Prompt '{name}' version != 1.0.0"


class TestInterpretACRISSchema:
    def test_output_schema_keys(self):
        from app.prompts.interpret_acris import ACRISInterpretationPrompt

        prompt = ACRISInterpretationPrompt()
        schema = prompt.output_schema
        props = schema["properties"]
        assert "current_owner" in props
        assert "purchase_price" in props
        assert "existing_mortgages" in props
        assert "ownership_chain" in props
        assert "flags" in props
        assert "summary" in props

    def test_validate_good_output(self):
        from app.prompts.interpret_acris import ACRISInterpretationPrompt

        prompt = ACRISInterpretationPrompt()
        is_valid, errors = prompt.validate_output({
            "summary": "Property owned by Test LLC since 2020",
            "current_owner": "Test LLC",
        })
        assert is_valid
        assert errors == []

    def test_validate_missing_summary(self):
        from app.prompts.interpret_acris import ACRISInterpretationPrompt

        prompt = ACRISInterpretationPrompt()
        is_valid, errors = prompt.validate_output({"current_owner": "Test"})
        assert not is_valid


class TestInterpretDOBSchema:
    def test_output_schema_keys(self):
        from app.prompts.interpret_dob import DOBInterpretationPrompt

        prompt = DOBInterpretationPrompt()
        schema = prompt.output_schema
        props = schema["properties"]
        assert "active_permits" in props
        assert "open_violations" in props
        assert "material_flags" in props
        assert "summary" in props


class TestInterpretNewsSchema:
    def test_output_schema_keys(self):
        from app.prompts.interpret_news import NewsRelevancePrompt

        prompt = NewsRelevancePrompt()
        schema = prompt.output_schema
        props = schema["properties"]
        assert "articles" in props
        assert "summary" in props


class TestInterpretAGREFBSchema:
    def test_output_schema_keys(self):
        from app.prompts.interpret_ag_refb import AGREFBInterpretationPrompt

        prompt = AGREFBInterpretationPrompt()
        schema = prompt.output_schema
        props = schema["properties"]
        assert "offering_plans" in props
        assert "material_flags" in props
        assert "summary" in props


class TestExtractMarketResearchSchema:
    def test_output_schema_keys(self):
        from app.prompts.extract_market_research import MarketResearchExtractionPrompt

        prompt = MarketResearchExtractionPrompt()
        schema = prompt.output_schema
        assert "properties" in schema or "fields" in schema.get("properties", {})


class TestExtractCompReportSchema:
    def test_output_schema_keys(self):
        from app.prompts.extract_comp_report import CompReportExtractionPrompt

        prompt = CompReportExtractionPrompt()
        schema = prompt.output_schema
        assert "properties" in schema


class TestExtractSubmarketOverviewSchema:
    def test_output_schema_keys(self):
        from app.prompts.extract_submarket_overview import SubmarketOverviewExtractionPrompt

        prompt = SubmarketOverviewExtractionPrompt()
        schema = prompt.output_schema
        assert "properties" in schema


class TestValidateAssumptionsSchema:
    def test_output_schema_keys(self):
        from app.prompts.validate_assumptions import BorrowerAssumptionValidationPrompt

        prompt = BorrowerAssumptionValidationPrompt()
        schema = prompt.output_schema
        props = schema["properties"]
        assert "validation_flags" in props
        assert "overall_assessment" in props
        assert "summary" in props

    def test_severity_enum(self):
        from app.prompts.validate_assumptions import BorrowerAssumptionValidationPrompt

        prompt = BorrowerAssumptionValidationPrompt()
        flag_schema = prompt.output_schema["properties"]["validation_flags"]["items"]
        severity = flag_schema["properties"]["severity"]
        assert severity["enum"] == ["info", "warning", "critical"]

    def test_assessment_enum(self):
        from app.prompts.validate_assumptions import BorrowerAssumptionValidationPrompt

        prompt = BorrowerAssumptionValidationPrompt()
        assessment = prompt.output_schema["properties"]["overall_assessment"]
        assert "consistent" in assessment["enum"]
        assert "significant_red_flags" in assessment["enum"]

    def test_validate_good_output(self):
        from app.prompts.validate_assumptions import BorrowerAssumptionValidationPrompt

        prompt = BorrowerAssumptionValidationPrompt()
        is_valid, errors = prompt.validate_output({
            "validation_flags": [],
            "overall_assessment": "consistent",
            "summary": "No significant discrepancies found.",
        })
        assert is_valid
        assert errors == []

    def test_validate_missing_fields(self):
        from app.prompts.validate_assumptions import BorrowerAssumptionValidationPrompt

        prompt = BorrowerAssumptionValidationPrompt()
        is_valid, errors = prompt.validate_output({})
        assert not is_valid
        assert len(errors) == 3
