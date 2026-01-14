# Design: Text Extraction Pipeline

## Context
Text extraction is the foundation for document understanding in Lucien. The system must extract text from diverse file formats (PDFs, Office documents, text files) to enable AI labeling in Phase 2. The challenge is handling varied file formats, encodings, corrupted files, and extraction failures gracefully while maintaining performance and auditability.

**Constraints:**
- Must work with local files only (no cloud services)
- Must preserve original source files (read-only)
- Must be idempotent and resumable
- Must handle large collections (10K+ files)
- Must provide clear error messages for failures

**Stakeholders:**
- End users: Need reliable text extraction for their documents
- Phase 2 (AI labeling): Depends on extracted text quality
- Developers: Need extensible architecture for future extractors (OCR, etc.)

## Goals / Non-Goals

### Goals
- Extract text from PDFs, Office documents (.docx, .xlsx, .pptx), and text files
- Provide multiple extraction backends with automatic fallback
- Store extracted text as hash-based sidecars for deduplication
- Record extraction metadata (method, status, errors) for auditability
- Support resumable extraction (skip already-extracted files)
- Graceful handling of failures (corrupted files, encoding issues, etc.)

### Non-Goals
- OCR for scanned documents (deferred to future milestone)
- Image extraction or processing (Phase 2 focuses on text)
- Real-time extraction (batch processing only)
- Format conversion (extract text only, not reformatting)
- Cloud-based extraction services

## Decisions

### Decision 1: Multi-Backend Architecture with Fallback Chain
**What:** Use multiple extraction backends (Docling, pypdf, plain text) with automatic fallback based on file type and extraction success.

**Why:**
- No single extractor works for all file types perfectly
- Docling provides best quality for PDFs with tables/structure but may fail on some files
- pypdf is lightweight and works for simple PDFs when Docling fails
- Plain text extractor handles .txt, .md, and other text files
- Fallback increases overall success rate

**Alternatives considered:**
- Single extractor (Docling only): Rejected - lower success rate, no fallback
- pypdf only: Rejected - poor table extraction, no Office document support
- External service (Adobe API, etc.): Rejected - violates local-first principle

**Implementation:**
```python
class ExtractionPipeline:
    def extract(self, file_info) -> ExtractionResult:
        # Determine extractors based on file type
        extractors = self._select_extractors(file_info.mime_type, file_info.extension)

        # Try each extractor in order until one succeeds
        for extractor in extractors:
            result = extractor.extract(file_info.path)
            if result.status == "success":
                return result

        # All failed
        return ExtractionResult(status="failed", error="All extractors failed")
```

### Decision 2: Hash-Based Sidecar Filenames with Compression
**What:** Store extracted text using SHA256 hash as filename with gzip compression: `~/.lucien/extracted_text/{sha256}.txt.gz`

**Why:**
- Automatic deduplication: identical files share one sidecar
- Content-addressable: sidecar survives file renames/moves
- Collision-free: SHA256 virtually eliminates collisions
- Simple: no complex directory structure needed
- **Storage efficient:** 70-90% compression (plain text compresses very well)
- Built-in Python gzip module (no dependencies)
- Still inspectable: `zcat ~/.lucien/extracted_text/{hash}.txt.gz`

**Alternatives considered:**
- Plain text files: Rejected - wastes storage (500MB+ for large collections)
- SQLite BLOBs: Rejected - harder to inspect, single point of failure
- Mirror source structure: Rejected - complex, doesn't handle duplicates
- Sequential IDs: Rejected - not content-addressable, harder to debug
- Filename-based: Rejected - name collisions, no deduplication

**Implementation:**
```python
# Writing compressed text
import gzip
with gzip.open(output_path, 'wt', encoding='utf-8') as f:
    f.write(extracted_text)

# Reading compressed text
with gzip.open(sidecar_path, 'rt', encoding='utf-8') as f:
    text = f.read()
```

**Directory structure:**
```
~/.lucien/extracted_text/
  ├── abc123def456...789.txt.gz
  ├── 123456abcdef...xyz.txt.gz
  └── ...
```

**Storage impact:**
- Typical 50KB text file → ~10KB compressed (80% reduction)
- 20K documents @ 25KB avg → 500MB raw → ~100MB compressed
- Built-in compression, transparent to consumers

**Future migration path:**
- Current architecture allows future migration to PostgreSQL/pgvector
- Compressed files can be batch-imported to JSONB or BYTEA columns
- Embeddings can be added alongside text in PostgreSQL
- No breaking changes to core pipeline logic

### Decision 3: Extraction Result Schema
**What:** Standardized `ExtractionResult` dataclass for all extractors:

```python
@dataclass
class ExtractionResult:
    status: str  # 'success', 'failed', 'skipped'
    method: str  # 'docling', 'pypdf', 'text'
    text: Optional[str]
    output_path: Optional[Path]
    error: Optional[str]
    metadata: dict  # PDF title, author, etc.
```

**Why:**
- Uniform interface for all extractors
- Easy to add new extractors without breaking existing code
- Clear status tracking for database records
- Metadata preservation for future use (AI labeling can use titles, dates)

### Decision 4: Optional Dependencies with Graceful Fallback
**What:** Make extraction libraries optional dependencies, gracefully degrade when missing.

**Why:**
- Users may not need all extractors (text-only users don't need Docling)
- Docling has heavy dependencies (PyTorch, transformers)
- Reduces installation friction for basic use cases
- Allows minimal installs for testing/CI

**Implementation:**
```python
try:
    from docling.document_converter import DocumentConverter
    DOCLING_AVAILABLE = True
except ImportError:
    DOCLING_AVAILABLE = False

class DoclingExtractor:
    def __init__(self):
        if not DOCLING_AVAILABLE:
            raise RuntimeError("Docling not installed. Run: pip install lucien[extraction]")
```

### Decision 5: Extraction Run Tracking
**What:** Track each extraction run with `extraction_run_id` in database, link to `runs` table.

**Why:**
- Enables versioning: can re-extract files with updated extractors
- Auditability: know when/how each file was extracted
- Debugging: track extraction performance over time
- Idempotency: skip files with successful extractions in current run

**Schema:**
```sql
CREATE TABLE extractions (
    file_id INTEGER REFERENCES files(id),
    extraction_run_id INTEGER REFERENCES runs(id),
    method TEXT,
    status TEXT,
    output_path TEXT,
    error TEXT,
    created_at INTEGER,
    UNIQUE(file_id, extraction_run_id)
);
```

### Decision 6: Text Truncation Strategy
**What:** Truncate extracted text to `max_text_length` (default: 50,000 characters), keep beginning and end.

**Why:**
- Large documents (100+ pages) exceed LLM context windows
- Full text not needed for labeling (first pages usually contain key info)
- Reduces storage and processing costs
- Keep end because signature, dates often at bottom

**Implementation:**
```python
if len(text) > max_length:
    head = text[:max_length // 2]
    tail = text[-(max_length // 2):]
    text = f"{head}\n\n[... truncated ...]\n\n{tail}"
```

## Risks / Trade-offs

### Risk: Docling Installation Complexity
- **Impact:** Users may struggle with PyTorch/transformers dependencies
- **Mitigation:**
  - Make Docling optional
  - Provide clear installation instructions
  - Add fallback to pypdf automatically
  - Document system requirements (memory, disk space)

### Risk: Extraction Performance on Large Collections
- **Impact:** 10K+ files may take hours to extract
- **Mitigation:**
  - Show progress bars with time estimates
  - Support resumable extraction (skip completed files)
  - Add `--limit` flag for testing on subsets
  - Consider parallel extraction in future (not v0.2)

### Risk: Encrypted or Corrupted PDFs
- **Impact:** Extraction fails, no text for AI labeling
- **Mitigation:**
  - Graceful error handling (record error, continue)
  - Clear error messages in database
  - Manual review possible via CSV export
  - Flag files for manual processing

### Risk: Incorrect MIME Type Detection
- **Impact:** Wrong extractor selected, extraction fails
- **Mitigation:**
  - Use both MIME type and file extension
  - Try fallback extractors on failure
  - Log extractor selection decisions
  - Allow manual `--method` override

### Risk: Disk Space for Sidecars
- **Impact:** Large text sidecars may fill disk
- **Mitigation:**
  - Truncate to max_text_length (50KB per file)
  - Use plain text format (not JSON/Markdown)
  - Document disk space requirements
  - Add cleanup command in future

## Migration Plan

**This is a new feature, no migration needed.**

Initial deployment:
1. Install extraction dependencies: `pip install lucien[extraction]`
2. Run extraction: `lucien extract`
3. Verify sidecars created in `~/.lucien/extracted_text/`
4. Check stats: `lucien stats`

Rollback: Not applicable (new feature, can be disabled by not running `extract` command)

## Open Questions

1. **Should we support incremental extraction (only new files)?**
   - Current: Re-run skips already-extracted files (idempotent)
   - Future: Add `--incremental` flag to only process files added since last scan
   - Decision: Defer to user feedback

2. **Should we extract embedded images from PDFs?**
   - Current: Text only
   - Future: Could add image extraction for AI vision models
   - Decision: Defer to Phase 2 requirements

3. **Should we support custom extractors via plugins?**
   - Current: Built-in extractors only
   - Future: Plugin architecture for user-defined extractors
   - Decision: Defer until proven need

4. **Should extracted text be Markdown or plain text?**
   - Current: Plain text (simple, universal)
   - Alternative: Markdown (preserves structure)
   - Decision: Plain text for v0.2, can add Markdown option later

5. **Should we cache Docling model files?**
   - Current: Docling handles caching internally
   - Future: Add `~/.lucien/cache/docling/` for explicit control
   - Decision: Use Docling defaults for now

6. **Future database architecture: PostgreSQL/pgvector?**
   - Current: SQLite + compressed file sidecars
   - Future consideration: PostgreSQL with text in JSONB/BYTEA, embeddings in pgvector
   - Benefits: Better concurrency, advanced queries, vector similarity search
   - Migration path: Compressed files can be batch-imported to PostgreSQL
   - Decision: SQLite for v0.2, evaluate PostgreSQL based on scale requirements
