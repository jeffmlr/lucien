# Configuration Specification

## ADDED Requirements

### Requirement: Storage Directory Structure
The system SHALL store all application data in `~/.lucien/` with the following subdirectories:
- `db/` - SQLite database files
- `extracted_text/` - Text extraction sidecars
- `plans/` - Generated materialization plans
- `logs/` - Application log files
- `cache/` - Optional cache files (LLM responses, etc.)

#### Scenario: Fresh installation creates directories
- **WHEN** a user runs any Lucien command for the first time
- **THEN** the system creates `~/.lucien/` and all required subdirectories
- **AND** all subdirectories have appropriate permissions

#### Scenario: Existing directories are preserved
- **WHEN** `~/.lucien/` already exists
- **THEN** the system does not modify existing files or directories
- **AND** only creates missing subdirectories if needed

### Requirement: Database Storage Location
The system SHALL store the SQLite index database at `~/.lucien/db/index.db` by default.

#### Scenario: Database path is configurable
- **WHEN** a user provides a custom `index_db` path in configuration
- **THEN** the system uses the custom path instead of the default
- **AND** the system creates parent directories if needed

#### Scenario: Database file creation
- **WHEN** the database file does not exist
- **THEN** the system creates `~/.lucien/db/index.db` with proper schema
- **AND** the parent directory `~/.lucien/db/` is created if it doesn't exist

### Requirement: Extracted Text Storage Location
The system SHALL store extracted text sidecars in `~/.lucien/extracted_text/` by default.

#### Scenario: Text extraction directory is configurable
- **WHEN** a user provides a custom `extracted_text_dir` path in configuration
- **THEN** the system uses the custom path for storing text sidecars
- **AND** the system creates the directory if it doesn't exist

#### Scenario: Text sidecar organization
- **WHEN** the system extracts text from a file
- **THEN** the text sidecar is stored in `~/.lucien/extracted_text/`
- **AND** the filename is based on the file's SHA256 hash

### Requirement: Plan Storage Location
The system SHALL store generated materialization plans in `~/.lucien/plans/` by default.

#### Scenario: Plans directory is configurable
- **WHEN** a user provides a custom `plans_dir` path in configuration
- **THEN** the system uses the custom path for storing plan files
- **AND** the system creates the directory if it doesn't exist

#### Scenario: Plan files are timestamped
- **WHEN** the system generates a plan
- **THEN** plan files include a timestamp in the filename (e.g., `plan_20260112_143000.jsonl`)
- **AND** files are stored in `~/.lucien/plans/`

### Requirement: Log File Storage Location
The system SHALL store application logs at `~/.lucien/logs/lucien.log` by default.

#### Scenario: Log file path is configurable
- **WHEN** a user provides a custom `log_file` path in configuration
- **THEN** the system writes logs to the custom path
- **AND** the system creates parent directories if needed

#### Scenario: Log file creation
- **WHEN** logging is enabled
- **THEN** the system creates `~/.lucien/logs/lucien.log` if it doesn't exist
- **AND** the parent directory `~/.lucien/logs/` is created if needed

### Requirement: Configuration File Locations
The system SHALL load configuration files in the following precedence order (highest to lowest):
1. `./lucien.yaml` (project-local config)
2. `~/.lucien/config.yaml` (user config, new location)
3. `~/.config/lucien/config.yaml` (XDG user config, legacy location)
4. Environment variables with `LUCIEN_` prefix
5. Built-in defaults

#### Scenario: Project-local config takes precedence
- **WHEN** both `./lucien.yaml` and `~/.lucien/config.yaml` exist
- **THEN** the system loads `./lucien.yaml` first
- **AND** settings from `./lucien.yaml` override `~/.lucien/config.yaml`

#### Scenario: User config in new location
- **WHEN** `~/.lucien/config.yaml` exists but `./lucien.yaml` does not
- **THEN** the system loads configuration from `~/.lucien/config.yaml`
- **AND** applies environment variable overrides

#### Scenario: Legacy XDG config compatibility
- **WHEN** only `~/.config/lucien/config.yaml` exists
- **THEN** the system loads configuration from the XDG location
- **AND** the system continues to work without migration

#### Scenario: Environment variable overrides
- **WHEN** environment variables with `LUCIEN_` prefix are set
- **THEN** they override all file-based configuration
- **AND** nested settings use `__` delimiter (e.g., `LUCIEN_LLM__BASE_URL`)

### Requirement: Directory Creation
The system SHALL automatically create all required directories when missing.

#### Scenario: Automatic directory creation on first run
- **WHEN** a user runs any Lucien command
- **AND** `~/.lucien/` or its subdirectories do not exist
- **THEN** the system creates all required directories
- **AND** the operation succeeds without manual intervention

#### Scenario: Parent directory creation
- **WHEN** a config specifies a path with non-existent parent directories
- **THEN** the system creates all parent directories recursively
- **AND** the operation does not fail due to missing directories

### Requirement: Path Expansion
The system SHALL expand user home directory (`~`) and environment variables in all configured paths.

#### Scenario: Tilde expansion in paths
- **WHEN** a configuration path contains `~`
- **THEN** the system expands it to the user's home directory
- **AND** the expanded path is used for all operations

#### Scenario: Environment variable expansion
- **WHEN** a configuration path contains environment variables (e.g., `$HOME`)
- **THEN** the system expands them to their values
- **AND** the operation uses the expanded path
