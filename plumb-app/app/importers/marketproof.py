"""MarketProof new development condo data importer."""

import csv
import io
import logging

from app.importers.base import StructuredImporter

logger = logging.getLogger(__name__)

MP_HEADERS = {
    "building", "building name", "address", "unit", "price",
    "price per sf", "ppsf", "closing date", "bedrooms", "sqft",
}

HEADER_MAP = {
    "building": "building_name",
    "building name": "building_name",
    "project": "building_name",
    "address": "address",
    "property address": "address",
    "unit": "unit",
    "unit number": "unit",
    "apt": "unit",
    "price": "price",
    "sale price": "price",
    "closed price": "price",
    "last price": "price",
    "price per sf": "price_per_sf",
    "ppsf": "price_per_sf",
    "$/sf": "price_per_sf",
    "price/sf": "price_per_sf",
    "closing date": "closing_date",
    "close date": "closing_date",
    "sale date": "closing_date",
    "date": "closing_date",
    "floor": "floor",
    "bedrooms": "bedrooms",
    "beds": "bedrooms",
    "br": "bedrooms",
    "sqft": "sqft",
    "sq ft": "sqft",
    "square feet": "sqft",
    "interior sf": "sqft",
    "bathrooms": "bathrooms",
    "baths": "bathrooms",
    "status": "status",
}


class MarketProofImporter(StructuredImporter):
    data_source = "marketproof"
    data_type = "comps"
    supported_mimetypes = [
        "text/csv",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ]

    def detect(self, file_bytes: bytes, filename: str) -> bool:
        fname = filename.lower()
        if "marketproof" in fname or "market_proof" in fname or "market-proof" in fname:
            return True

        if fname.endswith(".csv"):
            try:
                text = file_bytes.decode("utf-8-sig", errors="replace")
                reader = csv.reader(io.StringIO(text))
                header_row = next(reader, None)
                if header_row:
                    lower_headers = {h.strip().lower() for h in header_row}
                    has_mp = len(lower_headers & MP_HEADERS) >= 4
                    has_ppsf = "ppsf" in lower_headers or "price per sf" in lower_headers
                    return has_mp and has_ppsf
            except Exception:
                return False

        return False

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
            if mapped.get("address") or mapped.get("building_name"):
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
            if mapped.get("address") or mapped.get("building_name"):
                records.append(mapped)
        return records

    def validate(self, records: list[dict]) -> tuple[list[dict], list[str]]:
        valid = []
        warnings = []
        for i, rec in enumerate(records):
            ppsf = rec.get("price_per_sf", "")
            if ppsf:
                try:
                    ppsf_val = float(ppsf.replace("$", "").replace(",", "").strip())
                    if ppsf_val > 10000:
                        warnings.append(f"Row {i+1}: price/SF ${ppsf_val} unusually high")
                    elif ppsf_val < 100:
                        warnings.append(f"Row {i+1}: price/SF ${ppsf_val} unusually low")
                except ValueError:
                    pass

            price = rec.get("price", "")
            if price:
                try:
                    p = float(price.replace("$", "").replace(",", "").strip())
                    if p < 0:
                        warnings.append(f"Row {i+1}: negative price ${p}")
                        continue
                except ValueError:
                    pass

            valid.append(rec)
        return valid, warnings
