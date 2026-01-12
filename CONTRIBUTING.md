# Contributing to Lucien

Thank you for your interest in contributing to Lucien! This document provides guidelines for development and contribution.

## Development Setup

### Prerequisites

- macOS (Apple Silicon or Intel)
- Python 3.11+
- Git
- Optional: LM Studio with Qwen2.5 models

### Getting Started

1. **Fork and clone the repository**

```bash
git clone https://github.com/your-username/lucien.git
cd lucien
```

2. **Create a virtual environment**

```bash
# Using uv (recommended)
uv venv
source .venv/bin/activate

# Or using venv
python3 -m venv .venv
source .venv/bin/activate
```

3. **Install development dependencies**

```bash
# Using uv
uv pip install -e ".[dev]"

# Or using pip
pip install -e ".[dev]"
```

4. **Run tests to verify setup**

```bash
pytest
```

## Development Workflow

### Project Structure

Lucien follows OpenSpec conventions:

- `openspec/project.md` - Project overview and conventions
- `lucien/` - Main package
- `tests/` - Test suite
- `docs/` - Documentation

### Coding Standards

#### Python Style

- Use **Black** for formatting (line length: 120)
- Use **Ruff** for linting
- Use **mypy** for type checking
- Follow PEP 8 naming conventions

#### Naming Conventions

- **Modules**: `snake_case` (e.g., `scanner.py`, `llm_client.py`)
- **Classes**: `PascalCase` (e.g., `FileScanner`, `LLMClient`)
- **Functions/Methods**: `snake_case` (e.g., `scan_directory()`, `extract_text()`)
- **Constants**: `UPPER_SNAKE_CASE` (e.g., `DEFAULT_MODEL`, `MAX_RETRIES`)

#### Code Quality

```bash
# Format code
black lucien/

# Lint code
ruff check lucien/
ruff check --fix lucien/  # Auto-fix issues

# Type check
mypy lucien/

# Run all checks
black lucien/ && ruff check --fix lucien/ && mypy lucien/ && pytest
```

### Testing

- Write tests for all new features
- Aim for 80%+ test coverage
- Use fixtures for common test setup
- Mock external dependencies (LM Studio, file system)

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=lucien --cov-report=html

# Run specific test file
pytest tests/test_config.py

# Run specific test
pytest tests/test_config.py::test_config_defaults
```

### Making Changes

1. **Create a feature branch**

```bash
git checkout -b feature/your-feature-name
```

2. **Make your changes**
   - Write code
   - Add tests
   - Update documentation

3. **Commit your changes**

```bash
git add .
git commit -m "feat: add feature description

Detailed description of changes.
"
```

Use conventional commit messages:
- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation changes
- `test:` - Test changes
- `refactor:` - Code refactoring
- `chore:` - Maintenance tasks

4. **Push and create a pull request**

```bash
git push origin feature/your-feature-name
```

Then create a PR on GitHub.

## OpenSpec Workflow

Lucien uses [OpenSpec](https://openspec.dev/) for specification-driven development.

### When to Create a Spec Proposal

Create a proposal when:
- Adding new features or functionality
- Making breaking changes
- Changing architecture or patterns
- Optimizing performance (changes behavior)
- Updating security patterns

### Creating a Proposal

1. **Check existing specs**

```bash
openspec list
openspec list --specs
```

2. **Create a new change proposal**

```bash
mkdir -p openspec/changes/add-feature-name/{specs/capability}
```

3. **Write proposal files**
   - `proposal.md` - Why, what, impact
   - `tasks.md` - Implementation checklist
   - `specs/capability/spec.md` - Delta changes

4. **Validate**

```bash
openspec validate add-feature-name --strict
```

See `openspec/AGENTS.md` for detailed OpenSpec guidelines.

## Areas for Contribution

### High Priority

1. **Text Extraction (Milestone 2)**
   - Implement Docling integration
   - Add pypdf fallback
   - Implement extraction command

2. **AI Labeling (Milestone 3)**
   - Complete LLM client implementation
   - Prompt engineering and tuning
   - Implement escalation logic

3. **Planning & Materialization (Milestone 4)**
   - Plan generation (JSONL, CSV)
   - Staging mirror creation
   - macOS Finder tag application

### Future Enhancements

- OCR integration (tesseract, OCRmyPDF)
- Embedding-based similarity clustering
- Advanced reranking
- DEVONthink AppleScript automation
- Web UI for plan review

### Documentation

- Installation guides
- Configuration examples
- Workflow tutorials
- API documentation
- Video tutorials

### Testing

- Unit tests for all modules
- Integration tests
- End-to-end tests
- Performance tests

## Issue Reporting

When reporting issues, please include:

1. **Environment**
   - macOS version
   - Python version
   - Lucien version

2. **Steps to reproduce**
   - Command run
   - Configuration used
   - Expected behavior
   - Actual behavior

3. **Logs and errors**
   - Error messages
   - Stack traces
   - Log output

## Questions?

- Open a [GitHub Discussion](https://github.com/jeffmlr/lucien/discussions)
- Open an [Issue](https://github.com/jeffmlr/lucien/issues)
- Contact: github@jeffmlr.net

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
