"""
Integration tests for the labeling pipeline.

Tests the LabelingPipeline class with mocked LLM responses.
"""

import gzip
import json
import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from lucien.config import LucienSettings
from lucien.db import Database, FileRecord
from lucien.llm.pipeline import LabelingPipeline
from lucien.llm.models import LabelOutput


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def config():
    """Create test configuration."""
    return LucienSettings()


@pytest.fixture
def temp_db(tmp_path):
    """Create a temporary database."""
    db_path = tmp_path / "test.db"
    return Database(db_path)


@pytest.fixture
def mock_llm_client():
    """Create a mocked LLM client."""
    with patch('lucien.llm.pipeline.LLMClient') as mock:
        yield mock


@pytest.fixture
def sample_label_output():
    """Sample LabelOutput for mocking."""
    return LabelOutput(
        doc_type="financial",
        title="Chase Bank Statement - March 2024",
        canonical_filename="2024-03-15-Financial-Chase_Bank-Statement",
        suggested_tags=["finances", "statement", "chase"],
        target_group_path="03 Financial/Bank Statements",
        date="2024-03-15",
        issuer="Chase Bank",
        confidence=0.92,
        why="Bank statement with clear account information and transaction history",
    )


# =============================================================================
# Pipeline Initialization Tests
# =============================================================================

class TestPipelineInitialization:
    """Tests for pipeline initialization."""

    def test_pipeline_init(self, config, temp_db, mock_llm_client):
        """Test pipeline initializes correctly."""
        pipeline = LabelingPipeline(config, temp_db)

        assert pipeline.config == config
        assert pipeline.database == temp_db
        mock_llm_client.assert_called_once_with(config)

    def test_pipeline_prompt_version(self, config, temp_db, mock_llm_client):
        """Test that pipeline has a prompt version."""
        pipeline = LabelingPipeline(config, temp_db)

        assert pipeline.prompt_version is not None
        assert len(pipeline.prompt_version) == 16


# =============================================================================
# Text Reading Tests
# =============================================================================

class TestTextReading:
    """Tests for reading extracted text from sidecar files."""

    def test_read_plain_text(self, config, temp_db, mock_llm_client, tmp_path):
        """Test reading plain text extraction file."""
        pipeline = LabelingPipeline(config, temp_db)

        # Create a plain text file
        text_file = tmp_path / "extracted.txt"
        text_file.write_text("This is extracted text content.")

        result = pipeline._read_extracted_text(str(text_file))
        assert result == "This is extracted text content."

    def test_read_gzipped_text(self, config, temp_db, mock_llm_client, tmp_path):
        """Test reading gzipped extraction file."""
        pipeline = LabelingPipeline(config, temp_db)

        # Create a gzipped text file
        text_file = tmp_path / "extracted.txt.gz"
        with gzip.open(text_file, 'wt', encoding='utf-8') as f:
            f.write("This is gzipped extracted text.")

        result = pipeline._read_extracted_text(str(text_file))
        assert result == "This is gzipped extracted text."

    def test_read_nonexistent_file(self, config, temp_db, mock_llm_client):
        """Test reading from nonexistent file returns None."""
        pipeline = LabelingPipeline(config, temp_db)

        result = pipeline._read_extracted_text("/nonexistent/path.txt")
        assert result is None

    def test_read_empty_path(self, config, temp_db, mock_llm_client):
        """Test reading with empty path returns None."""
        pipeline = LabelingPipeline(config, temp_db)

        result = pipeline._read_extracted_text("")
        assert result is None

        result = pipeline._read_extracted_text(None)
        assert result is None


# =============================================================================
# Context Building Tests
# =============================================================================

class TestContextBuilding:
    """Tests for building labeling context."""

    def test_build_context_basic(self, config, temp_db, mock_llm_client, tmp_path):
        """Test building context from file info."""
        pipeline = LabelingPipeline(config, temp_db)

        # Create extraction file
        text_file = tmp_path / "extracted.txt"
        text_file.write_text("Account Statement\nBalance: $1,234.56")

        file_info = {
            "id": 1,
            "path": "/Documents/Financial/2024/statement.pdf",
            "size": 50000,
            "mime_type": "application/pdf",
            "mtime": 1700000000,
            "extraction_path": str(text_file),
        }

        context = pipeline._build_context(file_info)

        assert context.filename == "statement.pdf"
        assert "2024" in context.parent_folders
        assert "Financial" in context.parent_folders
        assert context.extracted_text == "Account Statement\nBalance: $1,234.56"
        assert context.file_size == 50000
        assert context.mime_type == "application/pdf"
        assert config.doc_types == context.available_doc_types
        assert config.tags == context.available_tags

    def test_build_context_no_extraction(self, config, temp_db, mock_llm_client):
        """Test building context with no extraction file."""
        pipeline = LabelingPipeline(config, temp_db)

        file_info = {
            "id": 1,
            "path": "/Documents/image.jpg",
            "size": 2000000,
            "mime_type": "image/jpeg",
            "mtime": 1700000000,
        }

        context = pipeline._build_context(file_info)

        assert context.filename == "image.jpg"
        assert context.extracted_text is None

    def test_build_context_parent_folders_limit(self, config, temp_db, mock_llm_client):
        """Test that only last 5 parent folders are included."""
        pipeline = LabelingPipeline(config, temp_db)

        # Deep path with more than 5 parents
        file_info = {
            "id": 1,
            "path": "/a/b/c/d/e/f/g/h/file.pdf",
            "size": 1000,
            "mtime": 0,
        }

        context = pipeline._build_context(file_info)

        # Should only have last 5 folders (d, e, f, g, h)
        assert len(context.parent_folders) == 5
        assert context.parent_folders[-1] == "h"


# =============================================================================
# File Labeling Tests
# =============================================================================

class TestFileLabeling:
    """Tests for labeling individual files."""

    def test_label_file_success(self, config, temp_db, mock_llm_client, sample_label_output, tmp_path):
        """Test successful file labeling."""
        # Setup mock
        mock_instance = mock_llm_client.return_value
        mock_instance.label_with_escalation.return_value = (sample_label_output, False)

        pipeline = LabelingPipeline(config, temp_db)

        # Create a run
        run_id = temp_db.create_run("label", {})

        # Create extraction file
        text_file = tmp_path / "extracted.txt"
        text_file.write_text("Bank Statement")

        file_info = {
            "id": 1,
            "path": "/Documents/statement.pdf",
            "size": 50000,
            "mime_type": "application/pdf",
            "mtime": 1700000000,
            "extraction_path": str(text_file),
        }

        # First, insert a file record so we have a valid file_id
        scan_run_id = temp_db.create_run("scan", {})
        temp_db.insert_file(FileRecord(
            path=file_info["path"],
            sha256="abc123",
            size=file_info["size"],
            mtime=file_info["mtime"],
            ctime=file_info["mtime"],
            mime_type=file_info["mime_type"],
            scan_run_id=scan_run_id,
        ))

        result, escalated, error = pipeline.label_file(file_info, run_id)

        assert error is None
        assert result.doc_type == "financial"
        assert result.confidence == 0.92
        assert escalated is False
        mock_instance.label_with_escalation.assert_called_once()

    def test_label_file_with_escalation(self, config, temp_db, mock_llm_client, sample_label_output, tmp_path):
        """Test file labeling with escalation."""
        mock_instance = mock_llm_client.return_value
        mock_instance.label_with_escalation.return_value = (sample_label_output, True)  # escalated=True

        pipeline = LabelingPipeline(config, temp_db)
        run_id = temp_db.create_run("label", {})

        text_file = tmp_path / "extracted.txt"
        text_file.write_text("Tax Document")

        file_info = {
            "id": 1,
            "path": "/Documents/taxes.pdf",
            "size": 30000,
            "mime_type": "application/pdf",
            "mtime": 1700000000,
            "extraction_path": str(text_file),
        }

        scan_run_id = temp_db.create_run("scan", {})
        temp_db.insert_file(FileRecord(
            path=file_info["path"],
            sha256="def456",
            size=file_info["size"],
            mtime=file_info["mtime"],
            ctime=file_info["mtime"],
            mime_type=file_info["mime_type"],
            scan_run_id=scan_run_id,
        ))

        result, escalated, error = pipeline.label_file(file_info, run_id)

        assert error is None
        assert escalated is True

    def test_label_file_no_escalation_flag(self, config, temp_db, mock_llm_client, sample_label_output, tmp_path):
        """Test file labeling with escalation disabled."""
        mock_instance = mock_llm_client.return_value
        mock_instance.label_document.return_value = sample_label_output

        pipeline = LabelingPipeline(config, temp_db)
        run_id = temp_db.create_run("label", {})

        text_file = tmp_path / "extracted.txt"
        text_file.write_text("Document text")

        file_info = {
            "id": 1,
            "path": "/Documents/doc.pdf",
            "size": 10000,
            "mime_type": "application/pdf",
            "mtime": 1700000000,
            "extraction_path": str(text_file),
        }

        scan_run_id = temp_db.create_run("scan", {})
        temp_db.insert_file(FileRecord(
            path=file_info["path"],
            sha256="ghi789",
            size=file_info["size"],
            mtime=file_info["mtime"],
            ctime=file_info["mtime"],
            mime_type=file_info["mime_type"],
            scan_run_id=scan_run_id,
        ))

        result, escalated, error = pipeline.label_file(file_info, run_id, use_escalation=False)

        assert error is None
        assert escalated is False
        # Should call label_document directly, not label_with_escalation
        mock_instance.label_document.assert_called_once()
        mock_instance.label_with_escalation.assert_not_called()

    def test_label_file_error_handling(self, config, temp_db, mock_llm_client, tmp_path):
        """Test error handling during labeling."""
        mock_instance = mock_llm_client.return_value
        mock_instance.label_with_escalation.side_effect = Exception("LLM connection failed")

        pipeline = LabelingPipeline(config, temp_db)
        run_id = temp_db.create_run("label", {})

        file_info = {
            "id": 1,
            "path": "/Documents/doc.pdf",
            "size": 10000,
            "mtime": 1700000000,
        }

        result, escalated, error = pipeline.label_file(file_info, run_id)

        assert result is None
        assert escalated is False
        assert error is not None
        assert "LLM connection failed" in error


# =============================================================================
# Database Query Tests
# =============================================================================

class TestDatabaseQueries:
    """Tests for pipeline database queries."""

    def test_get_files_for_labeling(self, config, temp_db, mock_llm_client):
        """Test getting files that need labeling."""
        pipeline = LabelingPipeline(config, temp_db)

        # Initially should be empty
        files = pipeline.get_files_for_labeling()
        assert len(files) == 0

    def test_count_files_for_labeling(self, config, temp_db, mock_llm_client):
        """Test counting files that need labeling."""
        pipeline = LabelingPipeline(config, temp_db)

        count = pipeline.count_files_for_labeling()
        assert count == 0

    def test_get_files_with_limit(self, config, temp_db, mock_llm_client):
        """Test getting limited number of files."""
        pipeline = LabelingPipeline(config, temp_db)

        files = pipeline.get_files_for_labeling(limit=5)
        assert isinstance(files, list)

    def test_get_files_force_mode(self, config, temp_db, mock_llm_client):
        """Test getting files in force mode (include already labeled)."""
        pipeline = LabelingPipeline(config, temp_db)

        files = pipeline.get_files_for_labeling(force=True)
        assert isinstance(files, list)


# =============================================================================
# LM Studio Connection Tests
# =============================================================================

class TestLMStudioConnection:
    """Tests for LM Studio connection checking."""

    def test_check_connection_success(self, config, temp_db, mock_llm_client):
        """Test successful connection check."""
        mock_instance = mock_llm_client.return_value
        mock_models = Mock()
        mock_models.data = [
            Mock(id="qwen2.5-7b-instruct"),
            Mock(id="qwen2.5-14b-instruct"),
        ]
        mock_instance.client.models.list.return_value = mock_models

        pipeline = LabelingPipeline(config, temp_db)
        success, message = pipeline.check_lm_studio_connection()

        assert success is True
        assert "Connected" in message

    def test_check_connection_no_models(self, config, temp_db, mock_llm_client):
        """Test connection check with no models loaded."""
        mock_instance = mock_llm_client.return_value
        mock_models = Mock()
        mock_models.data = []
        mock_instance.client.models.list.return_value = mock_models

        pipeline = LabelingPipeline(config, temp_db)
        success, message = pipeline.check_lm_studio_connection()

        assert success is False
        assert "no models are loaded" in message

    def test_check_connection_missing_model(self, config, temp_db, mock_llm_client):
        """Test connection check with missing required models."""
        mock_instance = mock_llm_client.return_value
        mock_models = Mock()
        mock_models.data = [
            Mock(id="some-other-model"),
        ]
        mock_instance.client.models.list.return_value = mock_models

        pipeline = LabelingPipeline(config, temp_db)
        success, message = pipeline.check_lm_studio_connection()

        assert success is False
        assert "Missing" in message

    def test_check_connection_refused(self, config, temp_db, mock_llm_client):
        """Test connection check when LM Studio not running."""
        mock_instance = mock_llm_client.return_value
        mock_instance.client.models.list.side_effect = Exception("Connection refused")

        pipeline = LabelingPipeline(config, temp_db)
        success, message = pipeline.check_lm_studio_connection()

        assert success is False
        assert "Cannot connect" in message or "Connection refused" in message


# =============================================================================
# End-to-End Pipeline Tests
# =============================================================================

class TestEndToEndPipeline:
    """End-to-end tests for the labeling pipeline."""

    def test_full_labeling_workflow(self, config, temp_db, mock_llm_client, sample_label_output, tmp_path):
        """Test complete labeling workflow."""
        mock_instance = mock_llm_client.return_value
        mock_instance.label_with_escalation.return_value = (sample_label_output, False)

        pipeline = LabelingPipeline(config, temp_db)

        # 1. Create a scan run and add a file
        scan_run_id = temp_db.create_run("scan", {"source_root": "/test"})
        file_id = temp_db.insert_file(FileRecord(
            path="/test/document.pdf",
            sha256="abc123def456",
            size=50000,
            mtime=1700000000,
            ctime=1700000000,
            mime_type="application/pdf",
            scan_run_id=scan_run_id,
        ))

        # 2. Create extraction record
        extraction_file = tmp_path / "extracted.txt.gz"
        with gzip.open(extraction_file, 'wt') as f:
            f.write("Bank of America\nAccount Statement\nBalance: $5,432.10")

        temp_db.record_extraction(
            file_id=file_id,
            run_id=scan_run_id,
            method="docling",
            status="success",
            output_path=str(extraction_file),
        )

        # 3. Verify file appears in labeling queue
        files_to_label = pipeline.get_files_for_labeling()
        assert len(files_to_label) == 1
        assert files_to_label[0]["id"] == file_id

        # 4. Create labeling run and label the file
        label_run_id = temp_db.create_run("label", {})
        result, escalated, error = pipeline.label_file(files_to_label[0], label_run_id)

        assert error is None
        assert result.doc_type == "financial"

        # 5. Verify file no longer in labeling queue
        files_remaining = pipeline.get_files_for_labeling()
        assert len(files_remaining) == 0

        # 6. Force mode should still show the file
        files_force = pipeline.get_files_for_labeling(force=True)
        assert len(files_force) == 1

    def test_multiple_files_labeling(self, config, temp_db, mock_llm_client, tmp_path):
        """Test labeling multiple files."""
        labels = [
            LabelOutput(
                doc_type="financial",
                title="Statement 1",
                canonical_filename="2024-01-01-Financial-Bank-Statement",
                suggested_tags=["finances"],
                target_group_path="03 Financial",
                confidence=0.9,
                why="Bank statement",
            ),
            LabelOutput(
                doc_type="tax",
                title="W2 Form",
                canonical_filename="2024-01-15-Taxes-Employer-W2",
                suggested_tags=["taxes"],
                target_group_path="04 Taxes",
                confidence=0.85,
                why="W2 tax form",
            ),
        ]

        mock_instance = mock_llm_client.return_value
        mock_instance.label_with_escalation.side_effect = [
            (labels[0], False),
            (labels[1], True),  # Second file escalated
        ]

        pipeline = LabelingPipeline(config, temp_db)

        # Add files
        scan_run_id = temp_db.create_run("scan", {})
        for i in range(2):
            file_id = temp_db.insert_file(FileRecord(
                path=f"/test/doc{i}.pdf",
                sha256=f"hash{i}",
                size=10000,
                mtime=1700000000,
                ctime=1700000000,
                scan_run_id=scan_run_id,
            ))
            extraction_file = tmp_path / f"extracted{i}.txt"
            extraction_file.write_text(f"Document {i} content")
            temp_db.record_extraction(
                file_id=file_id,
                run_id=scan_run_id,
                method="docling",
                status="success",
                output_path=str(extraction_file),
            )

        # Label all files
        label_run_id = temp_db.create_run("label", {})
        files = pipeline.get_files_for_labeling()
        assert len(files) == 2

        results = []
        for file_info in files:
            result, escalated, error = pipeline.label_file(file_info, label_run_id)
            results.append((result, escalated, error))

        # Verify results
        assert results[0][0].doc_type == "financial"
        assert results[0][1] is False  # Not escalated
        assert results[1][0].doc_type == "tax"
        assert results[1][1] is True  # Escalated

        # All files should be labeled
        remaining = pipeline.get_files_for_labeling()
        assert len(remaining) == 0
