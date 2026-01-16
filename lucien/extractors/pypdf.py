"""
PyPDF extractor for PDF files.

Lightweight fallback extractor for simple PDFs.
"""

from pathlib import Path

from . import BaseExtractor, ExtractionResult

try:
    from pypdf import PdfReader
    PYPDF_AVAILABLE = True
except ImportError:
    PYPDF_AVAILABLE = False


class PyPDFExtractor(BaseExtractor):
    """PDF text extractor using pypdf library."""

    @property
    def name(self) -> str:
        """Return the name of this extractor."""
        return "pypdf"

    def can_extract(self, file_path: Path) -> bool:
        """Check if file is a PDF."""
        if not PYPDF_AVAILABLE:
            return False
        return file_path.suffix.lower() == ".pdf"

    def extract(self, file_path: Path) -> ExtractionResult:
        """Extract text from PDF using pypdf."""
        if not PYPDF_AVAILABLE:
            return ExtractionResult(
                status="failed",
                error="pypdf not installed. Run: pip install lucien[extraction]",
                method=self.name,
            )

        try:
            reader = PdfReader(str(file_path))

            # Check if PDF is encrypted
            if reader.is_encrypted:
                del reader
                return ExtractionResult(
                    status="failed",
                    error="PDF is encrypted/password-protected",
                    method=self.name,
                )

            # Extract text from all pages incrementally
            text_parts = []
            for page in reader.pages:
                try:
                    page_text = page.extract_text()
                    if page_text and page_text.strip():
                        text_parts.append(page_text)
                    # Clear page_text reference immediately
                    del page_text
                except Exception:
                    # Continue with other pages if one fails
                    continue

            # Extract metadata before clearing reader
            metadata = {}
            if reader.metadata:
                if reader.metadata.title:
                    metadata["title"] = str(reader.metadata.title)
                if reader.metadata.author:
                    metadata["author"] = str(reader.metadata.author)
                if reader.metadata.creation_date:
                    metadata["creation_date"] = str(reader.metadata.creation_date)

            # Explicitly clear reader to free PDF structure from memory
            del reader

            # Join text parts after reader is cleared
            text = "\n\n".join(text_parts)
            # Clear text_parts list
            del text_parts

            if not text.strip():
                return ExtractionResult(
                    status="failed",
                    error="No text extracted (possibly scanned PDF without OCR)",
                    method=self.name,
                )

            return ExtractionResult(
                status="success",
                text=text,
                method=self.name,
                metadata=metadata,
            )

        except Exception as e:
            return ExtractionResult(
                status="failed",
                error=f"PyPDF extraction failed: {e}",
                method=self.name,
            )
