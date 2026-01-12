# Lucien Quickstart Guide

This document helps you get started with the newly scaffolded Lucien project.

## What Was Created

### Project Specification

- **`openspec/project.md`** - Comprehensive project specification with:
  - Goals and non-goals
  - Architecture (5-phase pipeline)
  - Data model (SQLite schema)
  - Key conventions (naming, taxonomy, vocabularies)
  - Technology stack
  - Milestones and roadmap

### Core Python Package

```
lucien/
├── __init__.py          # Package metadata (v0.1.0)
├── cli.py               # Typer CLI entrypoint (scan, stats, init-config commands)
├── config.py            # Pydantic configuration with YAML loading
├── db.py                # SQLite database with schema and operations
├── scanner.py           # Phase 0: File scanning (WORKING)
├── extractors/          # Phase 1: Text extraction (stubs for Milestone 2)
│   ├── __init__.py
│   ├── docling.py       # Docling extractor (stub)
│   ├── pypdf.py         # PyPDF fallback (stub)
│   └── text.py          # Plain text extractor (WORKING)
├── llm/                 # Phase 2: AI labeling (stubs for Milestone 3)
│   ├── __init__.py
│   ├── client.py        # LM Studio client
│   ├── models.py        # Pydantic models (LabelOutput)
│   └── prompts.py       # Prompt templates
├── planner.py           # Phase 3: Plan generation (stub for Milestone 4)
├── materialize.py       # Phase 4: Staging mirror (stub for Milestone 4)
└── tags_macos.py        # macOS Finder tags (stub for Milestone 4)
```

### Tests

- **`tests/test_config.py`** - Example tests for configuration and scanner
- **`tests/__init__.py`** - Test suite initialization

### Configuration

- **`pyproject.toml`** - Python package configuration with all dependencies
- **`lucien.example.yaml`** - Example configuration with detailed comments
- **`.gitignore`** - Git ignore patterns

### Documentation

- **`README.md`** - Project overview, quickstart, architecture, CLI reference
- **`CONTRIBUTING.md`** - Development guidelines, OpenSpec workflow
- **`LICENSE`** - MIT license
- **`QUICKSTART.md`** - This file

## Current Status: Milestone 1 (v0.1) ✅

**What's Working:**
- ✅ File scanning and indexing (Phase 0)
- ✅ SQLite database with full schema
- ✅ Configuration management (YAML + env vars)
- ✅ CLI framework with `scan`, `stats`, `init-config` commands
- ✅ Progress bars and rich console output

**What's Next:**
- Milestone 2: Text extraction (Phase 1)
- Milestone 3: AI labeling (Phase 2)
- Milestone 4: Planning and materialization (Phases 3-4)

## Getting Started (5 Minutes)

### 1. Install Dependencies

```bash
# Using uv (recommended)
uv venv
source .venv/bin/activate
uv pip install -e .

# Or using pip
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### 2. Initialize Configuration

```bash
lucien init-config
```

This creates `lucien.yaml` in your current directory.

### 3. Edit Configuration

```bash
# Edit lucien.yaml and set your source_root
vim lucien.yaml
```

Example:
```yaml
source_root: /path/to/your/documents
```

### 4. Test the Scanner

```bash
# Dry run (doesn't write to database)
lucien scan /path/to/test/folder --dry-run

# Actual scan
lucien scan /path/to/test/folder

# Check statistics
lucien stats
```

## End-to-End Test

```bash
# 1. Create test directory
mkdir -p /tmp/lucien-test/documents
echo "Sample document" > /tmp/lucien-test/documents/sample.txt
echo "Another file" > /tmp/lucien-test/documents/readme.md

# 2. Initialize config
lucien init-config

# 3. Scan test directory
lucien scan /tmp/lucien-test/documents

# 4. Check statistics
lucien stats

# Expected output:
# ✓ Indexed 2 files
# Total files in database: 2
```

## Next Steps

### For Users

1. **Scan your documents**
   ```bash
   lucien scan /path/to/your/documents
   ```

2. **Wait for Milestone 2-4** implementations for:
   - Text extraction
   - AI labeling
   - Plan generation
   - Staging mirror creation

### For Developers

1. **Set up development environment**
   ```bash
   uv pip install -e ".[dev]"
   ```

2. **Run tests**
   ```bash
   pytest
   ```

3. **Pick a milestone to work on**
   - See `openspec/project.md` for details
   - See `CONTRIBUTING.md` for guidelines

4. **Create a change proposal** (if adding features)
   ```bash
   openspec list --specs
   # Follow OpenSpec workflow in CONTRIBUTING.md
   ```

## Key Commands

```bash
# Scanning
lucien scan <source_root>              # Scan and index files
lucien scan <path> --dry-run           # Count files without indexing
lucien scan <path> --db custom.db      # Use custom database

# Statistics
lucien stats                           # Show database statistics

# Configuration
lucien init-config                     # Create lucien.yaml
lucien init-config --user              # Create ~/.config/lucien/config.yaml

# Development
pytest                                 # Run tests
black lucien/                          # Format code
ruff check lucien/                     # Lint code
mypy lucien/                           # Type check
```

## Architecture Overview

### Pipeline Phases

1. **Phase 0: Scan/Index** (✅ WORKING)
   - Recursively scan source backup
   - Compute SHA256 hashes
   - Store metadata in SQLite

2. **Phase 1: Text Extraction** (⏳ Milestone 2)
   - Extract text from PDFs, Office docs
   - Store as sidecars in `10_extracted_text/`

3. **Phase 2: AI Labeling** (⏳ Milestone 3)
   - Call LM Studio for document classification
   - Store labels with confidence scores
   - Auto-escalate to larger model when needed

4. **Phase 3: Plan Generation** (⏳ Milestone 4)
   - Generate `plan.jsonl` and `plan.csv`
   - Human-reviewable transformation plan

5. **Phase 4: Materialize** (⏳ Milestone 4)
   - Create staging mirror with organized files
   - Apply canonical filenames
   - Apply macOS Finder tags

6. **Phase 5: DEVONthink Import** (⏳ Milestone 5)
   - Manual import to DEVONthink
   - Documentation and helpers provided

### Database Schema

SQLite tables:
- `files` - File inventory from source backup
- `extractions` - Text extraction results
- `labels` - AI labeling results
- `plans` - Materialization plans
- `runs` - Run history and versioning

### Configuration Hierarchy

1. Defaults (in `config.py`)
2. User config (`~/.config/lucien/config.yaml`)
3. Project config (`./lucien.yaml`)
4. Environment variables (`LUCIEN_*`)

## Configuration Reference

Key settings in `lucien.yaml`:

```yaml
# Core paths
source_root: /Volumes/Backup/Documents
index_db: ~/.local/share/lucien/index.db
staging_root: ~/Documents/Lucien-Staging

# LLM (for Milestone 3)
llm:
  base_url: http://localhost:1234/v1
  default_model: qwen2.5-7b-instruct
  escalation_model: qwen2.5-14b-instruct
  escalation_threshold: 0.7

# Taxonomy (customize to your needs)
taxonomy:
  top_level:
    - "01 Identity & Legal"
    - "02 Medical"
    - "03 Financial"
    - "04 Taxes"
    # ... etc
```

See `lucien.example.yaml` for full configuration with comments.

## Troubleshooting

### "source_root must be provided"

Edit `lucien.yaml` and set `source_root`:
```yaml
source_root: /path/to/your/documents
```

### "Database is locked"

Ensure no other Lucien process is running:
```bash
ps aux | grep lucien
```

### "Permission denied" during scan

Check that the source directory is readable:
```bash
ls -l /path/to/source
```

## Resources

- **Project Spec**: `openspec/project.md`
- **OpenSpec Guide**: `openspec/AGENTS.md`
- **Development Guide**: `CONTRIBUTING.md`
- **Example Config**: `lucien.example.yaml`
- **Tests**: `tests/`

## Questions?

- Open an issue on GitHub
- See README.md for more details
- Check CONTRIBUTING.md for development workflow

---

**Current Version**: v0.1.0 (Milestone 1 - Core Pipeline)

**Next Milestone**: v0.2.0 (Text Extraction)
