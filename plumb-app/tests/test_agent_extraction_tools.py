"""Tests that extraction agent tools pass correct task_data keys to LLM prompts.

Regression tests for the bug where ExtractFromPDFTool passed 'content_blocks'
instead of 'page_images', and ExtractFromExcelTool passed 'excel_content'
instead of 'sheet_text' — causing all extractions to return <UNKNOWN>.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agent.tools.base import ToolContext, ToolResult
from app.agent.tools.extraction_tools import ExtractFromExcelTool, ExtractFromPDFTool


@pytest.fixture
def deal_id():
    return uuid.uuid4()


@pytest.fixture
def doc_id():
    return uuid.uuid4()


@pytest.fixture
def mock_doc(doc_id):
    doc = MagicMock()
    doc.id = doc_id
    doc.filename = "test.pdf"
    doc.document_type = "appraisal"
    doc.mime_type = "application/pdf"
    doc.page_count = None
    return doc


@pytest.fixture
def mock_db(mock_doc):
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = mock_doc
    db.execute = AsyncMock(return_value=result)
    db.flush = AsyncMock()
    return db


@pytest.fixture
def mock_llm_client():
    client = AsyncMock()
    client.execute = AsyncMock(return_value={
        "fields": {
            "as_is_value": {
                "value": "$12,500,000",
                "source_page": 3,
                "source_text": "As-Is Value: $12,500,000",
                "confidence_basis": "explicit_label",
                "source_type": "heading",
                "label_match": "exact",
            }
        }
    })
    return client


@pytest.fixture
def ctx(mock_db, deal_id, mock_llm_client):
    return ToolContext(db=mock_db, deal_id=deal_id, llm_client=mock_llm_client)


class TestExtractFromPDFTaskDataKeys:
    """Verify ExtractFromPDFTool passes 'page_images' key (not 'content_blocks')."""

    @pytest.mark.asyncio
    async def test_pdf_tool_passes_page_images_key(self, ctx, doc_id):
        fake_page = MagicMock()
        fake_page.page_number = 1
        fake_page.to_claude_content.return_value = {
            "type": "image",
            "source": {"type": "base64", "media_type": "image/png", "data": "abc"},
        }

        with (
            patch(
                "app.storage.s3.download_document",
                return_value=b"fake-pdf",
            ),
            patch(
                "app.parsing.pdf.pdf_to_page_images",
                return_value=[fake_page],
            ),
            patch(
                "app.parsing.pdf.chunk_pages",
                return_value=[[fake_page]],
            ),
            patch(
                "app.extraction.handlers.get_prompt_name",
                return_value="extract_appraisal",
            ),
        ):
            tool = ExtractFromPDFTool()
            result = await tool.execute(
                _ctx=ctx, document_id=str(doc_id), document_type="appraisal"
            )

        assert result.success
        assert result.data["fields_extracted"] == 1

        # THE CRITICAL CHECK: verify 'page_images' key was used
        call_args = ctx.llm_client.execute.call_args
        task_data = call_args.args[2] if len(call_args.args) > 2 else call_args.kwargs.get("task_data")
        assert "page_images" in task_data, (
            f"Expected 'page_images' key in task_data, got keys: {list(task_data.keys())}. "
            "This is the bug that caused all extractions to return <UNKNOWN>."
        )
        assert "content_blocks" not in task_data, (
            "'content_blocks' should not be in task_data — prompts expect 'page_images'"
        )
        assert len(task_data["page_images"]) == 1


class TestExtractFromExcelTaskDataKeys:
    """Verify ExtractFromExcelTool passes 'sheet_text' key (not 'excel_content')."""

    @pytest.mark.asyncio
    async def test_excel_tool_passes_sheet_text_key(self, ctx, doc_id, mock_doc):
        mock_doc.filename = "pro_forma.xlsx"
        mock_doc.document_type = "pro_forma"

        mock_excel_content = MagicMock()
        mock_excel_content.sheet_names = ["Summary", "Detail"]

        with (
            patch(
                "app.storage.s3.download_document",
                return_value=b"fake-xlsx",
            ),
            patch(
                "app.parsing.excel.extract_excel_content",
                return_value=mock_excel_content,
            ),
            patch(
                "app.parsing.excel.format_sheets_for_llm",
                return_value="| Col A | Col B |\n|---|---|\n| 1 | 2 |",
            ),
            patch(
                "app.extraction.handlers.get_prompt_name",
                return_value="extract_pro_forma",
            ),
        ):
            tool = ExtractFromExcelTool()
            result = await tool.execute(_ctx=ctx, document_id=str(doc_id))

        assert result.success
        assert result.data["fields_extracted"] == 1

        # THE CRITICAL CHECK: verify 'sheet_text' key was used
        call_args = ctx.llm_client.execute.call_args
        task_data = call_args.args[2] if len(call_args.args) > 2 else call_args.kwargs.get("task_data")
        assert "sheet_text" in task_data, (
            f"Expected 'sheet_text' key in task_data, got keys: {list(task_data.keys())}. "
            "This is the bug that caused Excel extractions to return <UNKNOWN>."
        )
        assert "excel_content" not in task_data, (
            "'excel_content' should not be in task_data — prompts expect 'sheet_text'"
        )
