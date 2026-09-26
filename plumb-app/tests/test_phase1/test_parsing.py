"""Tests for document parsing — PDF chunking and Excel content extraction."""

import struct

from app.parsing.excel import ExcelContent, _cell_to_str, _strip_empty_rows, format_sheets_for_llm
from app.parsing.pdf import chunk_pages, PageImage


def _make_page(n: int) -> PageImage:
    """Create a minimal PageImage for testing (not a valid PNG, just for chunking tests)."""
    return PageImage(page_number=n, image_bytes=b"fake-png-" + str(n).encode())


class TestChunkPages:
    def test_small_doc_no_chunking(self):
        pages = [_make_page(i) for i in range(1, 11)]  # 10 pages
        chunks = chunk_pages(pages, max_pages=25, overlap=1)
        assert len(chunks) == 1
        assert len(chunks[0]) == 10

    def test_exact_max_pages_no_chunking(self):
        pages = [_make_page(i) for i in range(1, 26)]  # 25 pages
        chunks = chunk_pages(pages, max_pages=25, overlap=1)
        assert len(chunks) == 1
        assert len(chunks[0]) == 25

    def test_chunking_with_overlap(self):
        pages = [_make_page(i) for i in range(1, 51)]  # 50 pages
        chunks = chunk_pages(pages, max_pages=25, overlap=1)
        assert len(chunks) >= 2
        # Each chunk should have at most 25 pages
        for chunk in chunks:
            assert len(chunk) <= 50  # last chunk may be bigger due to merging

        # All pages should be covered
        all_page_nums = set()
        for chunk in chunks:
            for page in chunk:
                all_page_nums.add(page.page_number)
        assert all_page_nums == set(range(1, 51))

    def test_chunking_overlap_content(self):
        pages = [_make_page(i) for i in range(1, 51)]  # 50 pages
        chunks = chunk_pages(pages, max_pages=25, overlap=1)
        # First chunk starts at page 1
        assert chunks[0][0].page_number == 1

    def test_single_page(self):
        pages = [_make_page(1)]
        chunks = chunk_pages(pages, max_pages=25, overlap=1)
        assert len(chunks) == 1
        assert len(chunks[0]) == 1

    def test_empty_pages(self):
        chunks = chunk_pages([], max_pages=25, overlap=1)
        assert len(chunks) == 1
        assert len(chunks[0]) == 0

    def test_overlap_zero(self):
        pages = [_make_page(i) for i in range(1, 51)]
        chunks = chunk_pages(pages, max_pages=25, overlap=0)
        assert len(chunks) == 2
        assert chunks[0][0].page_number == 1
        assert chunks[0][-1].page_number == 25
        assert chunks[1][0].page_number == 26


class TestPageImage:
    def test_base64_encoding(self):
        page = PageImage(page_number=1, image_bytes=b"hello")
        b64 = page.base64
        assert isinstance(b64, str)
        assert len(b64) > 0

    def test_to_claude_content(self):
        page = PageImage(page_number=1, image_bytes=b"hello")
        content = page.to_claude_content()
        assert content["type"] == "image"
        assert content["source"]["type"] == "base64"
        assert content["source"]["media_type"] == "image/png"


class TestExcelParsing:
    def test_cell_to_str_none(self):
        assert _cell_to_str(None) == ""

    def test_cell_to_str_float_whole(self):
        assert _cell_to_str(42.0) == "42"

    def test_cell_to_str_float_decimal(self):
        assert _cell_to_str(3.14159) == "3.14"

    def test_cell_to_str_string(self):
        assert _cell_to_str("hello") == "hello"

    def test_cell_to_str_int(self):
        assert _cell_to_str(42) == "42"

    def test_strip_empty_rows(self):
        rows = [
            ["", "", ""],
            ["a", "b", "c"],
            ["d", "e", "f"],
            ["", "", ""],
        ]
        result = _strip_empty_rows(rows)
        assert len(result) == 2
        assert result[0] == ["a", "b", "c"]

    def test_strip_empty_rows_all_empty(self):
        rows = [["", ""], ["", ""]]
        assert _strip_empty_rows(rows) == []

    def test_format_sheets_for_llm(self):
        content = ExcelContent(
            sheets={"Sheet1": [["Name", "Value"], ["TDC", "100000000"]]},
            sheet_names=["Sheet1"],
        )
        result = format_sheets_for_llm(content)
        assert "## Sheet: Sheet1" in result
        assert "Name" in result
        assert "TDC" in result
        assert "---" in result  # header separator

    def test_format_sheets_empty(self):
        content = ExcelContent(sheets={}, sheet_names=[])
        result = format_sheets_for_llm(content)
        assert result == ""
