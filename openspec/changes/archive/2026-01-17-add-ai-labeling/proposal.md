# Change: Add AI Labeling (Phase 2)

## Why
Phase 1 (text extraction) is complete. Phase 2 (AI labeling) is required to intelligently categorize, title, and tag documents using a local LLM. This is the core intelligence layer that transforms raw extracted text into structured metadata suitable for organizing the document library. Local LLM processing via LM Studio ensures privacy and no cloud dependencies.

## What Changes
- Implement LM Studio client using OpenAI-compatible API (`http://localhost:1234/v1`)
- Create Pydantic schema for strict JSON output validation (LabelOutput)
- Design and implement labeling prompts with context (filename, folders, text excerpts)
- Add `lucien label` CLI command with progress tracking
- Implement two-tier model escalation:
  - Default: Qwen2.5-Instruct-7B (fast, handles most documents)
  - Escalation: Qwen2.5-Instruct-14B for low confidence, sensitive docs, or missing fields
- Store labeling results in `labels` table with full traceability (model name, prompt hash)
- Support resumable labeling (skip already-labeled files)
- Add configurable controlled vocabularies for doc_types and tags

## Impact
- Affected specs: `ai-labeling` (NEW)
- Affected code:
  - `lucien/llm/` package (NEW - LM Studio client, prompts, schemas)
  - `lucien/llm/client.py` (LM Studio API client)
  - `lucien/llm/prompts.py` (prompt templates and construction)
  - `lucien/llm/schemas.py` (Pydantic models for LLM output)
  - `lucien/cli.py` (add `label` command)
  - `lucien/db.py` (add labeling queries, ensure labels table works)
  - `lucien/config.py` (add LLM settings)
- Dependencies:
  - `openai>=1.0.0` (for LM Studio API compatibility)
  - `pydantic>=2.0.0` (already present, for schema validation)
- External:
  - LM Studio running locally with Qwen models loaded
- **NOT BREAKING**: This is a new feature, no breaking changes
