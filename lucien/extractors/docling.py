"""
Docling-based text extractor (primary method).

Uses Docling library for high-quality PDF and document extraction
with table/structure preservation.
"""

import gc
import logging
import signal
import warnings
from pathlib import Path
from typing import Optional

from . import BaseExtractor, ExtractionResult

# Suppress noisy warnings from docling's dependencies
# - Semaphore leak warnings from multiprocessing (harmless cleanup noise)
# - Table structure errors that don't prevent text extraction
warnings.filterwarnings(
    "ignore",
    message="resource_tracker:.*semaphore.*",
    category=UserWarning,
)

# Suppress docling's internal logging for non-critical issues
# Table structure failures are logged but don't prevent text extraction
logging.getLogger("docling.pipeline").setLevel(logging.ERROR)
logging.getLogger("docling.models").setLevel(logging.ERROR)

try:
    from docling.document_converter import DocumentConverter
    DOCLING_AVAILABLE = True
except ImportError:
    DOCLING_AVAILABLE = False


class TimeoutException(Exception):
    """Raised when extraction times out."""
    pass


def timeout_handler(signum, frame):
    """Signal handler for timeout."""
    raise TimeoutException("Docling extraction timed out")


class DoclingExtractor(BaseExtractor):
    """Docling-based text extractor for PDFs and Office documents."""

    SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".pptx", ".xlsx"}

    # Maximum time (seconds) to spend on a single file before giving up
    # This prevents Docling from hanging indefinitely on problematic PDFs
    TIMEOUT_SECONDS = 90

    def __init__(self):
        """Initialize Docling extractor."""
        # Don't create converter here - create per file to avoid memory leaks
        pass

    @property
    def name(self) -> str:
        """Return the name of this extractor."""
        return "docling"

    def can_extract(self, file_path: Path) -> bool:
        """Check if file is supported by Docling."""
        if not DOCLING_AVAILABLE:
            return False
        return file_path.suffix.lower() in self.SUPPORTED_EXTENSIONS

    def extract(self, file_path: Path) -> ExtractionResult:
        """Extract text using Docling."""
        if not DOCLING_AVAILABLE:
            return ExtractionResult(
                status="failed",
                error="Docling not installed. Run: pip install lucien[extraction]",
                method=self.name,
            )

        # Set up timeout to prevent Docling from hanging indefinitely
        # Some PDFs (especially EPIC statements) cause Docling to hang forever
        old_handler = signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(self.TIMEOUT_SECONDS)

        # Create a new converter for each file to prevent memory leaks
        # Docling's DocumentConverter may accumulate state when reused
        converter = None
        try:
            converter = DocumentConverter()
        except TimeoutException:
            signal.alarm(0)  # Cancel alarm
            signal.signal(signal.SIGALRM, old_handler)  # Restore old handler
            return ExtractionResult(
                status="failed",
                error=f"Docling initialization timed out after {self.TIMEOUT_SECONDS}s",
                method=self.name,
            )
        except Exception as e:
            signal.alarm(0)  # Cancel alarm
            signal.signal(signal.SIGALRM, old_handler)  # Restore old handler
            return ExtractionResult(
                status="failed",
                error=f"Docling converter failed to initialize: {e}",
                method=self.name,
            )

        try:
            # Convert document using Docling
            result = converter.convert(str(file_path))

            # Extract text from conversion result
            text = None
            if hasattr(result, 'document') and hasattr(result.document, 'export_to_markdown'):
                # Export to markdown to preserve structure
                text = result.document.export_to_markdown()
            elif hasattr(result, 'document') and hasattr(result.document, 'export_to_text'):
                text = result.document.export_to_text()
            elif hasattr(result, 'text'):
                text = result.text
            else:
                # Clear result before returning
                del result
                return ExtractionResult(
                    status="failed",
                    error="Docling result format not recognized",
                    method=self.name,
                )

            # Extract metadata if available (before clearing result)
            metadata = {}
            if hasattr(result, 'document') and hasattr(result.document, 'metadata'):
                doc_metadata = result.document.metadata
                if hasattr(doc_metadata, 'title') and doc_metadata.title:
                    metadata["title"] = str(doc_metadata.title)
                if hasattr(doc_metadata, 'author') and doc_metadata.author:
                    metadata["author"] = str(doc_metadata.author)

            # Explicitly clear result object to free memory
            del result
            # Clear converter to free any cached state
            del converter

            # Force garbage collection to prevent memory accumulation
            gc.collect()

            # Clear torch cache to free GPU/MPS memory
            try:
                import torch
                if hasattr(torch, 'mps') and torch.backends.mps.is_available():
                    torch.mps.empty_cache()
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except (ImportError, AttributeError):
                pass

            # Cancel timeout alarm - extraction succeeded
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)

            if not text or not text.strip():
                return ExtractionResult(
                    status="failed",
                    error="No text extracted from document",
                    method=self.name,
                )

            return ExtractionResult(
                status="success",
                text=text,
                method=self.name,
                metadata=metadata,
            )

        except TimeoutException:
            # Timeout - Docling hung on this file
            # Clear converter and alarm
            if converter is not None:
                del converter
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)
            gc.collect()
            try:
                import torch
                if hasattr(torch, 'mps') and torch.backends.mps.is_available():
                    torch.mps.empty_cache()
            except (ImportError, AttributeError):
                pass

            return ExtractionResult(
                status="failed",
                error=f"Docling timed out after {self.TIMEOUT_SECONDS}s (file may be too complex or Docling may have hung)",
                method=self.name,
            )

        except Exception as e:
            # Clear converter even on error
            if converter is not None:
                del converter
            # Cancel alarm
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)
            # Force cleanup even on error
            gc.collect()
            try:
                import torch
                if hasattr(torch, 'mps') and torch.backends.mps.is_available():
                    torch.mps.empty_cache()
            except (ImportError, AttributeError):
                pass

            return ExtractionResult(
                status="failed",
                error=f"Docling extraction failed: {e}",
                method=self.name,
            )
