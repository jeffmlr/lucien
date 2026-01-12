"""
PyPDF-based text extractor (fallback for simple PDFs).

TODO: Implement in Milestone 2 (v0.2)
"""

from pathlib import Path

from . import TextExtractor, ExtractionResult


class PyPDFExtractor(TextExtractor):
    """PyPDF-based text extractor."""

    def can_extract(self, file_path: Path) -> bool:
        """Check if file is a PDF."""
        return file_path.suffix.lower() == ".pdf"

    def extract(self, file_path: Path) -> ExtractionResult:
        """Extract text using PyPDF."""
        # TODO: Implement actual PyPDF extraction
        return ExtractionResult(
            success=False,
            error="PyPDF extraction not yet implemented (Milestone 2)",
            method="pypdf",
        )
