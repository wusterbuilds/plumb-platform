"""Tests for structured data importers (CoStar, Argus, MarketProof)."""

import io

import pytest

from app.importers.costar_comps import CoStarCompImporter
from app.importers.costar_market import CoStarMarketImporter
from app.importers.argus_dcf import ArgusDCFImporter
from app.importers.marketproof import MarketProofImporter
from app.importers.registry import detect_importer


# ===========================================================================
# CoStar Comp Importer
# ===========================================================================


class TestCoStarCompDetect:
    def test_detect_csv_with_costar_name(self, costar_comp_csv_bytes):
        imp = CoStarCompImporter()
        assert imp.detect(costar_comp_csv_bytes, "costar_comps_export.csv") is True

    def test_detect_csv_with_comp_name(self, costar_comp_csv_bytes):
        imp = CoStarCompImporter()
        assert imp.detect(costar_comp_csv_bytes, "comp_report.csv") is True

    def test_reject_random_filename(self):
        imp = CoStarCompImporter()
        csv = b"Name,Age\nAlice,30\n"
        assert imp.detect(csv, "people.csv") is False

    def test_reject_market_file(self, costar_market_csv_bytes):
        imp = CoStarCompImporter()
        # "costar_market_stats.csv" doesn't have "comp" in the name
        # and the headers don't overlap enough with COSTAR_COMP_HEADERS
        assert imp.detect(costar_market_csv_bytes, "random_stats.csv") is False


class TestCoStarCompParse:
    def test_parse_csv_maps_headers(self, costar_comp_csv_bytes):
        imp = CoStarCompImporter()
        records = imp.parse(costar_comp_csv_bytes, "costar_comps.csv")
        assert len(records) == 3
        assert records[0]["property_name"] == "One Manhattan West"
        assert records[0]["address"] == "401 9th Ave"
        assert records[0]["price"] == "150000000"
        assert records[0]["cap_rate"] == "4.5%"
        assert records[0]["buyer"] == "Brookfield"

    def test_parse_skips_rows_without_identifier(self):
        csv = b"Sale Price,Cap Rate\n100000,5%\n"
        imp = CoStarCompImporter()
        records = imp.parse(csv, "costar_comp.csv")
        assert len(records) == 0


class TestCoStarCompValidate:
    def test_valid_records_pass(self, costar_comp_csv_bytes):
        imp = CoStarCompImporter()
        records = imp.parse(costar_comp_csv_bytes, "costar_comps.csv")
        valid, warnings = imp.validate(records)
        assert len(valid) == 3
        assert warnings == []

    def test_high_cap_rate_warning(self):
        imp = CoStarCompImporter()
        records = [{"address": "123 Main", "cap_rate": "25%"}]
        valid, warnings = imp.validate(records)
        assert len(valid) == 1
        assert any("cap rate" in w.lower() for w in warnings)

    def test_negative_price_excluded(self):
        imp = CoStarCompImporter()
        records = [{"address": "123 Main", "price": "-500000"}]
        valid, warnings = imp.validate(records)
        assert len(valid) == 0
        assert any("negative" in w.lower() for w in warnings)

    def test_missing_identifier_excluded(self):
        imp = CoStarCompImporter()
        records = [{"price": "100000"}]
        valid, warnings = imp.validate(records)
        assert len(valid) == 0
        assert any("missing" in w.lower() for w in warnings)


class TestCoStarCompEndToEnd:
    def test_run(self, costar_comp_csv_bytes):
        imp = CoStarCompImporter()
        result = imp.run(costar_comp_csv_bytes, "costar_comps.csv")
        assert result.data_source == "costar"
        assert result.data_type == "comps"
        assert len(result.records) == 3
        assert result.warnings == []


# ===========================================================================
# CoStar Market Importer
# ===========================================================================


class TestCoStarMarketDetect:
    def test_detect_market_stats(self, costar_market_csv_bytes):
        imp = CoStarMarketImporter()
        assert imp.detect(costar_market_csv_bytes, "costar_market_stats.csv") is True

    def test_reject_comp_file(self, costar_comp_csv_bytes):
        imp = CoStarMarketImporter()
        # "costar_comp" has "comp" in the name → rejected
        assert imp.detect(costar_comp_csv_bytes, "costar_comp_export.csv") is False

    def test_reject_non_costar(self, costar_market_csv_bytes):
        imp = CoStarMarketImporter()
        assert imp.detect(costar_market_csv_bytes, "market_stats.csv") is False


class TestCoStarMarketParse:
    def test_parse_csv_field_mapping(self, costar_market_csv_bytes):
        imp = CoStarMarketImporter()
        records = imp.parse(costar_market_csv_bytes, "costar_market_stats.csv")
        assert len(records) == 2
        assert records[0]["submarket"] == "Midtown West"
        assert records[0]["vacancy_rate"] == "8.2%"
        assert records[0]["asking_rent"] == "$85.50"
        assert records[0]["net_absorption"] == "150000"


class TestCoStarMarketValidate:
    def test_high_vacancy_warning(self):
        imp = CoStarMarketImporter()
        records = [{"submarket": "Test", "vacancy_rate": "55%"}]
        valid, warnings = imp.validate(records)
        assert len(valid) == 1
        assert any("vacancy" in w.lower() for w in warnings)


# ===========================================================================
# MarketProof Importer
# ===========================================================================


class TestMarketProofDetect:
    def test_detect_by_filename(self):
        imp = MarketProofImporter()
        # Filename alone is sufficient
        assert imp.detect(b"dummy", "marketproof_export.csv") is True

    def test_detect_by_headers(self, marketproof_csv_bytes):
        imp = MarketProofImporter()
        assert imp.detect(marketproof_csv_bytes, "new_dev_sales.csv") is True

    def test_reject_no_ppsf(self):
        imp = MarketProofImporter()
        csv = b"Building,Address,Price,Unit\nA,123 St,$1M,5A\n"
        assert imp.detect(csv, "sales_data.csv") is False


class TestMarketProofParse:
    def test_parse_csv(self, marketproof_csv_bytes):
        imp = MarketProofImporter()
        records = imp.parse(marketproof_csv_bytes, "marketproof_export.csv")
        assert len(records) == 3
        assert records[0]["building_name"] == "The Emerson"
        assert records[0]["price_per_sf"] == "$1850"
        assert records[0]["bedrooms"] == "2"
        assert records[0]["sqft"] == "1135"


class TestMarketProofValidate:
    def test_ppsf_too_high_warning(self):
        imp = MarketProofImporter()
        records = [{"address": "123 St", "price_per_sf": "$15000"}]
        valid, warnings = imp.validate(records)
        assert len(valid) == 1
        assert any("high" in w.lower() for w in warnings)

    def test_ppsf_too_low_warning(self):
        imp = MarketProofImporter()
        records = [{"address": "123 St", "price_per_sf": "$50"}]
        valid, warnings = imp.validate(records)
        assert len(valid) == 1
        assert any("low" in w.lower() for w in warnings)

    def test_negative_price_excluded(self):
        imp = MarketProofImporter()
        records = [{"address": "123 St", "price": "-100000"}]
        valid, warnings = imp.validate(records)
        assert len(valid) == 0


# ===========================================================================
# Argus DCF Importer
# ===========================================================================


class TestArgusDCFDetect:
    def test_detect_by_filename(self, argus_dcf_xlsx_bytes):
        imp = ArgusDCFImporter()
        assert imp.detect(argus_dcf_xlsx_bytes, "argus_dcf_model.xlsx") is True

    def test_detect_by_sheet_names(self, argus_dcf_xlsx_bytes):
        imp = ArgusDCFImporter()
        # Sheet is named "Cash Flow"
        assert imp.detect(argus_dcf_xlsx_bytes, "unknown_model.xlsx") is True

    def test_reject_csv(self):
        imp = ArgusDCFImporter()
        assert imp.detect(b"some,data", "argus_report.csv") is False


class TestArgusDCFParse:
    def test_extracts_noi(self, argus_dcf_xlsx_bytes):
        imp = ArgusDCFImporter()
        records = imp.parse(argus_dcf_xlsx_bytes, "argus_dcf.xlsx")
        assert len(records) == 1
        cf = records[0]
        assert "noi_schedule" in cf
        assert len(cf["noi_schedule"]) == 5

    def test_extracts_cap_rate_and_irr(self, argus_dcf_xlsx_bytes):
        imp = ArgusDCFImporter()
        records = imp.parse(argus_dcf_xlsx_bytes, "argus_dcf.xlsx")
        cf = records[0]
        # "Exit Cap Rate" row matches "exit" label → exit_assumptions
        assert cf.get("exit_assumptions") == ["5.5%"]
        assert cf.get("discount_rate") == "8.0%"
        assert cf.get("irr") == "12.5%"
        assert cf.get("npv") == "4500000"


class TestArgusDCFValidate:
    def test_empty_records_warning(self):
        imp = ArgusDCFImporter()
        valid, warnings = imp.validate([])
        assert any("no data" in w.lower() for w in warnings)


# ===========================================================================
# Importer Registry
# ===========================================================================


class TestImporterRegistry:
    def test_detect_costar_comp(self, costar_comp_csv_bytes):
        imp = detect_importer(costar_comp_csv_bytes, "costar_comp_export.csv")
        assert imp is not None
        assert isinstance(imp, CoStarCompImporter)

    def test_detect_marketproof(self, marketproof_csv_bytes):
        imp = detect_importer(marketproof_csv_bytes, "marketproof_sales.csv")
        assert imp is not None
        assert isinstance(imp, MarketProofImporter)

    def test_detect_argus(self, argus_dcf_xlsx_bytes):
        imp = detect_importer(argus_dcf_xlsx_bytes, "argus_dcf.xlsx")
        assert imp is not None
        assert isinstance(imp, ArgusDCFImporter)

    def test_detect_unknown(self):
        imp = detect_importer(b"random bytes", "mystery_file.txt")
        assert imp is None

    def test_marketproof_before_costar(self, marketproof_csv_bytes):
        """MarketProof is checked first in registry order."""
        imp = detect_importer(marketproof_csv_bytes, "marketproof_comp_data.csv")
        assert isinstance(imp, MarketProofImporter)
