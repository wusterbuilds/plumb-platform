"""Base class for structured data importers (CoStar, Argus, MarketProof)."""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ImportResult:
    records: list[dict]
    warnings: list[str]
    data_source: str
    data_type: str


class StructuredImporter(ABC):
    data_source: str
    data_type: str
    supported_mimetypes: list[str]

    @abstractmethod
    def detect(self, file_bytes: bytes, filename: str) -> bool:
        """Return True if this importer can handle the given file."""
        ...

    @abstractmethod
    def parse(self, file_bytes: bytes, filename: str) -> list[dict]:
        """Parse the file into a list of structured records."""
        ...

    @abstractmethod
    def validate(self, records: list[dict]) -> tuple[list[dict], list[str]]:
        """Validate records and return (valid_records, warnings)."""
        ...

    def run(self, file_bytes: bytes, filename: str) -> ImportResult:
        """Parse and validate a file end-to-end."""
        raw_records = self.parse(file_bytes, filename)
        valid_records, warnings = self.validate(raw_records)
        return ImportResult(
            records=valid_records,
            warnings=warnings,
            data_source=self.data_source,
            data_type=self.data_type,
        )
