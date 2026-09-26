"""Auto-detect importer from file content and filename."""

from app.importers.argus_dcf import ArgusDCFImporter
from app.importers.base import StructuredImporter
from app.importers.costar_comps import CoStarCompImporter
from app.importers.costar_market import CoStarMarketImporter
from app.importers.marketproof import MarketProofImporter

import_registry: list[StructuredImporter] = [
    MarketProofImporter(),
    CoStarCompImporter(),
    CoStarMarketImporter(),
    ArgusDCFImporter(),
]


def detect_importer(file_bytes: bytes, filename: str) -> StructuredImporter | None:
    """Try each importer's detect() method, return the first match."""
    for imp in import_registry:
        try:
            if imp.detect(file_bytes, filename):
                return imp
        except Exception:
            continue
    return None
