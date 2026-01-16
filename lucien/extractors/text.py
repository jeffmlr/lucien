"""
Plain text file extractor.

Simple extractor for text-based files.
"""

import chardet
from pathlib import Path

from . import BaseExtractor, ExtractionResult


class PlainTextExtractor(BaseExtractor):
    """Plain text file extractor with encoding detection."""

    TEXT_EXTENSIONS = {
        ".txt", ".md", ".markdown", ".rst", ".log",
        ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg",
        ".py", ".js", ".ts", ".html", ".css", ".xml",
        ".sh", ".bash", ".zsh", ".fish",
    }

    @property
    def name(self) -> str:
        """Return the name of this extractor."""
        return "text"

    def can_extract(self, file_path: Path) -> bool:
        """Check if file is a text file."""
        return file_path.suffix.lower() in self.TEXT_EXTENSIONS

    def _detect_encoding(self, file_path: Path) -> str:
        """Detect file encoding using chardet."""
        try:
            with open(file_path, "rb") as f:
                raw_data = f.read(10000)  # Read first 10KB
            result = chardet.detect(raw_data)
            return result.get("encoding", "utf-8") or "utf-8"
        except Exception:
            return "utf-8"

    def extract(self, file_path: Path) -> ExtractionResult:
        """Extract text by reading file with encoding detection."""
        try:
            # Try UTF-8 first (most common)
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    text = f.read()
                return ExtractionResult(
                    status="success",
                    text=text,
                    method=self.name,
                )
            except UnicodeDecodeError:
                # Use chardet for encoding detection
                encoding = self._detect_encoding(file_path)
                with open(file_path, "r", encoding=encoding, errors="replace") as f:
                    text = f.read()
                return ExtractionResult(
                    status="success",
                    text=text,
                    method=self.name,
                    metadata={"encoding": encoding}
                )
        except Exception as e:
            return ExtractionResult(
                status="failed",
                error=f"Failed to read file: {e}",
                method=self.name,
            )
