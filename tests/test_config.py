"""
Tests for configuration management.
"""

import pytest
from pathlib import Path
from lucien.config import LucienSettings, LLMSettings


def test_config_defaults():
    """Test that default configuration loads correctly."""
    config = LucienSettings()

    # Check defaults
    assert config.llm.base_url == "http://localhost:1234/v1"
    assert config.llm.default_model == "qwen2.5-7b-instruct"
    assert config.llm.escalation_threshold == 0.7
    assert config.scan.hash_algorithm == "sha256"


def test_config_llm_settings():
    """Test LLM settings."""
    config = LucienSettings()
    assert config.llm.base_url == "http://localhost:1234/v1"
    assert config.llm.default_model == "qwen2.5-7b-instruct"
    assert config.llm.escalation_threshold == 0.7


def test_config_taxonomies():
    """Test that default taxonomies are loaded."""
    from lucien.config import LucienSettings

    config = LucienSettings()
    assert len(config.taxonomy.top_level) > 0
    assert "01 Identity & Legal" in config.taxonomy.top_level
    assert len(config.doc_types) > 0
    assert "financial" in config.doc_types


def test_database_init(tmp_path):
    """Test database initialization."""
    from lucien.db import Database

    db_path = tmp_path / "test.db"
    db = Database(db_path)

    # Check that schema was created
    assert db.db_path.exists()

    # Get stats (should be empty)
    stats = db.get_stats()
    assert stats["total_files"] == 0
    assert stats["total_runs"] == 0


def test_scanner_skip_dirs():
    """Test that scanner correctly identifies directories to skip."""
    from lucien.scanner import FileScanner
    from lucien.config import LucienSettings
    from lucien.db import Database
    from pathlib import Path

    config = LucienSettings()
    db = Database(":memory:")  # In-memory database for testing
    scanner = FileScanner(config, db)

    # Test skip directory logic
    assert scanner.should_skip_directory(Path(".git"))
    assert scanner.should_skip_directory(Path("__pycache__"))
    assert not scanner.should_skip_directory(Path("Documents"))
