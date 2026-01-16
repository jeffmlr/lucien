"""
Text extraction modules (Phase 1).

Provides interfaces and implementations for extracting text
from various document formats.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Type


@dataclass
class ExtractionResult:
    """Result of text extraction operation."""
    status: str  # 'success', 'failed', 'skipped'
    method: str  # 'docling', 'pypdf', 'text', etc.
    text: Optional[str] = None
    output_path: Optional[Path] = None
    error: Optional[str] = None
    metadata: Dict[str, str] = field(default_factory=dict)

    @property
    def success(self) -> bool:
        """Compatibility property for success status."""
        return self.status == "success"


class BaseExtractor(ABC):
    """Abstract base class for text extractors."""

    @abstractmethod
    def can_extract(self, file_path: Path) -> bool:
        """Check if this extractor can handle the file."""
        pass

    @abstractmethod
    def extract(self, file_path: Path) -> ExtractionResult:
        """Extract text from file."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the name of this extractor."""
        pass


class ExtractorRegistry:
    """Registry for managing multiple extractors."""

    def __init__(self):
        self._extractors: List[BaseExtractor] = []

    def register(self, extractor: BaseExtractor) -> None:
        """Register an extractor."""
        self._extractors.append(extractor)

    def get_extractors_for_file(self, file_path: Path) -> List[BaseExtractor]:
        """Get all extractors that can handle the file."""
        return [ext for ext in self._extractors if ext.can_extract(file_path)]

    def get_all_extractors(self) -> List[BaseExtractor]:
        """Get all registered extractors."""
        return self._extractors.copy()


# Global registry instance
_registry = ExtractorRegistry()


def get_registry() -> ExtractorRegistry:
    """Get the global extractor registry."""
    return _registry


__all__ = ["BaseExtractor", "ExtractionResult", "ExtractorRegistry", "get_registry"]
