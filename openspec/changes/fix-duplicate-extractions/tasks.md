# Implementation Tasks

## 1. Database Schema
- [ ] 1.1 Add migration to deduplicate existing extraction records
  - Keep record with MAX(created_at) for each file_id
  - Delete older duplicates
- [ ] 1.2 Add UNIQUE constraint on `extractions(file_id)`
- [ ] 1.3 Update schema version

## 2. Code Changes
- [ ] 2.1 Modify `Database.record_extraction()` to use INSERT OR REPLACE
- [ ] 2.2 Update any queries that assume multiple extractions per file

## 3. Testing
- [ ] 3.1 Verify migration correctly deduplicates
- [ ] 3.2 Verify new extractions replace old ones
- [ ] 3.3 Verify labeling pipeline works with deduplicated data

## Summary
**Total:** 7 tasks
**Estimated complexity:** Low - straightforward schema and query changes
