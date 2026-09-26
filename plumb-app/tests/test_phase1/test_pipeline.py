"""Tests for pipeline orchestration logic — mocked LLM and DB.

These test the pipeline coordination logic without hitting external services.
"""

import uuid
from unittest.mock import MagicMock, patch

from app.extraction.handlers import get_prompt_name, is_extractable


class TestHandlers:
    def test_get_prompt_name_known_types(self):
        assert get_prompt_name("project_summary_deck") == "extract_project_summary"
        assert get_prompt_name("pro_forma") == "extract_pro_forma"
        assert get_prompt_name("appraisal") == "extract_appraisal"
        assert get_prompt_name("sponsor_resume") == "extract_sponsor"
        assert get_prompt_name("zoning_approval") == "extract_zoning"
        assert get_prompt_name("legal_document") == "extract_legal"

    def test_get_prompt_name_unknown(self):
        assert get_prompt_name("other") is None
        assert get_prompt_name("environmental_report") is None

    def test_is_extractable(self):
        assert is_extractable("project_summary_deck") is True
        assert is_extractable("pro_forma") is True
        assert is_extractable("other") is False
        assert is_extractable("rent_roll") is False


class TestFieldSpecs:
    def test_all_extractable_types_have_specs(self):
        from app.extraction.field_specs import get_extractable_doc_types, get_field_specs

        for doc_type in get_extractable_doc_types():
            specs = get_field_specs(doc_type)
            assert specs is not None, f"No field specs for {doc_type}"
            assert len(specs) > 0, f"Empty field specs for {doc_type}"

    def test_field_spec_structure(self):
        from app.extraction.field_specs import get_field_specs

        specs = get_field_specs("project_summary_deck")
        for spec in specs:
            assert spec.name, "Field spec must have a name"
            assert spec.description, "Field spec must have a description"
            assert spec.field_type in ("string", "number", "list", "object")


class TestPromptRegistration:
    def test_all_prompts_registered(self):
        # Import triggers registration
        import app.prompts.registration  # noqa: F401
        from app.prompts.registry import prompt_registry

        prompts = prompt_registry.list_all()
        expected = [
            "classify_document",
            "extract_project_summary",
            "extract_pro_forma",
            "extract_appraisal",
            "extract_sponsor",
            "extract_zoning",
            "extract_legal",
        ]
        for name in expected:
            assert name in prompts, f"Prompt '{name}' not registered"
            assert prompts[name] == "1.0.0"


class TestPromptValidation:
    def test_classify_validates_good_output(self):
        from app.prompts.classify import ClassifyDocumentPrompt

        prompt = ClassifyDocumentPrompt()
        is_valid, errors = prompt.validate_output({
            "document_type": "pro_forma",
            "confidence": 0.95,
            "reasoning": "Contains financial projections",
        })
        assert is_valid
        assert errors == []

    def test_classify_rejects_bad_type(self):
        from app.prompts.classify import ClassifyDocumentPrompt

        prompt = ClassifyDocumentPrompt()
        is_valid, errors = prompt.validate_output({
            "document_type": "invalid_type",
            "confidence": 0.95,
            "reasoning": "test",
        })
        assert not is_valid

    def test_classify_rejects_bad_confidence(self):
        from app.prompts.classify import ClassifyDocumentPrompt

        prompt = ClassifyDocumentPrompt()
        is_valid, _ = prompt.validate_output({
            "document_type": "pro_forma",
            "confidence": 1.5,
            "reasoning": "test",
        })
        assert not is_valid

    def test_extraction_validates_good_output(self):
        from app.prompts.extract_project_summary import ExtractProjectSummaryPrompt

        prompt = ExtractProjectSummaryPrompt()
        is_valid, errors = prompt.validate_output({
            "fields": {
                "total_units": {
                    "value": "415",
                    "source_page": 3,
                    "source_text_snippet": "Total Units: 415",
                    "source_type": "list_item",
                    "label_match": "exact",
                }
            }
        })
        assert is_valid

    def test_extraction_rejects_missing_fields(self):
        from app.prompts.extract_project_summary import ExtractProjectSummaryPrompt

        prompt = ExtractProjectSummaryPrompt()
        is_valid, _ = prompt.validate_output({})
        assert not is_valid
