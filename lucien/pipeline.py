"""
Extraction pipeline for orchestrating text extraction.

Manages extractor selection, fallback chains, text truncation,
and sidecar file management with compression.
"""

import gzip
from pathlib import Path
from typing import Generator, List, Optional

from .config import LucienSettings
from .db import Database
from .extractors import BaseExtractor, ExtractionResult, get_registry
from .extractors.docling import DoclingExtractor
from .extractors.pypdf import PyPDFExtractor
from .extractors.vision_ocr import VisionOCRExtractor
from .extractors.text import PlainTextExtractor


class ExtractionPipeline:
    """Pipeline for extracting text from files."""

    def __init__(self, config: LucienSettings, database: Database):
        """Initialize the extraction pipeline."""
        self.config = config
        self.database = database
        self._init_extractors()

    def _init_extractors(self) -> None:
        """Initialize and register extractors."""
        registry = get_registry()

        # Register extractors in priority order
        # Docling (primary) → PyPDF (fast fallback) → VisionOCR (scanned PDFs) → PlainText (text files)

        # Only register Docling if enabled (memory intensive: ~10GB per worker)
        if self.config.extraction.use_docling:
            registry.register(DoclingExtractor())

        registry.register(PyPDFExtractor())
        registry.register(VisionOCRExtractor())  # M-series Neural Engine OCR
        registry.register(PlainTextExtractor())

    def _should_skip_file(self, file_path: Path) -> bool:
        """Check if file should be skipped based on configuration."""
        extension = file_path.suffix.lower()
        return extension in self.config.extraction.skip_extensions

    def _truncate_text(self, text: str, max_length: int) -> str:
        """Truncate text to max_length, preserving beginning and end."""
        if len(text) <= max_length:
            return text

        # Keep first half and last half
        half = max_length // 2
        head = text[:half]
        tail = text[-half:]
        return f"{head}\n\n[... text truncated to {max_length} characters ...]\n\n{tail}"

    def _get_sidecar_path(self, sha256: str) -> Path:
        """Get the path for a sidecar file based on SHA256 hash."""
        return self.config.extracted_text_dir / f"{sha256}.txt.gz"

    def write_compressed_sidecar(self, text: str, sidecar_path: Path) -> None:
        """Write text to compressed sidecar file."""
        sidecar_path.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(sidecar_path, 'wt', encoding='utf-8') as f:
            f.write(text)

    def read_compressed_sidecar(self, sidecar_path: Path) -> str:
        """Read text from compressed sidecar file."""
        with gzip.open(sidecar_path, 'rt', encoding='utf-8') as f:
            return f.read()

    def extract_file(self, file_id: int, file_path: Path, sha256: str) -> ExtractionResult:
        """Extract text from a single file."""
        # Check if file should be skipped
        if self._should_skip_file(file_path):
            return ExtractionResult(
                status="skipped",
                method="none",
                error=f"Extension {file_path.suffix} in skip list",
            )

        # Get extractors that can handle this file
        registry = get_registry()
        extractors = registry.get_extractors_for_file(file_path)

        if not extractors:
            return ExtractionResult(
                status="skipped",
                method="none",
                error="No extractor available for this file type",
            )

        # Try each extractor in order (fallback chain)
        last_error = None
        for extractor in extractors:
            result = extractor.extract(file_path)

            if result.status == "success":
                # Truncate text if needed
                if result.text:
                    # Truncate before writing to reduce memory
                    truncated_text = self._truncate_text(
                        result.text,
                        self.config.extraction.max_text_length
                    )
                    
                    # Clear original text from memory
                    del result.text

                    # Write compressed sidecar
                    sidecar_path = self._get_sidecar_path(sha256)
                    self.write_compressed_sidecar(truncated_text, sidecar_path)
                    result.output_path = sidecar_path
                    
                    # Clear truncated text after writing
                    del truncated_text

                return result

            last_error = result.error

        # All extractors failed
        return ExtractionResult(
            status="failed",
            method="all",
            error=f"All extractors failed. Last error: {last_error}",
        )

    def get_files_for_extraction(self, force: bool = False, limit: Optional[int] = None) -> List[dict]:
        """Get files that need extraction."""
        return self.database.get_files_for_extraction(
            force=force,
            limit=limit,
            skip_extensions=self.config.extraction.skip_extensions
        )

    def count_files_for_extraction(self, force: bool = False) -> int:
        """Count files that need extraction."""
        return self.database.count_files_for_extraction(
            force=force,
            skip_extensions=self.config.extraction.skip_extensions
        )

    def iter_files_for_extraction(self, force: bool = False, limit: Optional[int] = None,
                                   batch_size: int = 100) -> Generator[List[dict], None, None]:
        """
        Iterate over files that need extraction in batches.

        Args:
            force: If True, include all files even if already extracted
            limit: Maximum total number of files to process
            batch_size: Number of files to process per batch

        Yields:
            Batches of file records as dictionaries
        """
        offset = 0
        processed = 0

        while True:
            # Determine batch size for this iteration
            if limit:
                remaining = limit - processed
                if remaining <= 0:
                    break
                current_batch_size = min(batch_size, remaining)
            else:
                current_batch_size = batch_size

            batch = self.database.get_files_for_extraction(
                force=force,
                offset=offset,
                batch_size=current_batch_size,
                skip_extensions=self.config.extraction.skip_extensions
            )

            if not batch:
                break

            yield batch

            processed += len(batch)
            offset += len(batch)

            if limit and processed >= limit:
                break