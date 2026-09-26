"""Excel parsing via openpyxl — extracts sheet data and formats for LLM consumption."""

from dataclasses import dataclass, field
from io import BytesIO
from typing import Any

import openpyxl


@dataclass
class ExcelContent:
    sheets: dict[str, list[list[Any]]] = field(default_factory=dict)
    sheet_names: list[str] = field(default_factory=list)


def extract_excel_content(file_bytes: bytes) -> ExcelContent:
    """Read all sheets from an Excel file into structured data."""
    wb = openpyxl.load_workbook(BytesIO(file_bytes), data_only=True, read_only=True)
    content = ExcelContent(sheet_names=wb.sheetnames)
    for name in wb.sheetnames:
        ws = wb[name]
        rows = []
        for row in ws.iter_rows(values_only=True):
            # Convert all values to strings, preserving None
            rows.append([_cell_to_str(cell) for cell in row])
        content.sheets[name] = rows
    wb.close()
    return content


def format_sheets_for_llm(content: ExcelContent) -> str:
    """Format Excel content as Markdown tables for LLM consumption."""
    parts = []
    for name in content.sheet_names:
        rows = content.sheets.get(name, [])
        if not rows:
            continue

        parts.append(f"## Sheet: {name}\n")

        # Find max columns across all rows
        max_cols = max((len(r) for r in rows), default=0)
        if max_cols == 0:
            continue

        # Skip fully empty rows at the top
        data_rows = _strip_empty_rows(rows)
        if not data_rows:
            continue

        # Build markdown table
        for i, row in enumerate(data_rows):
            padded = row + [""] * (max_cols - len(row))
            line = "| " + " | ".join(padded) + " |"
            parts.append(line)
            if i == 0:
                parts.append("| " + " | ".join(["---"] * max_cols) + " |")

        parts.append("")  # blank line between sheets

    return "\n".join(parts)


def _cell_to_str(value: Any) -> str:
    """Convert a cell value to a display string."""
    if value is None:
        return ""
    if isinstance(value, float):
        # Avoid ugly float repr for whole numbers
        if value == int(value):
            return str(int(value))
        return f"{value:,.2f}"
    return str(value)


def _strip_empty_rows(rows: list[list[str]]) -> list[list[str]]:
    """Remove leading and trailing rows that are entirely empty."""
    # Find first non-empty row
    start = 0
    for i, row in enumerate(rows):
        if any(cell.strip() for cell in row):
            start = i
            break
    else:
        return []

    # Find last non-empty row
    end = len(rows) - 1
    for i in range(len(rows) - 1, -1, -1):
        if any(cell.strip() for cell in rows[i]):
            end = i
            break

    return rows[start : end + 1]
