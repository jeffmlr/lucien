# Change: Fix Duplicate Extraction Records

## Why
The `extractions` table can accumulate multiple records for the same `file_id` when extraction is run multiple times. This causes:

1. **Duplicate processing**: Queries joining files to extractions return multiple rows per file, causing the labeling pipeline to process the same file multiple times
2. **Wasted storage**: Multiple extraction outputs stored for the same file
3. **Confusion**: Unclear which extraction result is authoritative

Currently observed: Files with up to 9 duplicate extraction records.

## What Changes
- Modify extraction recording to use UPSERT (INSERT OR REPLACE) semantics
- Keep only the latest extraction per file_id
- Add unique constraint on `extractions(file_id)` to prevent future duplicates
- Migration to deduplicate existing records (keep most recent by `created_at`)

## Impact
- Affected code:
  - `lucien/db.py`: `record_extraction()` method - change to UPSERT
  - Migration script to clean up existing duplicates
- Schema change: Add `UNIQUE` constraint on `file_id` column
- **NOT BREAKING**: Existing queries will work, just return fewer (correct) rows

## Alternatives Considered
1. **Keep all extraction history**: More complex, requires versioning logic everywhere
2. **Soft delete old extractions**: Adds complexity without clear benefit
3. **UPSERT approach** (chosen): Simple, matches intent that each file has one authoritative extraction
