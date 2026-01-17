# ai-labeling Specification

## Purpose
TBD - created by archiving change add-ai-labeling. Update Purpose after archive.
## Requirements
### Requirement: LM Studio Integration
The system SHALL connect to LM Studio via its OpenAI-compatible API for document labeling.

#### Scenario: Successful connection
- **WHEN** LM Studio is running at the configured base_url
- **THEN** the system establishes a connection and verifies model availability

#### Scenario: LM Studio unavailable
- **WHEN** LM Studio is not running or unreachable
- **THEN** the system displays an actionable error message with setup instructions
- **AND** exits gracefully without corrupting state

#### Scenario: Model not loaded
- **WHEN** LM Studio is running but the configured model is not loaded
- **THEN** the system displays an error identifying the missing model

### Requirement: Document Labeling Output Schema
The system SHALL validate all LLM responses against a strict Pydantic schema.

#### Scenario: Valid JSON response
- **WHEN** the LLM returns valid JSON matching the LabelOutput schema
- **THEN** the system parses and stores all fields in the labels table

#### Scenario: Required fields present
- **WHEN** a document is labeled
- **THEN** the response MUST include: doc_type, title, canonical_filename, suggested_tags, target_group_path, confidence, why

#### Scenario: Optional fields handling
- **WHEN** optional fields (date, issuer, source) are not determinable
- **THEN** the system accepts null values for those fields

#### Scenario: Malformed JSON response
- **WHEN** the LLM returns invalid JSON
- **THEN** the system retries up to max_retries times
- **AND** marks the file as failed if all retries fail

#### Scenario: Schema validation failure
- **WHEN** the LLM returns JSON that fails Pydantic validation
- **THEN** the system logs the validation error details
- **AND** marks the file as failed

### Requirement: Controlled Vocabulary Enforcement
The system SHALL validate doc_type values against a configurable controlled vocabulary.

#### Scenario: Valid doc_type
- **WHEN** the LLM returns a doc_type from the configured vocabulary
- **THEN** the system accepts the value

#### Scenario: Unknown doc_type
- **WHEN** the LLM returns a doc_type not in the vocabulary
- **THEN** the system maps it to "other" and logs a warning

### Requirement: Confidence Scoring
The system SHALL require a confidence score between 0.0 and 1.0 for each label.

#### Scenario: High confidence result
- **WHEN** confidence >= escalation_threshold
- **THEN** the result is stored without escalation

#### Scenario: Low confidence result
- **WHEN** confidence < escalation_threshold
- **THEN** the system triggers model escalation (if not already escalated)

### Requirement: Two-Tier Model Escalation
The system SHALL support escalation from a fast default model to a more capable model.

#### Scenario: Default model sufficient
- **WHEN** the default model produces a high-confidence result
- **AND** no escalation triggers are met
- **THEN** the system stores the result from the default model

#### Scenario: Confidence-based escalation
- **WHEN** the default model returns confidence < escalation_threshold
- **THEN** the system re-processes with the escalation model

#### Scenario: Doc-type-based escalation
- **WHEN** the default model returns a doc_type in escalation_doc_types list
- **THEN** the system re-processes with the escalation model

#### Scenario: Missing-field escalation
- **WHEN** the default model returns null for date AND issuer on document types that typically have these
- **THEN** the system re-processes with the escalation model

#### Scenario: Escalation result stored
- **WHEN** escalation occurs
- **THEN** the final result is stored with escalated=true flag

### Requirement: Context Building for Prompts
The system SHALL build rich context for LLM prompts from file metadata and extracted text.

#### Scenario: Context includes file metadata
- **WHEN** building a labeling prompt
- **THEN** the context includes: filename, parent folder path, MIME type, file size

#### Scenario: Context includes extracted text
- **WHEN** extracted text is available for a file
- **THEN** the context includes the first max_text_chars characters of text

#### Scenario: Text truncation for long documents
- **WHEN** extracted text exceeds max_text_chars
- **THEN** the system truncates to max_text_chars with an indicator

#### Scenario: Context includes vocabularies
- **WHEN** building a labeling prompt
- **THEN** the context includes available doc_types, tags, and taxonomy paths

### Requirement: Prompt Versioning
The system SHALL track prompt versions for reproducibility and auditing.

#### Scenario: Prompt hash recorded
- **WHEN** a labeling result is stored
- **THEN** the prompt_hash field contains a SHA256 hash of the prompt template

#### Scenario: Model name recorded
- **WHEN** a labeling result is stored
- **THEN** the model_name field contains the model identifier used

### Requirement: Label Command CLI
The system SHALL provide a `lucien label` CLI command for batch labeling.

#### Scenario: Basic labeling run
- **WHEN** user runs `lucien label`
- **THEN** the system labels all files with successful extraction but no existing label

#### Scenario: Force re-labeling
- **WHEN** user runs `lucien label --force`
- **THEN** the system re-labels all files regardless of existing labels

#### Scenario: Limited labeling run
- **WHEN** user runs `lucien label --limit N`
- **THEN** the system labels at most N files

#### Scenario: Model override
- **WHEN** user runs `lucien label --model MODEL_NAME`
- **THEN** the system uses the specified model instead of the default

#### Scenario: Disable escalation
- **WHEN** user runs `lucien label --no-escalate`
- **THEN** the system skips escalation even when triggers are met

#### Scenario: Progress display
- **WHEN** labeling is in progress
- **THEN** the system displays a progress bar with current/total count

#### Scenario: Completion statistics
- **WHEN** labeling completes
- **THEN** the system displays counts of: successful, failed, escalated, skipped

### Requirement: Idempotent Labeling
The system SHALL skip files that already have labels unless force mode is enabled.

#### Scenario: Skip already labeled
- **WHEN** running `lucien label` on a file with an existing label
- **THEN** the system skips the file and counts it as skipped

#### Scenario: Re-label with force
- **WHEN** running `lucien label --force` on a file with an existing label
- **THEN** the system creates a new label with a new run_id

#### Scenario: Preserve label history
- **WHEN** a file is re-labeled
- **THEN** previous labels are preserved in the database with their original run_id

### Requirement: Error Handling and Retry
The system SHALL handle transient failures with configurable retry logic.

#### Scenario: API timeout
- **WHEN** the LLM API times out
- **THEN** the system retries with exponential backoff up to max_retries

#### Scenario: Rate limiting
- **WHEN** the API returns a rate limit error
- **THEN** the system waits and retries

#### Scenario: Permanent failure
- **WHEN** all retries are exhausted
- **THEN** the system marks the file as failed with the error message
- **AND** continues processing remaining files

### Requirement: Labeling Run Tracking
The system SHALL track labeling runs for versioning and auditing.

#### Scenario: Run created on start
- **WHEN** `lucien label` starts
- **THEN** a new run record is created with run_type='label' and status='running'

#### Scenario: Run completed on success
- **WHEN** labeling completes successfully
- **THEN** the run record is updated with status='completed' and completed_at timestamp

#### Scenario: Run failed on error
- **WHEN** labeling fails with an unrecoverable error
- **THEN** the run record is updated with status='failed' and error message

### Requirement: Database Label Storage
The system SHALL store labeling results in the labels table with full metadata.

#### Scenario: All fields stored
- **WHEN** a label is stored
- **THEN** it includes: file_id, doc_type, title, canonical_filename, suggested_tags, target_group_path, date, issuer, source, confidence, why, model_name, prompt_hash, labeling_run_id

#### Scenario: Tags stored as JSON
- **WHEN** suggested_tags are stored
- **THEN** they are serialized as a JSON array string

#### Scenario: Unique constraint per run
- **WHEN** storing a label for a file_id in a run
- **THEN** only one label per (file_id, labeling_run_id) is allowed

