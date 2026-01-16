# Change: Add Text Extraction (Phase 1)

## Why
Phase 0 (scanning/indexing) is complete. Phase 1 (text extraction) is required to extract text from PDFs, Office documents, and other files to prepare for AI labeling in Phase 2. Text extraction is the foundation for document understanding and must handle diverse file formats reliably with multiple fallback strategies to maximize success rate.

## What Changes
- Implement text extraction pipeline with multiple extractor backends
- Add Docling as primary extractor for PDFs and Office documents (high-quality table/structure preservation)
- Add pypdf as fallback extractor for simple PDFs (lightweight, fast)
- Add plain text extractor for .txt, .md, and other text files
- Store extracted text as **compressed sidecars** in `~/.lucien/extracted_text/` (hash-based filenames with gzip compression: `.txt.gz`)
- Compression provides 70-90% storage reduction using built-in Python gzip (no dependencies)
- Record extraction results in `extractions` database table with status, method, and error tracking
- Add `lucien extract` CLI command to run extraction pipeline
- Support resumable extraction (skip already-extracted files)
- Add progress bars and rich console output for extraction operations
- Design allows future migration to PostgreSQL/pgvector for embeddings and advanced queries

## Impact
- Affected specs: `text-extraction` (NEW)
- Affected code:
  - `lucien/extractors/` package (implement all extractors)
  - `lucien/extractors/docling.py` (implement Docling integration)
  - `lucien/extractors/pypdf.py` (implement PyPDF fallback)
  - `lucien/extractors/text.py` (already exists as stub, implement fully)
  - `lucien/cli.py` (implement extract command)
  - `lucien/db.py` (already has extractions table schema)
  - `pyproject.toml` (add optional extraction dependencies)
  - Documentation (README, QUICKSTART)
- Dependencies:
  - `docling>=1.0.0` (optional, for advanced extraction)
  - `pypdf>=4.0.0` (optional, for fallback extraction)
  - `python-magic>=0.4.27` (optional, for MIME type detection)
- **NOT BREAKING**: This is a new feature, no breaking changes
