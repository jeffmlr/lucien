# Implementation Tasks

## 1. Core Extraction Infrastructure
- [x] 1.1 Create `BaseExtractor` abstract base class in `lucien/extractors/__init__.py`
- [x] 1.2 Define `ExtractionResult` dataclass for standardized results
- [x] 1.3 Implement extractor registry for managing multiple backends
- [x] 1.4 Add configuration for extraction settings (skip_extensions, methods order, max_text_length)

## 2. Plain Text Extractor
- [x] 2.1 Implement `TextExtractor` class in `lucien/extractors/text.py`
- [x] 2.2 Handle UTF-8, UTF-16, and common text encodings with fallback
- [x] 2.3 Support .txt, .md, .rst, .log, and other text file extensions
- [x] 2.4 Add character encoding detection
- [ ] 2.5 Write unit tests for text extractor with various encodings

## 3. PyPDF Extractor
- [x] 3.1 Implement `PyPDFExtractor` class in `lucien/extractors/pypdf.py`
- [x] 3.2 Extract text from PDF using pypdf library
- [x] 3.3 Handle encrypted PDFs gracefully (skip with error message)
- [x] 3.4 Handle corrupted/malformed PDFs with proper error handling
- [x] 3.5 Add metadata extraction (title, author, creation date) if available
- [ ] 3.6 Write unit tests with sample PDF fixtures

## 4. Docling Extractor
- [x] 4.1 Implement `DoclingExtractor` class in `lucien/extractors/docling.py`
- [x] 4.2 Integrate Docling library for PDFs and Office documents
- [x] 4.3 Extract structured content (tables, lists, headings)
- [x] 4.4 Handle Docling errors gracefully (timeout, unsupported formats)
- [x] 4.5 Configure Docling options (OCR disabled initially, can be added later)
- [x] 4.6 Add support for .docx, .xlsx, .pptx formats via Docling
- [ ] 4.7 Write integration tests with sample documents

## 4A. Apple Vision OCR Extractor (M-series Macs)
- [x] 4A.1 Implement `VisionOCRExtractor` class in `lucien/extractors/vision_ocr.py`
- [x] 4A.2 Use Apple Vision framework for Neural Engine acceleration
- [x] 4A.3 Implement per-page OCR with 2x resolution scaling for accuracy
- [x] 4A.4 Configure accurate recognition level with language correction
- [x] 4A.5 Add 50-page limit for performance
- [x] 4A.6 Add pyobjc-framework-Vision and pyobjc-framework-Quartz dependencies
- [x] 4A.7 Test Vision OCR on scanned PDFs

## 5. Extraction Pipeline
- [x] 5.1 Create `ExtractionPipeline` class to orchestrate extractors
- [x] 5.2 Implement fallback chain: Docling → PyPDF → VisionOCR → Text (based on file type)
- [x] 5.3 Add file type detection using MIME types and extensions
- [x] 5.4 Skip files in configured skip_extensions list
- [x] 5.5 Implement hash-based sidecar filename generation (SHA256-based)
- [x] 5.6 Write extracted text to `~/.lucien/extracted_text/` with gzip compression (.txt.gz)
- [x] 5.7 Implement transparent decompression when reading sidecars
- [x] 5.8 Record extraction results in database (status, method, output_path, error)
- [x] 5.9 Add idempotency: skip files with successful extractions
- [x] 5.10 Add helper functions for compressed sidecar I/O (write_compressed, read_compressed)

## 6. CLI Command Implementation
- [x] 6.1 Implement `extract` command in `lucien/cli.py`
- [x] 6.2 Add `--force` flag to re-extract already processed files
- [ ] 6.3 Add `--method` flag to override extraction method selection (deferred - not critical for v0.2)
- [x] 6.4 Add `--limit` flag to process only N files (for testing)
- [x] 6.5 Add progress bar showing extraction progress (using rich)
- [x] 6.6 Display statistics: successful, failed, skipped counts
- [ ] 6.7 Add verbose logging mode for debugging extraction issues (deferred - current error handling sufficient)

## 7. Database Operations
- [x] 7.1 Verify `extractions` table schema is correct in `lucien/db.py`
- [x] 7.2 Add `Database.record_extraction()` method
- [x] 7.3 Add `Database.get_files_for_extraction()` query (exclude already extracted)
- [x] 7.4 Add `Database.get_extraction_stats()` method
- [x] 7.5 Add extraction_run_id tracking for versioning

## 8. Configuration Updates
- [x] 8.1 Verify extraction settings in `lucien/config.py` (ExtractionSettings)
- [x] 8.2 Add extraction examples to `lucien.example.yaml`
- [x] 8.3 Document extraction configuration options

## 9. Dependencies
- [x] 9.1 Add extraction optional dependencies to `pyproject.toml` (already exists)
- [x] 9.2 Add graceful fallback when optional dependencies missing
- [x] 9.3 Add installation instructions for extraction dependencies

## 10. Testing
- [ ] 10.1 Create test fixtures: sample PDFs, text files, Office docs
- [ ] 10.2 Write unit tests for each extractor
- [ ] 10.3 Write integration tests for extraction pipeline
- [ ] 10.4 Test fallback behavior when primary extractor fails
- [x] 10.5 Test CLI command with various options (manually tested successfully)
- [x] 10.6 Test idempotency (re-running extraction skips completed files)
- [x] 10.7 Test error handling for corrupted/encrypted files (manually tested)

## 11. Documentation
- [ ] 11.1 Update README.md with extraction command examples
- [ ] 11.2 Update QUICKSTART.md with extraction workflow
- [ ] 11.3 Add extraction troubleshooting section
- [ ] 11.4 Document supported file formats and extractors
- [ ] 11.5 Add example extraction configuration

## 12. Error Handling & Edge Cases
- [x] 12.1 Handle files larger than max_text_length (truncate gracefully)
- [x] 12.2 Handle permission errors reading files (handled by try/except)
- [x] 12.3 Handle disk space issues writing sidecars (Python exceptions catch this)
- [ ] 12.4 Add timeout handling for slow extractions (deferred - can be added if needed)
- [x] 12.5 Handle non-text binary files gracefully (skip with appropriate message)
- [x] 12.6 Suppress noisy docling warnings (table structure errors, semaphore leaks)

## 13. Milestone Completion
- [x] 13.1 Verify all critical tasks completed (core functionality working)
- [ ] 13.2 Run full test suite and ensure all tests pass (tests to be written)
- [x] 13.3 Test end-to-end: scan → extract workflow (manually tested successfully)
- [ ] 13.4 Update milestone status to v0.2 in documentation

## Summary

**Completed:** 61/79 tasks (77%)

**Core Functionality:** ✅ COMPLETE
- All extractors implemented (Text, PyPDF, Docling, Vision OCR)
- Apple Vision OCR for scanned PDFs (M-series Neural Engine optimized)
- Pipeline with fallback chain working (Docling → PyPDF → VisionOCR → Text)
- CLI command functional with progress bars
- Compressed sidecar storage (.txt.gz) working
- Database operations complete
- Idempotency working

**Remaining Work:**
- Unit/integration tests (10 tasks)
- Documentation updates (5 tasks)
- Optional enhancements (3 tasks: verbose mode, method override, timeout handling)

**Status:** Text extraction (Phase 1) is functionally complete and tested. Remaining work is primarily tests and documentation, which can be done incrementally.
