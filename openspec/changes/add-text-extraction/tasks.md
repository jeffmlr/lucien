# Implementation Tasks

## 1. Core Extraction Infrastructure
- [ ] 1.1 Create `BaseExtractor` abstract base class in `lucien/extractors/__init__.py`
- [ ] 1.2 Define `ExtractionResult` dataclass for standardized results
- [ ] 1.3 Implement extractor registry for managing multiple backends
- [ ] 1.4 Add configuration for extraction settings (skip_extensions, methods order, max_text_length)

## 2. Plain Text Extractor
- [ ] 2.1 Implement `TextExtractor` class in `lucien/extractors/text.py`
- [ ] 2.2 Handle UTF-8, UTF-16, and common text encodings with fallback
- [ ] 2.3 Support .txt, .md, .rst, .log, and other text file extensions
- [ ] 2.4 Add character encoding detection
- [ ] 2.5 Write unit tests for text extractor with various encodings

## 3. PyPDF Extractor
- [ ] 3.1 Implement `PyPDFExtractor` class in `lucien/extractors/pypdf.py`
- [ ] 3.2 Extract text from PDF using pypdf library
- [ ] 3.3 Handle encrypted PDFs gracefully (skip with error message)
- [ ] 3.4 Handle corrupted/malformed PDFs with proper error handling
- [ ] 3.5 Add metadata extraction (title, author, creation date) if available
- [ ] 3.6 Write unit tests with sample PDF fixtures

## 4. Docling Extractor
- [ ] 4.1 Implement `DoclingExtractor` class in `lucien/extractors/docling.py`
- [ ] 4.2 Integrate Docling library for PDFs and Office documents
- [ ] 4.3 Extract structured content (tables, lists, headings)
- [ ] 4.4 Handle Docling errors gracefully (timeout, unsupported formats)
- [ ] 4.5 Configure Docling options (OCR disabled initially, can be added later)
- [ ] 4.6 Add support for .docx, .xlsx, .pptx formats via Docling
- [ ] 4.7 Write integration tests with sample documents

## 5. Extraction Pipeline
- [ ] 5.1 Create `ExtractionPipeline` class to orchestrate extractors
- [ ] 5.2 Implement fallback chain: Docling → PyPDF → Text (based on file type)
- [ ] 5.3 Add file type detection using MIME types and extensions
- [ ] 5.4 Skip files in configured skip_extensions list
- [ ] 5.5 Implement hash-based sidecar filename generation (SHA256-based)
- [ ] 5.6 Write extracted text to `~/.lucien/extracted_text/` with gzip compression (.txt.gz)
- [ ] 5.7 Implement transparent decompression when reading sidecars
- [ ] 5.8 Record extraction results in database (status, method, output_path, error)
- [ ] 5.9 Add idempotency: skip files with successful extractions
- [ ] 5.10 Add helper functions for compressed sidecar I/O (write_compressed, read_compressed)

## 6. CLI Command Implementation
- [ ] 6.1 Implement `extract` command in `lucien/cli.py`
- [ ] 6.2 Add `--force` flag to re-extract already processed files
- [ ] 6.3 Add `--method` flag to override extraction method selection
- [ ] 6.4 Add `--limit` flag to process only N files (for testing)
- [ ] 6.5 Add progress bar showing extraction progress (using rich)
- [ ] 6.6 Display statistics: successful, failed, skipped counts
- [ ] 6.7 Add verbose logging mode for debugging extraction issues

## 7. Database Operations
- [ ] 7.1 Verify `extractions` table schema is correct in `lucien/db.py`
- [ ] 7.2 Add `Database.record_extraction()` method
- [ ] 7.3 Add `Database.get_files_for_extraction()` query (exclude already extracted)
- [ ] 7.4 Add `Database.get_extraction_stats()` method
- [ ] 7.5 Add extraction_run_id tracking for versioning

## 8. Configuration Updates
- [ ] 8.1 Verify extraction settings in `lucien/config.py` (ExtractionSettings)
- [ ] 8.2 Add extraction examples to `lucien.example.yaml`
- [ ] 8.3 Document extraction configuration options

## 9. Dependencies
- [ ] 9.1 Add extraction optional dependencies to `pyproject.toml` (already exists)
- [ ] 9.2 Add graceful fallback when optional dependencies missing
- [ ] 9.3 Add installation instructions for extraction dependencies

## 10. Testing
- [ ] 10.1 Create test fixtures: sample PDFs, text files, Office docs
- [ ] 10.2 Write unit tests for each extractor
- [ ] 10.3 Write integration tests for extraction pipeline
- [ ] 10.4 Test fallback behavior when primary extractor fails
- [ ] 10.5 Test CLI command with various options
- [ ] 10.6 Test idempotency (re-running extraction skips completed files)
- [ ] 10.7 Test error handling for corrupted/encrypted files

## 11. Documentation
- [ ] 11.1 Update README.md with extraction command examples
- [ ] 11.2 Update QUICKSTART.md with extraction workflow
- [ ] 11.3 Add extraction troubleshooting section
- [ ] 11.4 Document supported file formats and extractors
- [ ] 11.5 Add example extraction configuration

## 12. Error Handling & Edge Cases
- [ ] 12.1 Handle files larger than max_text_length (truncate gracefully)
- [ ] 12.2 Handle permission errors reading files
- [ ] 12.3 Handle disk space issues writing sidecars
- [ ] 12.4 Add timeout handling for slow extractions
- [ ] 12.5 Handle non-text binary files gracefully (skip with appropriate message)

## 13. Milestone Completion
- [ ] 13.1 Verify all tasks above are completed
- [ ] 13.2 Run full test suite and ensure all tests pass
- [ ] 13.3 Test end-to-end: scan → extract workflow
- [ ] 13.4 Update milestone status to v0.2 in documentation
