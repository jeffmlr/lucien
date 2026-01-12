"""
Text extraction modules (Phase 1).

Provides interfaces and implementations for extracting text
from various document formats.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional


class ExtractionResult:
    """Result of text extraction operation."""

    def __init__(
        self,
        success: bool,
        text: Optional[str] = None,
        method: str = "unknown",
        error: Optional[str] = None,
    ):
        self.success = success
        self.text = text
        self.method = method
        self.error = error


class TextExtractor(ABC):
    """Abstract base class for text extractors."""

    @abstractmethod
    def can_extract(self, file_path: Path) -> bool:
        """Check if this extractor can handle the file."""
        pass

    @abstractmethod
    def extract(self, file_path: Path) -> ExtractionResult:
        """Extract text from file."""
        pass


__all__ = ["TextExtractor", "ExtractionResult"]
