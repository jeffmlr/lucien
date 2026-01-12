"""
Plain text file extractor.

Simple extractor for text-based files.
"""

from pathlib import Path

from . import TextExtractor, ExtractionResult


class PlainTextExtractor(TextExtractor):
    """Plain text file extractor."""

    TEXT_EXTENSIONS = {
        ".txt", ".md", ".markdown", ".rst", ".log",
        ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg",
        ".py", ".js", ".ts", ".html", ".css", ".xml",
        ".sh", ".bash", ".zsh", ".fish",
    }

    def can_extract(self, file_path: Path) -> bool:
        """Check if file is a text file."""
        return file_path.suffix.lower() in self.TEXT_EXTENSIONS

    def extract(self, file_path: Path) -> ExtractionResult:
        """Extract text by reading file."""
        try:
            # Try UTF-8 first
            with open(file_path, "r", encoding="utf-8") as f:
                text = f.read()
            return ExtractionResult(
                success=True,
                text=text,
                method="plaintext",
            )
        except UnicodeDecodeError:
            # Try latin-1 as fallback
            try:
                with open(file_path, "r", encoding="latin-1") as f:
                    text = f.read()
                return ExtractionResult(
                    success=True,
                    text=text,
                    method="plaintext",
                )
            except Exception as e:
                return ExtractionResult(
                    success=False,
                    error=f"Failed to read text file: {e}",
                    method="plaintext",
                )
        except Exception as e:
            return ExtractionResult(
                success=False,
                error=f"Failed to read file: {e}",
                method="plaintext",
            )
