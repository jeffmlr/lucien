"""
Apple Vision OCR extractor for scanned PDFs.

Uses Apple's Vision framework with Neural Engine acceleration
on M-series Macs for high-quality, fast OCR.
"""

from pathlib import Path
from typing import List

from . import BaseExtractor, ExtractionResult

try:
    import Quartz
    from Vision import (
        VNRecognizeTextRequest,
        VNImageRequestHandler,
    )
    from Foundation import NSURL
    VISION_AVAILABLE = True
except ImportError:
    VISION_AVAILABLE = False


class VisionOCRExtractor(BaseExtractor):
    """
    OCR extractor using Apple Vision framework.
    
    Optimized for M-series Macs with Neural Engine acceleration.
    """

    @property
    def name(self) -> str:
        """Return the name of this extractor."""
        return "vision-ocr"

    def can_extract(self, file_path: Path) -> bool:
        """Check if Vision framework is available and file is a PDF."""
        if not VISION_AVAILABLE:
            return False
        return file_path.suffix.lower() == ".pdf"

    def _extract_text_from_pdf_page(self, page: Quartz.CGPDFPageRef) -> str:
        """Extract text from a single PDF page using Vision OCR."""
        try:
            # Get page bounds
            page_rect = Quartz.CGPDFPageGetBoxRect(page, Quartz.kCGPDFMediaBox)
            
            # Create bitmap context
            width = int(page_rect.size.width)
            height = int(page_rect.size.height)
            
            # Scale up for better OCR (2x resolution)
            scale = 2.0
            width = int(width * scale)
            height = int(height * scale)
            
            color_space = Quartz.CGColorSpaceCreateDeviceRGB()
            context = Quartz.CGBitmapContextCreate(
                None,
                width,
                height,
                8,  # bits per component
                0,  # bytes per row (auto)
                color_space,
                Quartz.kCGImageAlphaPremultipliedLast
            )
            
            if context is None:
                return ""
            
            # Draw PDF page to bitmap
            Quartz.CGContextScaleCTM(context, scale, scale)
            Quartz.CGContextDrawPDFPage(context, page)
            
            # Get image from context
            cg_image = Quartz.CGBitmapContextCreateImage(context)
            if cg_image is None:
                return ""
            
            # Create Vision request handler
            request_handler = VNImageRequestHandler.alloc().initWithCGImage_options_(
                cg_image, None
            )
            
            # Create text recognition request
            request = VNRecognizeTextRequest.alloc().init()
            request.setRecognitionLevel_(1)  # Accurate (vs Fast = 0)
            request.setUsesLanguageCorrection_(True)
            
            # Perform OCR
            success = request_handler.performRequests_error_([request], None)[0]
            
            if not success:
                return ""
            
            # Extract recognized text
            observations = request.results()
            if not observations:
                return ""
            
            text_lines = []
            for observation in observations:
                # Get top candidate
                candidates = observation.topCandidates_(1)
                if candidates and len(candidates) > 0:
                    text_lines.append(candidates[0].string())
            
            return "\n".join(text_lines)
            
        except Exception as e:
            # Return empty string on error, page will be skipped
            return ""

    def extract(self, file_path: Path) -> ExtractionResult:
        """Extract text from PDF using Vision OCR."""
        if not VISION_AVAILABLE:
            return ExtractionResult(
                status="failed",
                error="Vision framework not available (macOS only)",
                method=self.name,
            )

        try:
            # Open PDF
            pdf_url = NSURL.fileURLWithPath_(str(file_path))
            pdf_doc = Quartz.CGPDFDocumentCreateWithURL(pdf_url)
            
            if pdf_doc is None:
                return ExtractionResult(
                    status="failed",
                    error="Could not open PDF",
                    method=self.name,
                )
            
            # Get number of pages
            num_pages = Quartz.CGPDFDocumentGetNumberOfPages(pdf_doc)
            
            if num_pages == 0:
                return ExtractionResult(
                    status="failed",
                    error="PDF has no pages",
                    method=self.name,
                )
            
            # Extract text from each page (limit to reasonable number)
            max_pages = min(num_pages, 50)  # Limit for performance
            text_parts = []
            
            for page_num in range(1, max_pages + 1):
                page = Quartz.CGPDFDocumentGetPage(pdf_doc, page_num)
                if page is not None:
                    page_text = self._extract_text_from_pdf_page(page)
                    if page_text.strip():
                        text_parts.append(f"--- Page {page_num} ---\n{page_text}")
                    # Note: CGPDFPage is not retained, so no explicit release needed

            if not text_parts:
                return ExtractionResult(
                    status="failed",
                    error="No text recognized in PDF (blank or non-text image)",
                    method=self.name,
                )
            
            text = "\n\n".join(text_parts)
            
            metadata = {
                "pages_processed": str(max_pages),
                "total_pages": str(num_pages),
            }
            
            if num_pages > max_pages:
                metadata["note"] = f"Limited to first {max_pages} pages"
            
            return ExtractionResult(
                status="success",
                text=text,
                method=self.name,
                metadata=metadata,
            )

        except Exception as e:
            return ExtractionResult(
                status="failed",
                error=f"Vision OCR failed: {e}",
                method=self.name,
            )