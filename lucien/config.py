"""
Configuration management using Pydantic Settings.

Loads configuration from:
1. ~/.config/lucien/config.yaml (user config)
2. ./lucien.yaml (project-local config)
3. Environment variables (override)
"""

import os
from pathlib import Path
from typing import List, Optional

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMSettings(BaseModel):
    """LLM configuration for LM Studio."""

    base_url: str = Field(default="http://localhost:1234/v1", description="LM Studio API base URL")
    default_model: str = Field(default="qwen2.5-7b-instruct", description="Default model for labeling")
    escalation_model: str = Field(default="qwen2.5-14b-instruct", description="Escalation model for complex docs")
    escalation_threshold: float = Field(default=0.7, ge=0.0, le=1.0, description="Confidence threshold for escalation")
    escalation_doc_types: List[str] = Field(
        default_factory=lambda: ["taxes", "medical", "legal", "insurance"],
        description="Doc types that always use escalation model"
    )
    max_retries: int = Field(default=3, description="Maximum retry attempts for LLM calls")
    timeout: int = Field(default=120, description="Timeout in seconds for LLM calls")


class ExtractionSettings(BaseModel):
    """Text extraction configuration."""

    skip_extensions: List[str] = Field(
        default_factory=lambda: [".jpg", ".jpeg", ".png", ".gif", ".mp4", ".mov", ".zip", ".tar", ".gz"],
        description="File extensions to skip during extraction"
    )
    methods: List[str] = Field(
        default_factory=lambda: ["docling", "pypdf", "textract"],
        description="Extraction methods to try in order"
    )
    max_text_length: int = Field(default=50000, description="Maximum text length to extract (chars)")


class TaxonomySettings(BaseModel):
    """Taxonomy and categorization configuration."""

    top_level: List[str] = Field(
        default_factory=lambda: [
            "01 Identity & Legal",
            "02 Medical",
            "03 Financial",
            "04 Taxes",
            "05 Insurance",
            "06 Home",
            "07 Vehicles",
            "08 Work & Retirement",
            "09 Travel",
            "10 Family Photos & Media",
            "98 Uncategorized",
            "99 Needs Review",
        ],
        description="Top-level taxonomy folders"
    )


class NamingSettings(BaseModel):
    """Canonical filename naming configuration."""

    format: str = Field(default="YYYY-MM-DD__Domain__Issuer__Title", description="Filename format template")
    separator: str = Field(default="__", description="Field separator in filenames")
    date_format: str = Field(default="%Y-%m-%d", description="Date format (strftime)")


class ScanSettings(BaseModel):
    """Filesystem scanning configuration."""

    skip_dirs: List[str] = Field(
        default_factory=lambda: [".git", ".cache", "__pycache__", "node_modules", ".DS_Store", ".Trash"],
        description="Directory names to skip during scanning"
    )
    follow_symlinks: bool = Field(default=False, description="Whether to follow symlinks")
    hash_algorithm: str = Field(default="sha256", description="Hash algorithm for file integrity")


class MaterializeSettings(BaseModel):
    """Staging mirror materialization configuration."""

    default_mode: str = Field(default="hardlink", description="Default mode: 'copy' or 'hardlink'")
    apply_tags: bool = Field(default=True, description="Apply macOS Finder tags")
    create_dirs: bool = Field(default=True, description="Automatically create target directories")


class LucienSettings(BaseSettings):
    """Main Lucien configuration."""

    model_config = SettingsConfigDict(
        env_prefix="LUCIEN_",
        env_nested_delimiter="__",
        case_sensitive=False,
    )

    # Core paths
    source_root: Optional[Path] = Field(default=None, description="Root path to source backup (immutable)")
    index_db: Path = Field(
        default_factory=lambda: Path.home() / ".local/share/lucien/index.db",
        description="SQLite database path"
    )
    extracted_text_dir: Path = Field(
        default_factory=lambda: Path.home() / ".local/share/lucien/extracted_text",
        description="Directory for extracted text sidecars"
    )
    staging_root: Path = Field(
        default_factory=lambda: Path.home() / "Documents/Lucien-Staging",
        description="Staging mirror root directory"
    )

    # Subsystem settings
    llm: LLMSettings = Field(default_factory=LLMSettings)
    extraction: ExtractionSettings = Field(default_factory=ExtractionSettings)
    taxonomy: TaxonomySettings = Field(default_factory=TaxonomySettings)
    naming: NamingSettings = Field(default_factory=NamingSettings)
    scan: ScanSettings = Field(default_factory=ScanSettings)
    materialize: MaterializeSettings = Field(default_factory=MaterializeSettings)

    # Controlled vocabularies
    doc_types: List[str] = Field(
        default_factory=lambda: [
            "identity", "legal", "contract", "deed", "will",
            "medical", "prescription", "lab_result", "insurance_eob",
            "financial", "bank_statement", "investment", "receipt",
            "tax", "w2", "1099", "1040",
            "insurance", "policy", "claim",
            "home", "mortgage", "utility", "repair",
            "vehicle", "registration", "maintenance",
            "work", "payslip", "401k", "retirement",
            "travel", "passport", "visa", "itinerary", "booking",
            "photo", "video", "media",
            "other", "uncategorized",
        ],
        description="Controlled vocabulary for document types"
    )

    tags: List[str] = Field(
        default_factory=lambda: [
            "important", "action-required", "archived",
            "tax-deductible", "warranty", "recurring",
        ],
        description="Suggested tags vocabulary (user-extendable)"
    )

    # Logging
    log_level: str = Field(default="INFO", description="Logging level")
    log_file: Optional[Path] = Field(default=None, description="Optional log file path")

    def ensure_directories(self) -> None:
        """Ensure all required directories exist."""
        self.index_db.parent.mkdir(parents=True, exist_ok=True)
        self.extracted_text_dir.mkdir(parents=True, exist_ok=True)
        self.staging_root.mkdir(parents=True, exist_ok=True)

    @classmethod
    def load_from_yaml(cls, yaml_path: Path) -> "LucienSettings":
        """Load configuration from YAML file."""
        if not yaml_path.exists():
            raise FileNotFoundError(f"Config file not found: {yaml_path}")

        with open(yaml_path) as f:
            config_dict = yaml.safe_load(f)

        return cls(**config_dict)

    @classmethod
    def load(cls) -> "LucienSettings":
        """
        Load configuration with precedence:
        1. Project-local ./lucien.yaml
        2. User config ~/.config/lucien/config.yaml
        3. Environment variables
        4. Defaults
        """
        # Start with defaults
        config = cls()

        # Try user config
        user_config = Path.home() / ".config/lucien/config.yaml"
        if user_config.exists():
            config = cls.load_from_yaml(user_config)

        # Override with project-local config
        local_config = Path.cwd() / "lucien.yaml"
        if local_config.exists():
            local_dict = {}
            with open(local_config) as f:
                local_dict = yaml.safe_load(f)
            # Merge with existing config (env vars already applied)
            config = cls(**{**config.model_dump(), **local_dict})

        return config

    def save_to_yaml(self, yaml_path: Path) -> None:
        """Save current configuration to YAML file."""
        yaml_path.parent.mkdir(parents=True, exist_ok=True)
        with open(yaml_path, "w") as f:
            yaml.dump(
                self.model_dump(mode="json", exclude_none=True),
                f,
                default_flow_style=False,
                sort_keys=False,
            )


def get_config() -> LucienSettings:
    """Convenience function to get current configuration."""
    return LucienSettings.load()
