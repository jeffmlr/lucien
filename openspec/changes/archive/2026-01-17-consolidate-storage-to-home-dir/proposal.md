# Change: Consolidate Storage to ~/.lucien

## Why
Lucien currently stores data in `~/.local/share/lucien/` and configuration in `~/.config/lucien/`, following XDG Base Directory conventions. However, for a Mac-first application with a small, focused set of data files, consolidating all storage to `~/.lucien/` provides a simpler, more discoverable structure that aligns with Mac user expectations (similar to `~/.ssh`, `~/.aws`, `~/.docker`). This also provides a single location for all Lucien-related files, making backup, inspection, and cleanup easier.

## What Changes
- Change default database path from `~/.local/share/lucien/index.db` to `~/.lucien/db/index.db`
- Change default extracted text directory from `~/.local/share/lucien/extracted_text` to `~/.lucien/extracted_text/`
- Add new `plans_dir` configuration field with default `~/.lucien/plans/` for generated plan files
- Add new `cache_dir` configuration field with default `~/.lucien/cache/` for future caching (LLM responses, etc.)
- Update default log file path from `null` to `~/.lucien/logs/lucien.log`
- Support optional user configuration at `~/.lucien/config.yaml` in addition to `~/.config/lucien/config.yaml`
- Update all documentation, examples, and defaults to reflect new paths
- Staging root remains at `~/Documents/Lucien-Staging` (unchanged - this is user-visible working data)

## Impact
- Affected specs: `configuration`
- Affected code:
  - `lucien/config.py` (path defaults and ensure_directories method)
  - `lucien.example.yaml` (example configuration)
  - `README.md` (documentation)
  - `openspec/project.md` (project documentation)
  - `QUICKSTART.md` (quick start guide)
- **BREAKING**: Users with existing data in `~/.local/share/lucien/` will need to migrate
  - Mitigation: Project is in alpha (v0.1) with no public users yet
  - Future: Add migration helper command if needed
- Config file locations checked in order:
  1. `./lucien.yaml` (project-local, highest priority)
  2. `~/.lucien/config.yaml` (new location, convenient)
  3. `~/.config/lucien/config.yaml` (XDG location, for compatibility)
  4. Environment variables (override)
  5. Defaults (fallback)
