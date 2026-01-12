# Lucien: Library Builder System

## Overview

Lucien is a Mac-first, open-source document library builder that transforms an **immutable source backup** into a searchable, consistently organized, and tagged document library ready for import into DEVONthink. The system uses local LLMs (via LM Studio) to intelligently label, categorize, and organize documents while maintaining complete auditability and never modifying the original source.

**One-liner**: Build a DEVONthink-ready, searchable document library from an immutable backup with AI-powered labeling, native macOS tags, and full auditability.

## Goals

### Primary Goals
1. **Immutability**: Never modify the source backup; all operations are read-only on source
2. **Auditability**: Every action traceable via hashes, plans, and versioned metadata
3. **Local-first**: No cloud dependencies; all AI processing via local LLM (LM Studio)
4. **Mac-native**: Leverage macOS Finder tags, filesystem features, and native tooling
5. **DEVONthink-ready**: Produce a staging library with consistent naming, tagging, and taxonomy suitable for clean import
6. **Idempotency**: All pipeline stages can be resumed and re-run safely
7. **Reviewability**: Generate human-readable plans (CSV, JSONL) before materializing changes

### Secondary Goals
- Extensible architecture for additional extractors (OCR, specialized parsers)
- Configurable taxonomies and controlled vocabularies
- Support for both copy and hardlink modes for staging mirror
- Rich CLI with progress bars and detailed logging
- Deterministic outputs where possible

## Non-Goals

### Explicit Non-Goals
1. **Not a DMS**: Lucien is a builder/organizer, not a document management system
2. **Not interactive**: No GUI; DEVONthink is the interaction layer
3. **Not a sync tool**: One-way transformation from backup to staging
4. **Not cloud-based**: No cloud LLM APIs, no cloud storage
5. **Not real-time**: Batch processing pipeline, not live monitoring
6. **Not multi-platform**: macOS-first; other platforms not prioritized

### Deferred Features (Future)
- OCR integration (hooks designed, implementation deferred)
- Embedding-based similarity clustering (design for it, implement later)
- DEVONthink AppleScript automation (provide helpers, not full automation)
- Advanced reranking or duplicate detection

## Architecture

### Pipeline Phases

```
[Immutable Source Backup]
         ↓
    Phase 0: Scan/Index
         ↓
 [SQLite Database + Metadata]
         ↓
    Phase 1: Text Extraction
         ↓
 [10_extracted_text/ sidecars]
         ↓
    Phase 2: AI Labeling (LLM)
         ↓
 [Label results in DB]
         ↓
    Phase 3: Plan Generation
         ↓
 [plan.jsonl, plan.csv, apply.sh]
         ↓
    Phase 4: Materialize Staging
         ↓
 [Staging Mirror + Finder Tags]
         ↓
    Phase 5: DEVONthink Import
         ↓
 [DEVONthink Library]
```

### Phase Details

#### Phase 0: Scan/Index
- **Input**: Root path to backup
- **Process**:
  - Recursive filesystem crawl
  - Collect: path, size, mtime/ctime, MIME type, SHA256 hash
  - Skip configurable junk directories (caches, .git, etc.)
- **Output**: SQLite `files` table with complete inventory
- **Idempotency**: Hash-based; re-scanning updates only changed files

#### Phase 1: Text Extraction
- **Input**: File records from database
- **Process**:
  - Extract text from PDFs, Office docs, text files
  - Primary: Docling for PDF/document extraction
  - Fallback: pypdf, textract, or custom parsers
  - OCR hooks designed but not implemented in v1
- **Output**:
  - Text sidecars in `10_extracted_text/` (`.txt` or `.md`)
  - Extraction metadata in `extractions` table
- **Idempotency**: Skip files with existing successful extractions

#### Phase 2: AI Labeling
- **Input**: File metadata + extracted text
- **Process**:
  - Call LM Studio OpenAI-compatible API (`http://localhost:1234/v1`)
  - Default model: Qwen2.5-Instruct-7B
  - Escalation model: Qwen2.5-Instruct-14B for:
    - confidence < threshold
    - doc_type in {Taxes, Medical, Legal, Insurance}
    - missing critical fields (date, issuer)
  - Prompt includes: filename, parent folders, text excerpts, metadata
  - Output: Strict JSON schema (validated with Pydantic)
- **Output**:
  - `labels` table with:
    - doc_type (controlled vocabulary)
    - title
    - canonical_filename
    - suggested_tags (list)
    - target_group_path (taxonomy path)
    - date (ISO), issuer/source
    - confidence (0..1)
    - why (explanation, 1-2 sentences)
  - Prompt version hash + model name for traceability
- **Idempotency**: Re-labeling allowed; versions tracked

#### Phase 3: Plan Generation
- **Input**: Label results from database
- **Process**:
  - Generate reviewable transformation plan
  - Includes: rename_to, copy_to/link_to path, tags, needs_review flags
- **Output**:
  - `plan.jsonl` (machine-readable, one record per file)
  - `plan.csv` (human review in Numbers/Excel)
  - `apply.sh` (optional, for mirror-only actions)
  - Records in `plans` table
- **Reviewability**: User can edit CSV before materialization

#### Phase 4: Materialize Staging Mirror
- **Input**: Approved plan (JSONL or CSV)
- **Process**:
  - Create staging mirror directory tree
  - Copy or hardlink files (configurable via `--mode`)
  - Apply canonical filenames in mirror
  - Apply macOS Finder tags (native tags via xattr)
- **Output**: Complete staging library ready for DEVONthink
- **Safety**: Never modifies source; all operations in staging area

#### Phase 5: DEVONthink Import Support
- **Input**: Staging library
- **Process**: Manual import by user
- **Support Provided**:
  - Recommended taxonomy layout
  - DT import checklist
  - Optional AppleScript helper templates
- **Note**: No automated DT integration in v1

### Data Model

#### SQLite Schema

```sql
-- File inventory from source backup
CREATE TABLE files (
    id INTEGER PRIMARY KEY,
    path TEXT NOT NULL UNIQUE,
    sha256 TEXT NOT NULL,
    size INTEGER NOT NULL,
    mime_type TEXT,
    mtime INTEGER,
    ctime INTEGER,
    scan_run_id INTEGER REFERENCES runs(id),
    created_at INTEGER DEFAULT (strftime('%s', 'now'))
);

-- Text extraction results
CREATE TABLE extractions (
    id INTEGER PRIMARY KEY,
    file_id INTEGER NOT NULL REFERENCES files(id),
    method TEXT NOT NULL, -- 'docling', 'pypdf', 'textract', etc.
    status TEXT NOT NULL, -- 'success', 'failed', 'skipped'
    output_path TEXT,     -- Path to sidecar .txt/.md
    error TEXT,
    extraction_run_id INTEGER REFERENCES runs(id),
    created_at INTEGER DEFAULT (strftime('%s', 'now')),
    UNIQUE(file_id, extraction_run_id)
);

-- AI labeling results
CREATE TABLE labels (
    id INTEGER PRIMARY KEY,
    file_id INTEGER NOT NULL REFERENCES files(id),
    doc_type TEXT NOT NULL,
    title TEXT,
    canonical_filename TEXT,
    suggested_tags TEXT,  -- JSON array
    target_group_path TEXT,
    date TEXT,            -- ISO date
    issuer TEXT,
    source TEXT,
    confidence REAL,
    why TEXT,
    model_name TEXT NOT NULL,
    prompt_hash TEXT NOT NULL,
    labeling_run_id INTEGER REFERENCES runs(id),
    created_at INTEGER DEFAULT (strftime('%s', 'now')),
    UNIQUE(file_id, labeling_run_id)
);

-- Materialization plans
CREATE TABLE plans (
    id INTEGER PRIMARY KEY,
    file_id INTEGER NOT NULL REFERENCES files(id),
    label_id INTEGER REFERENCES labels(id),
    operation TEXT NOT NULL, -- 'copy', 'hardlink', 'skip'
    source_path TEXT NOT NULL,
    target_path TEXT NOT NULL,
    target_filename TEXT NOT NULL,
    tags TEXT,            -- JSON array
    needs_review BOOLEAN DEFAULT 0,
    plan_run_id INTEGER REFERENCES runs(id),
    created_at INTEGER DEFAULT (strftime('%s', 'now'))
);

-- Run history and versioning
CREATE TABLE runs (
    id INTEGER PRIMARY KEY,
    run_type TEXT NOT NULL, -- 'scan', 'extract', 'label', 'plan', 'materialize'
    config TEXT,            -- JSON snapshot of config
    started_at INTEGER DEFAULT (strftime('%s', 'now')),
    completed_at INTEGER,
    status TEXT DEFAULT 'running', -- 'running', 'completed', 'failed'
    error TEXT
);
```

## Key Conventions

### Canonical Filename Format

Default format:
```
YYYY-MM-DD__Domain__Issuer__Title.ext
```

Examples:
- `2024-03-15__Financial__Chase__Checking-Statement.pdf`
- `2023-12-31__Taxes__IRS__1040-Form.pdf`
- `2024-01-10__Medical__Kaiser__Lab-Results.pdf`

### Default Taxonomy (Top-Level)

```
01 Identity & Legal/
02 Medical/
03 Financial/
04 Taxes/
05 Insurance/
06 Home/
07 Vehicles/
08 Work & Retirement/
09 Travel/
10 Family Photos & Media/
98 Uncategorized/
99 Needs Review/
```

Configurable via YAML/TOML; sub-folders created as needed by LLM.

### Controlled Vocabularies

#### doc_type (examples)
- `identity`, `legal`, `contract`, `deed`, `will`
- `medical`, `prescription`, `lab_result`, `insurance_eob`
- `financial`, `bank_statement`, `investment`, `receipt`
- `tax`, `w2`, `1099`, `1040`
- `insurance`, `policy`, `claim`
- `home`, `mortgage`, `utility`, `repair`
- `vehicle`, `registration`, `maintenance`, `insurance`
- `work`, `payslip`, `401k`, `retirement`
- `travel`, `passport`, `visa`, `itinerary`, `booking`
- `photo`, `video`, `media`
- `other`, `uncategorized`

User-extendable via config.

#### suggested_tags (examples)
- `important`, `action-required`, `archived`
- `tax-deductible`, `warranty`, `recurring`
- Person names, project names, location names
- Year tags: `2024`, `2023`, etc.

User-extendable via config.

### LLM Prompt Strategy

#### Context Provided to Model
- Filename and parent folder path
- Extracted text (top N characters + key snippets, chunked if needed)
- Basic file metadata (size, dates)
- Available doc_types and taxonomy
- Available tags

#### Output Schema (Pydantic)
```python
class LabelOutput(BaseModel):
    doc_type: str
    title: str
    canonical_filename: str
    suggested_tags: List[str]
    target_group_path: str
    date: Optional[str]  # ISO format
    issuer: Optional[str]
    source: Optional[str]
    confidence: float  # 0.0 to 1.0
    why: str  # 1-2 sentences
```

#### Escalation Rules
Use 14B model when:
- `confidence < 0.7` (configurable threshold)
- `doc_type` in escalation list (e.g., Taxes, Medical, Legal)
- Critical fields missing (date, issuer) on first pass

### macOS Finder Tags

Apply tags using native macOS extended attributes:
- Prefer Python `xattr` library or `osxmetadata`
- Fallback to `tag` CLI if present
- Tags are visible in Finder and preserved through DT import

## Technology Stack

### Core Dependencies
- **Python**: 3.11+ (Apple Silicon optimized)
- **CLI**: Typer + Rich (progress bars, tables, logging)
- **Database**: SQLite (single-file, embedded)
- **Config**: Pydantic Settings + YAML/TOML
- **LLM Client**: OpenAI Python SDK (for LM Studio compatibility)
- **Text Extraction**: Docling (primary), pypdf, textract (fallbacks)
- **macOS Tags**: xattr, osxmetadata
- **Testing**: pytest

### External Services
- **LM Studio**: Local LLM runtime at `http://localhost:1234/v1`
  - Models: Qwen2.5-Instruct-7B (default), Qwen2.5-Instruct-14B (escalation)
  - Future: bge-m3 for embeddings (similarity clustering)

### Development Tools
- **Package Manager**: uv or poetry
- **Linting**: ruff
- **Type Checking**: mypy
- **Formatting**: black

## Configuration

### Config File Locations
1. `~/.config/lucien/config.yaml` (user config)
2. `./lucien.yaml` (project-local config)
3. Environment variables (override)

### Config Schema (Example)
```yaml
# Source and outputs
source_root: /Volumes/Backup/Documents
index_db: ~/.local/share/lucien/index.db
extracted_text_dir: ~/.local/share/lucien/extracted_text
staging_root: ~/Documents/Lucien-Staging

# LLM settings
llm:
  base_url: http://localhost:1234/v1
  default_model: qwen2.5-7b-instruct
  escalation_model: qwen2.5-14b-instruct
  escalation_threshold: 0.7
  escalation_doc_types:
    - taxes
    - medical
    - legal
    - insurance

# Extraction
extraction:
  skip_extensions:
    - .jpg
    - .png
    - .mp4
    - .zip
  methods:
    - docling
    - pypdf
    - textract

# Taxonomy
taxonomy:
  top_level:
    - "01 Identity & Legal"
    - "02 Medical"
    - "03 Financial"
    - "04 Taxes"
    - "05 Insurance"
    - "06 Home"
    - "07 Vehicles"
    - "08 Work & Retirement"
    - "09 Travel"
    - "10 Family Photos & Media"
    - "98 Uncategorized"
    - "99 Needs Review"

# Doc types and tags (controlled vocabularies)
doc_types:
  - identity
  - legal
  - medical
  - financial
  - tax
  - insurance
  - home
  - vehicle
  - work
  - travel
  - photo
  - other

tags:
  - important
  - action-required
  - archived
  - tax-deductible
  - warranty
  - recurring

# Naming
naming:
  format: "YYYY-MM-DD__Domain__Issuer__Title"
  separator: "__"
  date_format: "%Y-%m-%d"

# Scanning
scan:
  skip_dirs:
    - .git
    - .cache
    - __pycache__
    - node_modules
    - .DS_Store

# Materialization
materialize:
  default_mode: hardlink  # or 'copy'
  apply_tags: true
  create_dirs: true
```

## Risks and Mitigations

### Risk: LLM Hallucination
- **Impact**: Incorrect labeling, wrong dates, bad taxonomy placement
- **Mitigation**:
  - Strict JSON schema validation
  - Confidence thresholds
  - Escalation to larger model
  - Human review via CSV plan
  - Auditability: all labels versioned with prompt hash

### Risk: Hash Collisions
- **Impact**: File identity confusion
- **Mitigation**: Use SHA256 (cryptographically strong); collision probability negligible

### Risk: Filesystem Limits
- **Impact**: Very large backups may exhaust inodes, disk space
- **Mitigation**:
  - Hardlink mode (same filesystem) saves space
  - Progress tracking allows resumption
  - Skip large files or binaries (configurable)

### Risk: LM Studio Unavailable
- **Impact**: Labeling phase fails
- **Mitigation**:
  - Clear error messages
  - Retry logic with exponential backoff
  - Allow manual labeling via CSV editing

### Risk: Source Backup Modification (Accidental)
- **Impact**: Integrity loss, auditability broken
- **Mitigation**:
  - All source operations are read-only
  - No writes to source paths in code
  - Ideally mount source as read-only (user responsibility)

### Risk: DEVONthink Import Issues
- **Impact**: Tags or structure not imported correctly
- **Mitigation**:
  - Provide detailed import checklist
  - Test with small sample first
  - Document DT preferences/settings

## Milestones

### Milestone 1: Core Pipeline (v0.1)
- [ ] Phase 0: Scan/Index working
- [ ] SQLite schema implemented with migrations
- [ ] CLI: `scan` command end-to-end
- [ ] Config loading from YAML
- [ ] Basic logging and progress bars

### Milestone 2: Text Extraction (v0.2)
- [ ] Phase 1: Text extraction with Docling
- [ ] Fallback to pypdf for simple PDFs
- [ ] CLI: `extract` command
- [ ] Sidecar file management

### Milestone 3: AI Labeling (v0.3)
- [ ] Phase 2: LM Studio client implementation
- [ ] Prompt engineering for labeling
- [ ] JSON schema validation
- [ ] CLI: `label` command
- [ ] Escalation logic

### Milestone 4: Planning & Materialization (v0.4)
- [ ] Phase 3: Plan generation (JSONL, CSV)
- [ ] Phase 4: Staging mirror creation
- [ ] macOS Finder tag application
- [ ] CLI: `plan` and `materialize` commands

### Milestone 5: DEVONthink Ready (v0.5)
- [ ] Phase 5: DT import documentation
- [ ] End-to-end testing with sample library
- [ ] Configuration refinement
- [ ] Documentation and examples

### Milestone 6: Polish & Release (v1.0)
- [ ] Error handling and edge cases
- [ ] Performance optimization
- [ ] Comprehensive tests
- [ ] User documentation
- [ ] Release on GitHub

## Extension Points

### Future Enhancements (Post-v1)
1. **OCR Integration**: tesseract/OCRmyPDF for scanned documents
2. **Embeddings**: bge-m3 for similarity clustering and duplicate detection
3. **Advanced Reranking**: Use embeddings to suggest better taxonomy placement
4. **DEVONthink Automation**: Full AppleScript integration for import
5. **Web UI**: Optional web-based review interface for plans
6. **Multi-source**: Support multiple backup roots
7. **Incremental Updates**: Detect new files and re-process only deltas

### Plugin Architecture (Future)
- Custom extractors: `lucien.extractors.register()`
- Custom labeling strategies: `lucien.llm.strategies.register()`
- Custom naming conventions: `lucien.naming.register()`
- Custom taxonomy loaders: `lucien.taxonomy.register()`

## Testing Strategy

### Unit Tests
- Database operations (CRUD, migrations)
- Config loading and validation
- Text extraction (with fixtures)
- LLM client (with mocked responses)
- Naming convention generation
- Tag application (mocked xattr)

### Integration Tests
- End-to-end pipeline with sample files
- LM Studio integration (requires local instance)
- Hardlink vs copy mode
- Plan CSV editing and re-import

### Manual Tests
- Large library (10K+ files)
- DEVONthink import workflow
- Finder tag verification
- Resume/idempotency

## Documentation

### User Documentation
- **README.md**: Quickstart, installation, basic usage
- **docs/installation.md**: Detailed setup (Python, LM Studio, models)
- **docs/configuration.md**: Config file reference
- **docs/workflow.md**: Step-by-step pipeline walkthrough
- **docs/devonthink.md**: DT import guide
- **docs/troubleshooting.md**: Common issues and solutions

### Developer Documentation
- **CONTRIBUTING.md**: Development setup, coding standards
- **docs/architecture.md**: System design deep-dive
- **docs/extending.md**: Plugin and extension guide
- **docs/schema.md**: SQLite schema reference
- **docs/prompts.md**: LLM prompt engineering notes

## Naming Conventions (Code)

### Python
- **Modules**: `snake_case` (e.g., `scanner.py`, `llm_client.py`)
- **Classes**: `PascalCase` (e.g., `FileScanner`, `LLMClient`)
- **Functions/Methods**: `snake_case` (e.g., `scan_directory()`, `extract_text()`)
- **Constants**: `UPPER_SNAKE_CASE` (e.g., `DEFAULT_MODEL`, `MAX_RETRIES`)

### CLI Commands
- Use dash-case for multi-word commands if needed
- Prefer single verbs: `scan`, `extract`, `label`, `plan`, `materialize`

### Database
- **Tables**: `snake_case` plural (e.g., `files`, `labels`, `plans`)
- **Columns**: `snake_case` (e.g., `file_id`, `created_at`)

## Success Criteria

### Functional
- [ ] Can scan 10K+ files in < 10 minutes
- [ ] Text extraction succeeds for 95%+ of PDFs
- [ ] LLM labeling produces valid JSON 99%+ of time
- [ ] Escalation improves confidence by 20%+ on average
- [ ] Staging mirror creation succeeds without source modification
- [ ] Finder tags visible in macOS Finder
- [ ] DEVONthink import works with default settings

### Quality
- [ ] 80%+ test coverage
- [ ] All code passes ruff, mypy, black
- [ ] Documentation covers all CLI commands
- [ ] Configuration examples provided
- [ ] Error messages are actionable

### User Experience
- [ ] Single command for end-to-end run
- [ ] Progress bars show live status
- [ ] Plan CSV is human-readable and editable
- [ ] Logs provide traceability for debugging
- [ ] Installation takes < 15 minutes

## License

MIT License (open-source)

## Maintainer

Jeff Miller (jeffmlr)

---

**Last Updated**: 2026-01-12
