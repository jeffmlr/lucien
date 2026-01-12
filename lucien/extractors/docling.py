"""
Docling-based text extractor (primary method).

Uses Docling library for high-quality PDF and document extraction.

TODO: Implement in Milestone 2 (v0.2)
"""

from pathlib import Path

from . import TextExtractor, ExtractionResult


class DoclingExtractor(TextExtractor):
    """Docling-based text extractor."""

    def can_extract(self, file_path: Path) -> bool:
        """Check if file is supported by Docling."""
        # TODO: Implement actual check based on Docling capabilities
        suffix = file_path.suffix.lower()
        return suffix in [".pdf", ".docx", ".doc", ".pptx", ".xlsx"]

    def extract(self, file_path: Path) -> ExtractionResult:
        """Extract text using Docling."""
        # TODO: Implement actual Docling extraction
        return ExtractionResult(
            success=False,
            error="Docling extraction not yet implemented (Milestone 2)",
            method="docling",
        )
