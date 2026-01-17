# Design: AI Labeling (Phase 2)

## Context

Phase 2 adds AI-powered document labeling using a local LLM via LM Studio. This is the intelligence layer that transforms raw extracted text into structured metadata for library organization. Key constraints:

- **Local-only**: No cloud LLM APIs; all processing via LM Studio
- **Deterministic output**: Strict JSON schema validation
- **Auditability**: Full traceability of model, prompt version, and confidence
- **Graceful degradation**: Handle LLM failures without data loss

## Goals / Non-Goals

**Goals:**
- Accurate document classification using local LLM
- Structured output with strict schema validation
- Two-tier model escalation for difficult documents
- Configurable controlled vocabularies
- Full traceability for debugging and auditing
- Resumable/idempotent labeling

**Non-Goals:**
- Cloud LLM support (explicitly excluded)
- Real-time labeling (batch processing only)
- Embedding-based similarity (deferred to future phase)
- Multi-language support (English-first for v0.3)

## Decisions

### Decision 1: Use OpenAI SDK for LM Studio

**What**: Use the official OpenAI Python SDK to communicate with LM Studio.

**Why**: LM Studio exposes an OpenAI-compatible API at `/v1/chat/completions`. Using the standard SDK:
- Reduces custom code
- Provides battle-tested retry/timeout handling
- Makes future model switching easier
- Well-documented and maintained

**Alternative considered**: Custom HTTP client with requests. Rejected because it duplicates SDK functionality.

### Decision 2: Pydantic for Output Validation

**What**: Define `LabelOutput` as a Pydantic model and validate all LLM responses against it.

**Why**:
- Catches malformed JSON immediately
- Provides clear error messages for debugging
- Enables field-level validation (date format, confidence range)
- Integrates well with existing Lucien codebase

**Schema**:
```python
class LabelOutput(BaseModel):
    doc_type: str                    # From controlled vocabulary
    title: str                       # Human-readable title
    canonical_filename: str          # Suggested filename
    suggested_tags: List[str]        # Tags for Finder/DT
    target_group_path: str           # Taxonomy path
    date: Optional[str]              # ISO format YYYY-MM-DD
    issuer: Optional[str]            # Who issued the document
    source: Optional[str]            # Where it came from
    confidence: float                # 0.0 to 1.0
    why: str                         # 1-2 sentence explanation
```

### Decision 3: Two-Tier Model Escalation

**What**: Use 7B model by default, escalate to 14B for complex cases.

**Why**:
- 7B is faster and handles 80%+ of documents well
- 14B provides better accuracy for edge cases
- Configurable threshold allows tuning based on results

**Escalation triggers** (configurable):
1. `confidence < 0.7` on first pass
2. `doc_type` in sensitive list: `[taxes, medical, legal, insurance]`
3. Missing critical fields: `date` or `issuer` is null

**Flow**:
```
Document → 7B Model → Check triggers
                    ↓
              No triggers? → Store result
              Triggers? → 14B Model → Store result (with escalation flag)
```

### Decision 4: Prompt Structure

**What**: System prompt + user prompt with structured context.

**System prompt** (role and format):
```
You are a document classification assistant. Analyze the provided document
and return a JSON object with the specified fields. Be precise and concise.
Output ONLY valid JSON, no explanations.
```

**User prompt** (context injection):
```
Classify this document:

FILENAME: {filename}
PATH: {parent_folders}
FILE TYPE: {mime_type}
FILE SIZE: {size_bytes} bytes

AVAILABLE DOC TYPES: {doc_types_list}
AVAILABLE TAGS: {tags_list}
TAXONOMY: {taxonomy_list}

DOCUMENT TEXT (first {max_chars} characters):
---
{extracted_text}
---

Return JSON with: doc_type, title, canonical_filename, suggested_tags,
target_group_path, date (YYYY-MM-DD or null), issuer, source,
confidence (0.0-1.0), why (1-2 sentences).
```

### Decision 5: Prompt Versioning

**What**: Hash the complete prompt template and store with each label result.

**Why**:
- Enables reproduction of labeling decisions
- Allows A/B testing of prompt changes
- Required for debugging hallucinations

**Implementation**: SHA256 of system prompt + user prompt template (before variable substitution).

### Decision 6: Text Truncation Strategy

**What**: Send first N characters of extracted text (default: 8000), with option to include key sections.

**Why**:
- Most identifying information is in the first few pages
- Keeps prompt size manageable for context windows
- Reduces API latency

**Future enhancement**: Extract key sections (headers, dates, amounts) rather than just first N chars.

## Package Structure

```
lucien/llm/
├── __init__.py          # Package exports
├── client.py            # LMStudioClient class
├── prompts.py           # Prompt templates and builders
├── schemas.py           # Pydantic models (LabelOutput, LabelingContext)
└── pipeline.py          # LabelingPipeline orchestration
```

## Risks / Trade-offs

### Risk: LLM Hallucination
- **Impact**: Incorrect dates, wrong doc_types, bad filenames
- **Mitigation**:
  - Strict schema validation catches structural errors
  - Confidence score flags uncertain results
  - Human review phase (Phase 3) catches semantic errors
  - Audit trail enables correction

### Risk: LM Studio Unavailable
- **Impact**: Labeling phase fails completely
- **Mitigation**:
  - Clear error message with setup instructions
  - Health check before starting batch
  - Graceful failure (no partial state corruption)

### Risk: Slow Labeling (Large Libraries)
- **Impact**: Hours to label 10K+ documents
- **Mitigation**:
  - Progress bar shows ETA
  - Resumable (skip already-labeled)
  - Limit flag for testing
  - Future: Parallel workers (carefully, to not overload LM Studio)

### Risk: Inconsistent JSON from LLM
- **Impact**: Schema validation failures
- **Mitigation**:
  - Strong prompt with format examples
  - JSON mode if LM Studio supports it
  - Retry on parse failure (up to 3 times)
  - Log raw response for debugging

## Configuration Schema

```yaml
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
  max_text_chars: 8000
  timeout_seconds: 120
  max_retries: 3

# Controlled vocabularies
doc_types:
  - identity
  - legal
  - contract
  - medical
  - financial
  - bank_statement
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
```

## Migration Plan

No migration needed - this is a new feature. The `labels` table already exists in the schema from Phase 0.

## Open Questions

1. **Batch vs streaming API**: Should we use streaming for progress feedback on slow models?
   - *Recommendation*: Start with non-streaming; add streaming if UX demands it.

2. **Parallel workers**: Can we safely run multiple labeling workers?
   - *Recommendation*: Start single-threaded; LM Studio may not handle concurrent requests well.

3. **JSON mode**: Does LM Studio support `response_format: { type: "json_object" }`?
   - *Action*: Test with LM Studio; use if available for more reliable JSON output.
