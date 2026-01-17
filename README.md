# Lucien: Library Builder System

> Transform your document backups into organized, searchable, DEVONthink-ready libraries with AI-powered labeling

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Status: Alpha](https://img.shields.io/badge/status-alpha-orange.svg)]()

Lucien is a Mac-first, open-source document library builder that transforms **immutable source backups** into searchable, consistently organized, and tagged document libraries ready for import into DEVONthink. It uses local LLMs (via LM Studio) to intelligently label, categorize, and organize documents while maintaining complete auditability and never modifying the original source.

## Features

- **Immutable Source**: Never modifies your backup; all operations are read-only on source
- **AI-Powered Labeling**: Uses local LLMs (Qwen2.5 via LM Studio) for intelligent document categorization
- **Native macOS Tags**: Applies Finder tags that are preserved through DEVONthink import
- **Reviewable Plans**: Generates human-readable CSV plans before making any changes
- **Auditability**: Every action traceable via hashes, plans, and versioned metadata
- **Local-First**: No cloud dependencies; all AI processing runs locally
- **Idempotent Pipeline**: Resume and re-run any stage safely

## Status

**Current Version**: v0.2.0 (Alpha)

**What's Working**:
- ✅ Phase 0: File scanning and indexing
- ✅ Phase 1: Text extraction (Docling, pypdf, textract)
- ✅ Phase 2: AI labeling (LM Studio integration)
- ✅ Configuration management
- ✅ CLI framework

**In Development** (see [Milestones](#milestones)):
- ⏳ Phase 3-4: Planning and materialization (Milestone 4)

## Quick Start

### Prerequisites

1. **macOS** (Apple Silicon or Intel)
2. **Python 3.11+**
3. **LM Studio** with Qwen2.5 models (for AI labeling)
   - Download from [lmstudio.ai](https://lmstudio.ai/)
   - Install `qwen2.5-7b-instruct` (default) and optionally `qwen2.5-14b-instruct` (escalation)
   - Enable the local server (default: `http://localhost:1234`)

### Installation

```bash
# Clone the repository
git clone https://github.com/jeffmlr/lucien.git
cd lucien

# Install with uv (recommended)
uv venv
source .venv/bin/activate
uv pip install -e .

# Or with pip
pip install -e .
```

### Basic Usage

```bash
# 1. Initialize configuration
lucien init-config

# 2. Edit lucien.yaml to set your source_root
vim lucien.yaml

# 3. Scan your backup
lucien scan /path/to/backup

# 4. Extract text from documents
lucien extract

# 5. Label documents with AI (requires LM Studio running)
lucien label

# 6. Check statistics
lucien stats

# Future: Plan and materialize
# lucien plan
# lucien materialize plan.jsonl
```

## Architecture

Lucien implements a 5-phase pipeline:

```
Phase 0: Scan/Index          → SQLite Database (~/.lucien/db/)
Phase 1: Text Extraction     → Text sidecars (~/.lucien/extracted_text/)
Phase 2: AI Labeling (LLM)   → Labels in database
Phase 3: Plan Generation     → plan.jsonl, plan.csv (~/.lucien/plans/)
Phase 4: Materialize Staging → Organized staging mirror + tags
Phase 5: DEVONthink Import   → Manual import (with helpers)
```

Each phase is **idempotent** and **resumable**. The source backup is **never modified**.

## Configuration

Configuration is loaded from (in order of precedence):
1. `./lucien.yaml` (project-local config)
2. `~/.lucien/config.yaml` (user config)
3. `~/.config/lucien/config.yaml` (XDG user config, legacy)
4. Environment variables (prefix: `LUCIEN_`)
5. Built-in defaults

Example `lucien.yaml`:

```yaml
# Source and outputs
source_root: /Volumes/Backup/Documents
index_db: ~/.lucien/db/index.db
extracted_text_dir: ~/.lucien/extracted_text
plans_dir: ~/.lucien/plans
cache_dir: ~/.lucien/cache
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

# Taxonomy (configurable)
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
```

See [example configuration](lucien.example.yaml) for full options.

## AI Labeling

Lucien uses local LLMs via LM Studio for intelligent document classification. No data leaves your machine.

### LM Studio Setup

1. **Download LM Studio** from [lmstudio.ai](https://lmstudio.ai/)
2. **Install recommended models**:
   - `qwen2.5-7b-instruct` - Default model for general labeling
   - `qwen2.5-14b-instruct` - Escalation model for complex/sensitive docs
3. **Enable local server**: Settings → Local Server → Enable
4. **Load a model**: Models → Load the model you want to use

### Model Escalation

Lucien uses a two-tier model approach:

1. **Default model** (`qwen2.5-7b-instruct`): Fast, handles most documents
2. **Escalation model** (`qwen2.5-14b-instruct`): Used when:
   - Confidence score < 0.7 (configurable)
   - Document type is sensitive (taxes, medical, legal, insurance)
   - Critical fields (date, issuer) are missing for financial/legal docs

This balances speed with accuracy for important documents.

### What Gets Labeled

For each document, the LLM extracts:
- **Document type**: From controlled vocabulary (w2, bank_statement, medical, etc.)
- **Title**: Human-readable description
- **Canonical filename**: Standardized naming following conventions
- **Tags**: Domain, document type, provider, and status tags
- **Target path**: Taxonomy folder for organization
- **Date & Issuer**: When discernible from the document
- **Confidence score**: 0.0-1.0 indicating certainty

### Directory Structure

Lucien stores all application data in `~/.lucien/`:

```
~/.lucien/
├── db/
│   └── index.db              # SQLite database (files, extractions, labels, plans)
├── extracted_text/           # Text extraction sidecars
│   └── <sha256>.txt          # Extracted text keyed by file hash
├── plans/                    # Generated materialization plans
│   ├── plan_<timestamp>.jsonl
│   └── plan_<timestamp>.csv
├── logs/                     # Application logs
│   └── lucien.log
├── cache/                    # Optional cache (LLM responses, etc.)
└── config.yaml               # Optional user configuration
```

## CLI Commands

### Phase 0: Scan

```bash
lucien scan <source_root> [--db <path>] [--dry-run]
```

Scans a directory tree, computes SHA256 hashes, and indexes files in the database.

**Options**:
- `--db`: Override database path
- `--config`: Use specific config file
- `--dry-run`: Count files without writing to database

### Statistics

```bash
lucien stats [--db <path>]
```

Display database statistics (total files, extractions, labels, plans, runs).

### Initialize Config

```bash
lucien init-config [--output <path>] [--user]
```

Create a configuration file with defaults.

**Options**:
- `--output`: Output path (default: `./lucien.yaml`)
- `--user`: Create user config at `~/.config/lucien/config.yaml`

### Phase 1: Extract Text

```bash
lucien extract [--db <path>] [--limit <n>] [--force] [--workers <n>]
```

Extracts text from documents using Docling (primary), pypdf, or textract fallbacks.

**Options**:
- `--db`: Override database path
- `--limit`: Process only N files (for testing)
- `--force`: Re-extract already processed files
- `--workers`: Number of parallel workers (default: 4)

### Phase 2: AI Label

```bash
lucien label [--db <path>] [--model <name>] [--limit <n>] [--force] [--no-escalate]
```

Labels documents using local LLMs via LM Studio.

**Options**:
- `--model`: Override default model name
- `--limit`: Process only N files (for testing)
- `--force`: Re-label already processed files
- `--no-escalate`: Disable automatic model escalation

**Requirements**: LM Studio must be running with models loaded.

### Future Commands

```bash
# Phase 3: Plan Generation (Milestone 4)
lucien plan [--db <path>] [--output <dir>]

# Phase 4: Materialize (Milestone 4)
lucien materialize <plan_file> [--staging <dir>] [--mode copy|hardlink] [--apply-tags]
```

## Naming Conventions

Lucien generates canonical filenames following this pattern:

```
YYYY-MM-DD-Category-Issuer-Description.ext
```

- Use **hyphens** (`-`) to separate the four main fields
- Use **underscores** (`_`) within multi-word values

Examples:
- `2024-03-15-Financial-Chase_Bank-Statement.pdf`
- `2023-12-31-Taxes-IRS-1040_Form.pdf`
- `2024-01-10-Medical-Kaiser-Lab_Results_Jeff.pdf`
- `2024-05-17-Insurance-Unum-LTC_Claim_Nancy.pdf`

Family member names are appended when documents are person-specific.
Format is configurable in `lucien.yaml`.

## Milestones

### ✅ Milestone 1: Core Pipeline (v0.1)
- [x] Phase 0: Scan/Index working
- [x] SQLite schema implemented with migrations
- [x] CLI: `scan` command end-to-end
- [x] Config loading from YAML
- [x] Basic logging and progress bars

### ✅ Milestone 2: Text Extraction (v0.2)
- [x] Phase 1: Text extraction with Docling
- [x] Fallback to pypdf for simple PDFs
- [x] Fallback to textract for other formats
- [x] CLI: `extract` command
- [x] Sidecar file management (gzip compressed)

### ✅ Milestone 3: AI Labeling (v0.3) - CURRENT
- [x] Phase 2: LM Studio client implementation
- [x] Prompt engineering for labeling
- [x] Pydantic schema validation
- [x] CLI: `label` command with progress display
- [x] Two-tier model escalation (confidence + doc type)
- [x] Family member attribution in filenames

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

## Development

### Setup

```bash
# Install with dev dependencies
uv pip install -e ".[dev]"

# Run tests
pytest

# Run linters
ruff check lucien/
black --check lucien/
mypy lucien/

# Format code
black lucien/
ruff check --fix lucien/
```

### Project Structure

```
lucien/
├── __init__.py          # Package metadata
├── cli.py               # Typer CLI entrypoint
├── config.py            # Pydantic settings
├── db.py                # SQLite operations
├── scanner.py           # Phase 0: File scanning
├── extractors/          # Phase 1: Text extraction
│   ├── __init__.py
│   ├── docling.py
│   ├── pypdf.py
│   └── text.py
├── llm/                 # Phase 2: AI labeling
│   ├── __init__.py
│   ├── client.py        # LM Studio client
│   ├── models.py        # Pydantic schemas
│   ├── pipeline.py      # Labeling orchestration
│   └── prompts.py       # Prompt templates
├── planner.py           # Phase 3: Plan generation
├── materialize.py       # Phase 4: Staging mirror
└── tags_macos.py        # macOS Finder tags

tests/                   # Test suite
docs/                    # Documentation
openspec/                # OpenSpec project specs
```

## License

MIT License. See [LICENSE](LICENSE) for details.

## Contributing

Contributions welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## Credits

Created by Jeff Miller (jeffmlr)

## See Also

- [DEVONthink](https://www.devontechnologies.com/apps/devonthink) - Document management application
- [LM Studio](https://lmstudio.ai/) - Local LLM runtime
- [Qwen2.5](https://huggingface.co/Qwen) - Open-source LLM models
- [OpenSpec](https://openspec.dev/) - Specification framework

---

**Questions?** Open an issue or discussion on GitHub.
