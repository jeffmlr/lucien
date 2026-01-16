# text-extraction Specification

## Purpose
TBD - created by archiving change add-text-extraction. Update Purpose after archive.
## Requirements
### Requirement: Text Extraction from Multiple File Types
The system SHALL extract text from PDFs, Office documents (.docx, .xlsx, .pptx), and plain text files (.txt, .md, .rst, .log).

#### Scenario: PDF text extraction
- **WHEN** a PDF file is provided for extraction
- **THEN** the system extracts text content using Docling or pypdf
- **AND** the extracted text is stored as a sidecar file

#### Scenario: Office document text extraction
- **WHEN** a .docx, .xlsx, or .pptx file is provided
- **THEN** the system extracts text content using Docling
- **AND** tables and structured content are preserved in extracted text

#### Scenario: Plain text file extraction
- **WHEN** a .txt, .md, .rst, or .log file is provided
- **THEN** the system reads the file content with appropriate encoding detection
- **AND** the text is stored as a sidecar file

### Requirement: Multi-Backend Extraction with Fallback
The system SHALL attempt extraction using multiple backends in priority order, falling back to the next backend if extraction fails.

#### Scenario: Primary extractor succeeds
- **WHEN** Docling successfully extracts text from a PDF
- **THEN** the system uses Docling's output
- **AND** no fallback extractors are attempted

#### Scenario: Primary extractor fails, fallback succeeds
- **WHEN** Docling fails to extract text from a PDF
- **THEN** the system attempts extraction using pypdf
- **AND** pypdf's output is used if successful

#### Scenario: All extractors fail
- **WHEN** all configured extractors fail for a file
- **THEN** the system records extraction status as "failed"
- **AND** the error message indicates which extractors were attempted
- **AND** the pipeline continues with remaining files

### Requirement: Hash-Based Sidecar Storage with Compression
The system SHALL store extracted text as compressed sidecar files in `~/.lucien/extracted_text/` using SHA256 hash as the filename with `.txt.gz` extension.

#### Scenario: Sidecar filename generation
- **WHEN** text is extracted from a file with SHA256 hash `abc123def456...`
- **THEN** the sidecar is stored as `~/.lucien/extracted_text/abc123def456....txt.gz`
- **AND** the filename is deterministic based on file content
- **AND** the text is compressed using gzip to reduce storage

#### Scenario: Duplicate file deduplication
- **WHEN** two files with identical content (same SHA256) are extracted
- **THEN** only one compressed sidecar file is created
- **AND** both file records reference the same sidecar path
- **AND** storage savings from both deduplication and compression are realized

#### Scenario: Sidecar directory creation
- **WHEN** `~/.lucien/extracted_text/` does not exist
- **THEN** the system creates the directory automatically
- **AND** extraction proceeds without error

#### Scenario: Compressed text reading
- **WHEN** the system needs to read extracted text for processing
- **THEN** the compressed sidecar is transparently decompressed
- **AND** the original text content is returned
- **AND** compression/decompression is transparent to consumers

### Requirement: Extraction Metadata Recording
The system SHALL record extraction results in the `extractions` database table with status, method, output path, and error information.

#### Scenario: Successful extraction recording
- **WHEN** text extraction succeeds
- **THEN** the system creates an extraction record with status "success"
- **AND** the record includes extraction method (e.g., "docling", "pypdf", "text")
- **AND** the record includes the output sidecar path
- **AND** the record is linked to the current extraction run

#### Scenario: Failed extraction recording
- **WHEN** text extraction fails for a file
- **THEN** the system creates an extraction record with status "failed"
- **AND** the record includes the error message
- **AND** the record indicates which extraction method(s) were attempted

#### Scenario: Skipped file recording
- **WHEN** a file is skipped (e.g., unsupported extension)
- **THEN** the system creates an extraction record with status "skipped"
- **AND** the record includes the reason for skipping

### Requirement: Idempotent Extraction
The system SHALL skip files that have already been successfully extracted in a previous run.

#### Scenario: Skip already-extracted files
- **WHEN** extraction is run on a file that has a successful extraction record
- **THEN** the system skips re-extraction
- **AND** the existing sidecar file is preserved
- **AND** a message indicates the file was skipped

#### Scenario: Re-extract with force flag
- **WHEN** extraction is run with `--force` flag
- **THEN** the system re-extracts all files regardless of existing records
- **AND** new extraction records are created for the current run
- **AND** existing sidecars are overwritten

#### Scenario: Re-extract failed files
- **WHEN** extraction is run on a file with a previous "failed" status
- **THEN** the system attempts extraction again
- **AND** the new result is recorded for the current run

### Requirement: CLI Extract Command
The system SHALL provide a `lucien extract` command to run text extraction on indexed files.

#### Scenario: Extract all files
- **WHEN** user runs `lucien extract`
- **THEN** the system extracts text from all indexed files
- **AND** a progress bar shows extraction progress
- **AND** statistics are displayed: successful, failed, skipped counts

#### Scenario: Extract with force flag
- **WHEN** user runs `lucien extract --force`
- **THEN** the system re-extracts all files including previously successful ones
- **AND** existing extraction records are preserved (new run ID)

#### Scenario: Extract with method override
- **WHEN** user runs `lucien extract --method pypdf`
- **THEN** the system uses only the pypdf extractor
- **AND** fallback to other extractors is disabled

#### Scenario: Extract with limit
- **WHEN** user runs `lucien extract --limit 100`
- **THEN** the system extracts text from at most 100 files
- **AND** this is useful for testing on a subset

### Requirement: Configurable File Type Filtering
The system SHALL skip extraction for files matching configured `skip_extensions`.

#### Scenario: Skip configured extensions
- **WHEN** a file has extension in the skip_extensions list (e.g., .jpg, .png, .mp4)
- **THEN** the system skips extraction
- **AND** an extraction record with status "skipped" is created
- **AND** the reason "Extension in skip list" is recorded

#### Scenario: Process non-skipped extensions
- **WHEN** a file has extension not in the skip_extensions list
- **THEN** the system attempts extraction
- **AND** the appropriate extractor is selected based on file type

### Requirement: Text Truncation for Large Documents
The system SHALL truncate extracted text to `max_text_length` characters while preserving beginning and end content.

#### Scenario: Small document no truncation
- **WHEN** extracted text is less than max_text_length (default: 50,000 chars)
- **THEN** the system stores the complete text
- **AND** no truncation marker is added

#### Scenario: Large document truncation
- **WHEN** extracted text exceeds max_text_length
- **THEN** the system keeps the first half of max_text_length
- **AND** the system keeps the last half of max_text_length
- **AND** a truncation marker "[... truncated ...]" is inserted between sections

#### Scenario: Truncation preserves document structure
- **WHEN** a large document is truncated
- **THEN** the beginning (first pages) is preserved for title/header extraction
- **AND** the end (last pages) is preserved for signatures/dates
- **AND** the middle portion is omitted

### Requirement: Encoding Detection for Text Files
The system SHALL detect and handle multiple text encodings (UTF-8, UTF-16, Latin-1, etc.) when extracting plain text files.

#### Scenario: UTF-8 text file
- **WHEN** a text file is encoded in UTF-8
- **THEN** the system reads the file correctly
- **AND** special characters are preserved

#### Scenario: Non-UTF-8 encoding detection
- **WHEN** a text file is encoded in UTF-16 or Latin-1
- **THEN** the system detects the encoding automatically
- **AND** the file is decoded correctly
- **AND** the text is stored in UTF-8 format

#### Scenario: Encoding detection failure fallback
- **WHEN** encoding detection fails
- **THEN** the system attempts to read as UTF-8 with error replacement
- **AND** extraction succeeds with possible character substitutions
- **AND** a warning is logged about encoding issues

### Requirement: Graceful Error Handling
The system SHALL handle extraction failures gracefully without stopping the pipeline.

#### Scenario: Corrupted file handling
- **WHEN** a PDF file is corrupted or malformed
- **THEN** the extraction fails gracefully
- **AND** an error message is recorded in the database
- **AND** extraction continues with the next file

#### Scenario: Encrypted PDF handling
- **WHEN** a PDF file is password-protected
- **THEN** the system records extraction status as "failed"
- **AND** the error message indicates "Encrypted PDF"
- **AND** extraction continues with the next file

#### Scenario: Permission denied handling
- **WHEN** a file is not readable due to permissions
- **THEN** the system records extraction status as "failed"
- **AND** the error message indicates "Permission denied"
- **AND** extraction continues with the next file

#### Scenario: Disk space error handling
- **WHEN** disk space is insufficient to write sidecar
- **THEN** the extraction fails with clear error message
- **AND** the error is recorded in the database
- **AND** the user is notified about disk space issues

### Requirement: Progress Reporting
The system SHALL display real-time progress during extraction operations.

#### Scenario: Progress bar display
- **WHEN** extraction is running
- **THEN** a progress bar shows percentage complete
- **AND** the current file being processed is displayed
- **AND** elapsed time and estimated remaining time are shown

#### Scenario: Extraction statistics display
- **WHEN** extraction completes
- **THEN** the system displays total files processed
- **AND** the system displays counts: successful, failed, skipped
- **AND** the system displays total extraction time

### Requirement: Extraction Run Tracking
The system SHALL track each extraction run with a unique run ID and link extraction records to the run.

#### Scenario: New extraction run creation
- **WHEN** `lucien extract` is invoked
- **THEN** a new run record is created with type "extract"
- **AND** all extraction records reference this run ID
- **AND** the run start time is recorded

#### Scenario: Extraction run completion
- **WHEN** extraction completes successfully
- **THEN** the run status is updated to "completed"
- **AND** the run completion time is recorded
- **AND** run statistics are available via `lucien stats`

#### Scenario: Extraction run failure
- **WHEN** extraction is interrupted or fails
- **THEN** the run status is set to "failed"
- **AND** the error message is recorded
- **AND** partial results are preserved in the database

### Requirement: Optional Dependencies with Graceful Degradation
The system SHALL function with a subset of extractors when optional dependencies are not installed.

#### Scenario: All extractors available
- **WHEN** docling, pypdf, and python-magic are installed
- **THEN** all extraction backends are available
- **AND** the full fallback chain is used

#### Scenario: Docling not installed
- **WHEN** docling is not installed but pypdf is available
- **THEN** the system uses pypdf for PDF extraction
- **AND** a warning is logged that Docling is not available
- **AND** extraction proceeds with reduced capabilities

#### Scenario: No optional extractors installed
- **WHEN** only built-in Python libraries are available
- **THEN** the system only supports plain text file extraction
- **AND** an error message suggests installing extraction dependencies
- **AND** PDF and Office documents are skipped

### Requirement: Metadata Extraction from PDFs
The system SHALL extract PDF metadata (title, author, creation date) when available and store it with extraction results.

#### Scenario: PDF with metadata
- **WHEN** a PDF contains title and author metadata
- **THEN** the system extracts the metadata
- **AND** metadata is stored in the extraction record's metadata field
- **AND** metadata is available for use in AI labeling

#### Scenario: PDF without metadata
- **WHEN** a PDF has no metadata
- **THEN** extraction succeeds with text only
- **AND** metadata field is empty or null
- **AND** extraction is not considered failed

