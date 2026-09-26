"""CoStar market statistics importer."""

import csv
import io
import logging

from app.importers.base import StructuredImporter

logger = logging.getLogger(__name__)

MARKET_HEADERS = {
    "submarket", "vacancy", "vacancy rate", "asking rent",
    "effective rent", "absorption", "net absorption",
}

HEADER_MAP = {
    "submarket": "submarket",
    "submarket name": "submarket",
    "market": "market",
    "market name": "market",
    "vacancy": "vacancy_rate",
    "vacancy rate": "vacancy_rate",
    "vacancy rate %": "vacancy_rate",
    "asking rent": "asking_rent",
    "asking rent/sf": "asking_rent",
    "effective rent": "effective_rent",
    "effective rent/sf": "effective_rent",
    "absorption": "net_absorption",
    "net absorption": "net_absorption",
    "net absorption sf": "net_absorption",
    "under construction": "under_construction_sf",
    "under construction sf": "under_construction_sf",
    "deliveries": "deliveries_sf",
    "deliveries sf": "deliveries_sf",
    "inventory": "inventory_sf",
    "inventory sf": "inventory_sf",
    "cap rate": "cap_rate",
    "market cap rate": "cap_rate",
    "period": "period",
    "quarter": "period",
    "year": "year",
}


class CoStarMarketImporter(StructuredImporter):
    data_source = "costar"
    data_type = "market_stats"
    supported_mimetypes = [
        "text/csv",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ]

    def detect(self, file_bytes: bytes, filename: str) -> bool:
        fname = filename.lower()
        if "costar" not in fname or "comp" in fname:
            return False
        is_market = any(kw in fname for kw in ("market", "submarket", "stats", "analytics"))
        if not is_market:
            return False

        if fname.endswith(".csv"):
            try:
                text = file_bytes.decode("utf-8-sig", errors="replace")
                reader = csv.reader(io.StringIO(text))
                header_row = next(reader, None)
                if header_row:
                    lower_headers = {h.strip().lower() for h in header_row}
                    return len(lower_headers & MARKET_HEADERS) >= 2
            except Exception:
                return False

        return fname.endswith((".xlsx", ".xls"))

    def parse(self, file_bytes: bytes, filename: str) -> list[dict]:
        fname = filename.lower()
        if fname.endswith(".csv"):
            return self._parse_csv(file_bytes)
        elif fname.endswith((".xlsx", ".xls")):
            return self._parse_excel(file_bytes)
        return []

    def _parse_csv(self, file_bytes: bytes) -> list[dict]:
        text = file_bytes.decode("utf-8-sig", errors="replace")
        reader = csv.DictReader(io.StringIO(text))
        records = []
        for row in reader:
            mapped = {}
            for key, val in row.items():
                normalized = key.strip().lower()
                our_key = HEADER_MAP.get(normalized)
                if our_key and val and val.strip():
                    mapped[our_key] = val.strip()
            if mapped:
                records.append(mapped)
        return records

    def _parse_excel(self, file_bytes: bytes) -> list[dict]:
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(file_bytes), read_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
        wb.close()

        if not rows:
            return []

        headers = [str(h or "").strip().lower() for h in rows[0]]
        records = []
        for row in rows[1:]:
            mapped = {}
            for i, val in enumerate(row):
                if i < len(headers) and val is not None:
                    our_key = HEADER_MAP.get(headers[i])
                    if our_key:
                        mapped[our_key] = str(val).strip()
            if mapped:
                records.append(mapped)
        return records

    def validate(self, records: list[dict]) -> tuple[list[dict], list[str]]:
        valid = []
        warnings = []
        for i, rec in enumerate(records):
            vacancy = rec.get("vacancy_rate", "")
            if vacancy:
                try:
                    v = float(vacancy.replace("%", "").strip())
                    if v > 50:
                        warnings.append(f"Row {i+1}: vacancy rate {v}% unusually high")
                except ValueError:
                    pass
            valid.append(rec)
        return valid, warnings
