# Implementation Tasks

## 1. Update Configuration Defaults
- [x] 1.1 Update `index_db` default in `lucien/config.py` from `~/.local/share/lucien/index.db` to `~/.lucien/db/index.db`
- [x] 1.2 Update `extracted_text_dir` default in `lucien/config.py` from `~/.local/share/lucien/extracted_text` to `~/.lucien/extracted_text/`
- [x] 1.3 Add `plans_dir` field to `LucienSettings` with default `~/.lucien/plans/`
- [x] 1.4 Add `cache_dir` field to `LucienSettings` with default `~/.lucien/cache/` (for future use)
- [x] 1.5 Update `log_file` default from `null` to `~/.lucien/logs/lucien.log`
- [x] 1.6 Update `ensure_directories()` method to create new directories: `plans_dir`, `cache_dir`, and log directory

## 2. Update Configuration Loading
- [x] 2.1 Update `LucienSettings.load()` to check `~/.lucien/config.yaml` before `~/.config/lucien/config.yaml`
- [x] 2.2 Update precedence order documentation in `config.py` docstring

## 3. Update Example Configuration
- [x] 3.1 Update all paths in `lucien.example.yaml` to use `~/.lucien/` prefix
- [x] 3.2 Add `plans_dir` and `cache_dir` to example config with comments
- [x] 3.3 Update log_file example to show `~/.lucien/logs/lucien.log`

## 4. Update Documentation
- [x] 4.1 Update `README.md` architecture diagram and paths
- [x] 4.2 Update `README.md` configuration section
- [x] 4.3 Update `QUICKSTART.md` example paths
- [x] 4.4 Update `openspec/project.md` to reflect new storage structure
- [x] 4.5 Add directory structure documentation showing `~/.lucien/` layout

## 5. Update CLI Commands
- [x] 5.1 Update `cli.py` to use new `plans_dir` when plan generation is implemented
- [x] 5.2 Verify all CLI commands use config paths correctly

## 6. Testing
- [x] 6.1 Test config loading with new paths
- [x] 6.2 Test `ensure_directories()` creates all required directories
- [x] 6.3 Test backward compatibility with `~/.config/lucien/config.yaml`
- [x] 6.4 Test config precedence order
- [x] 6.5 Verify existing scan/stats commands work with new paths
