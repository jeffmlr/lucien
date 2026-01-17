"""
Tests for LLM module (client, models, prompts, escalation).
"""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock

from lucien.config import LucienSettings
from lucien.llm.models import LabelOutput, LabelingContext
from lucien.llm.prompts import get_labeling_prompt, compute_prompt_hash, get_prompt_version, SYSTEM_PROMPT
from lucien.llm.client import LLMClient


# =============================================================================
# LabelOutput Model Tests
# =============================================================================

class TestLabelOutput:
    """Tests for LabelOutput Pydantic model."""

    def test_valid_label_output(self):
        """Test creating a valid LabelOutput."""
        label = LabelOutput(
            doc_type="financial",
            title="Chase Bank Statement - March 2024",
            canonical_filename="2024-03-15-Financial-Chase_Bank-Statement",
            suggested_tags=["finances", "statement"],
            target_group_path="03 Financial/Bank Statements",
            date="2024-03-15",
            issuer="Chase Bank",
            confidence=0.95,
            why="Clear bank statement with account details visible",
        )
        assert label.doc_type == "financial"
        assert label.confidence == 0.95
        assert len(label.suggested_tags) == 2

    def test_label_output_optional_fields(self):
        """Test LabelOutput with optional fields as None."""
        label = LabelOutput(
            doc_type="other",
            title="Unknown Document",
            canonical_filename="2024-01-01-Other-Unknown-Document",
            suggested_tags=[],
            target_group_path="98 Uncategorized",
            confidence=0.5,
            why="Unable to determine document type",
        )
        assert label.date is None
        assert label.issuer is None
        assert label.source is None

    def test_label_output_confidence_validation(self):
        """Test that confidence must be between 0 and 1."""
        # Valid boundary values
        label_low = LabelOutput(
            doc_type="other",
            title="Test",
            canonical_filename="test",
            target_group_path="test",
            confidence=0.0,
            why="test",
        )
        assert label_low.confidence == 0.0

        label_high = LabelOutput(
            doc_type="other",
            title="Test",
            canonical_filename="test",
            target_group_path="test",
            confidence=1.0,
            why="test",
        )
        assert label_high.confidence == 1.0

        # Invalid values
        with pytest.raises(ValueError):
            LabelOutput(
                doc_type="other",
                title="Test",
                canonical_filename="test",
                target_group_path="test",
                confidence=1.5,
                why="test",
            )

        with pytest.raises(ValueError):
            LabelOutput(
                doc_type="other",
                title="Test",
                canonical_filename="test",
                target_group_path="test",
                confidence=-0.1,
                why="test",
            )

    def test_label_output_required_fields(self):
        """Test that required fields raise error when missing."""
        with pytest.raises(ValueError):
            LabelOutput(
                title="Test",
                canonical_filename="test",
                target_group_path="test",
                confidence=0.5,
                why="test",
                # Missing doc_type
            )


# =============================================================================
# LabelingContext Model Tests
# =============================================================================

class TestLabelingContext:
    """Tests for LabelingContext model."""

    def test_valid_context(self):
        """Test creating a valid LabelingContext."""
        context = LabelingContext(
            filename="statement.pdf",
            parent_folders=["Documents", "Financial", "2024"],
            extracted_text="Account Statement\nBalance: $1,234.56",
            file_size=50000,
            mime_type="application/pdf",
            mtime=1700000000,
            available_doc_types=["financial", "tax", "other"],
            available_tags=["finances", "statement"],
            taxonomy=["01 Identity", "02 Medical", "03 Financial"],
            family_members=["Jeff", "Jamie"],
        )
        assert context.filename == "statement.pdf"
        assert len(context.parent_folders) == 3
        assert context.file_size == 50000

    def test_context_optional_text(self):
        """Test context with no extracted text."""
        context = LabelingContext(
            filename="image.jpg",
            parent_folders=["Photos"],
            file_size=2000000,
            mtime=1700000000,
            available_doc_types=["photo", "other"],
            available_tags=[],
            taxonomy=["10 Family Photos"],
        )
        assert context.extracted_text is None
        assert context.mime_type is None

    def test_context_family_members_default(self):
        """Test that family_members defaults to empty list."""
        context = LabelingContext(
            filename="test.pdf",
            parent_folders=[],
            file_size=1000,
            mtime=0,
            available_doc_types=["other"],
            available_tags=[],
            taxonomy=[],
        )
        assert context.family_members == []


# =============================================================================
# Prompt Generation Tests
# =============================================================================

class TestPromptGeneration:
    """Tests for prompt generation functions."""

    def test_get_labeling_prompt_structure(self):
        """Test that prompts are generated correctly."""
        context = LabelingContext(
            filename="test_document.pdf",
            parent_folders=["Documents", "Taxes"],
            extracted_text="W-2 Wage and Tax Statement",
            file_size=10000,
            mime_type="application/pdf",
            mtime=1700000000,
            available_doc_types=["w2", "tax", "other"],
            available_tags=["taxes", "form:w2"],
            taxonomy=["04 Taxes"],
            family_members=["Jeff"],
        )

        system_prompt, user_prompt = get_labeling_prompt(context)

        # Check system prompt
        assert "document classification assistant" in system_prompt
        assert "DOCUMENT TYPE:" in system_prompt
        assert "CANONICAL FILENAME FORMAT:" in system_prompt
        assert "JSON" in system_prompt

        # Check user prompt contains context
        assert "test_document.pdf" in user_prompt
        assert "Documents > Taxes" in user_prompt
        assert "W-2 Wage and Tax Statement" in user_prompt
        assert "w2, tax, other" in user_prompt
        assert "04 Taxes" in user_prompt
        assert "Jeff" in user_prompt

    def test_prompt_text_truncation(self):
        """Test that long text is truncated properly."""
        # Create context with very long text (>8000 chars)
        long_text = "A" * 10000
        context = LabelingContext(
            filename="test.pdf",
            parent_folders=[],
            extracted_text=long_text,
            file_size=1000,
            mtime=0,
            available_doc_types=["other"],
            available_tags=[],
            taxonomy=[],
        )

        _, user_prompt = get_labeling_prompt(context)

        # Text should be truncated
        assert "[... middle section omitted ...]" in user_prompt
        # Total should be around 8000 chars (head + marker + tail)
        assert len(user_prompt) < len(long_text) + 5000  # Prompt overhead

    def test_prompt_no_text(self):
        """Test prompt generation with no extracted text."""
        context = LabelingContext(
            filename="image.png",
            parent_folders=[],
            file_size=1000,
            mtime=0,
            available_doc_types=["photo"],
            available_tags=[],
            taxonomy=[],
        )

        _, user_prompt = get_labeling_prompt(context)
        assert "[No text extracted]" in user_prompt

    def test_prompt_hash_consistency(self):
        """Test that prompt hash is consistent for same input."""
        hash1 = compute_prompt_hash("system", "user")
        hash2 = compute_prompt_hash("system", "user")
        assert hash1 == hash2

    def test_prompt_hash_changes_with_content(self):
        """Test that prompt hash changes when content changes."""
        hash1 = compute_prompt_hash("system1", "user")
        hash2 = compute_prompt_hash("system2", "user")
        assert hash1 != hash2

    def test_get_prompt_version(self):
        """Test that prompt version returns a hash string."""
        version = get_prompt_version()
        assert isinstance(version, str)
        assert len(version) == 16  # SHA256 truncated to 16 chars


# =============================================================================
# Escalation Logic Tests
# =============================================================================

class TestEscalationLogic:
    """Tests for model escalation logic."""

    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return LucienSettings()

    @pytest.fixture
    def client(self, config):
        """Create LLM client with mocked OpenAI client."""
        with patch('lucien.llm.client.OpenAI'):
            return LLMClient(config)

    def test_escalate_for_sensitive_doc_type(self, client):
        """Test escalation for sensitive document types."""
        context = LabelingContext(
            filename="test.pdf",
            parent_folders=[],
            file_size=1000,
            mtime=0,
            available_doc_types=["tax", "other"],
            available_tags=[],
            taxonomy=[],
        )

        # Tax documents should escalate
        result = LabelOutput(
            doc_type="taxes",  # In escalation_doc_types
            title="Tax Return",
            canonical_filename="test",
            target_group_path="04 Taxes",
            confidence=0.95,
            why="test",
        )

        assert client.should_escalate(context, result) is True

    def test_escalate_for_low_confidence(self, client):
        """Test escalation for low confidence results."""
        context = LabelingContext(
            filename="test.pdf",
            parent_folders=[],
            file_size=1000,
            mtime=0,
            available_doc_types=["other"],
            available_tags=[],
            taxonomy=[],
        )

        # Low confidence should escalate (threshold is 0.7)
        result = LabelOutput(
            doc_type="other",
            title="Unknown",
            canonical_filename="test",
            target_group_path="test",
            confidence=0.5,  # Below threshold
            why="test",
        )

        assert client.should_escalate(context, result) is True

    def test_no_escalate_for_high_confidence(self, client):
        """Test no escalation for high confidence, non-sensitive docs."""
        context = LabelingContext(
            filename="test.pdf",
            parent_folders=[],
            file_size=1000,
            mtime=0,
            available_doc_types=["photo"],
            available_tags=[],
            taxonomy=[],
        )

        result = LabelOutput(
            doc_type="photo",
            title="Family Photo",
            canonical_filename="test",
            target_group_path="10 Family Photos",
            date="2024-01-01",
            issuer="Camera",
            confidence=0.95,
            why="test",
        )

        assert client.should_escalate(context, result) is False

    def test_escalate_for_missing_critical_fields(self, client):
        """Test escalation when critical fields are missing for certain doc types."""
        context = LabelingContext(
            filename="test.pdf",
            parent_folders=[],
            file_size=1000,
            mtime=0,
            available_doc_types=["financial"],
            available_tags=[],
            taxonomy=[],
        )

        # Financial doc with missing date/issuer should escalate
        result = LabelOutput(
            doc_type="financial",
            title="Some Financial Doc",
            canonical_filename="test",
            target_group_path="03 Financial",
            confidence=0.85,
            why="test",
            # date and issuer are None
        )

        assert client.should_escalate(context, result) is True


# =============================================================================
# LLM Client Tests
# =============================================================================

class TestLLMClient:
    """Tests for LLM client with mocked responses."""

    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return LucienSettings()

    @pytest.fixture
    def mock_openai(self):
        """Create mocked OpenAI client."""
        with patch('lucien.llm.client.OpenAI') as mock:
            yield mock

    def test_client_initialization(self, config, mock_openai):
        """Test client initializes with correct settings."""
        client = LLMClient(config)
        mock_openai.assert_called_once_with(
            base_url=config.llm.base_url,
            api_key="not-needed",
        )

    def test_label_document_success(self, config, mock_openai):
        """Test successful document labeling."""
        # Setup mock response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = json.dumps({
            "doc_type": "financial",
            "title": "Bank Statement",
            "canonical_filename": "2024-03-15-Financial-Chase-Statement",
            "suggested_tags": ["finances"],
            "target_group_path": "03 Financial",
            "date": "2024-03-15",
            "issuer": "Chase",
            "confidence": 0.9,
            "why": "Bank statement with clear formatting",
        })

        mock_openai.return_value.chat.completions.create.return_value = mock_response

        client = LLMClient(config)
        context = LabelingContext(
            filename="statement.pdf",
            parent_folders=["Documents"],
            file_size=1000,
            mtime=0,
            available_doc_types=["financial", "other"],
            available_tags=["finances"],
            taxonomy=["03 Financial"],
        )

        result = client.label_document(context)

        assert result.doc_type == "financial"
        assert result.confidence == 0.9
        assert "Chase" in result.issuer

    def test_label_document_with_markdown_response(self, config, mock_openai):
        """Test handling of markdown-wrapped JSON response."""
        mock_response = Mock()
        mock_response.choices = [Mock()]
        # Response wrapped in markdown code block
        mock_response.choices[0].message.content = """```json
{
    "doc_type": "tax",
    "title": "W2 Form",
    "canonical_filename": "2024-01-15-Taxes-Employer-W2",
    "suggested_tags": ["taxes"],
    "target_group_path": "04 Taxes",
    "confidence": 0.85,
    "why": "W2 tax form"
}
```"""

        mock_openai.return_value.chat.completions.create.return_value = mock_response

        client = LLMClient(config)
        context = LabelingContext(
            filename="w2.pdf",
            parent_folders=[],
            file_size=1000,
            mtime=0,
            available_doc_types=["tax", "w2"],
            available_tags=["taxes"],
            taxonomy=["04 Taxes"],
        )

        result = client.label_document(context)
        assert result.doc_type == "tax"

    def test_label_document_invalid_doc_type_correction(self, config, mock_openai):
        """Test that invalid doc_type is auto-corrected to 'other'."""
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = json.dumps({
            "doc_type": "invented_type",  # Not in available list
            "title": "Test Doc",
            "canonical_filename": "test",
            "suggested_tags": [],
            "target_group_path": "test",
            "confidence": 0.8,
            "why": "Original reasoning",
        })

        mock_openai.return_value.chat.completions.create.return_value = mock_response

        client = LLMClient(config)
        context = LabelingContext(
            filename="test.pdf",
            parent_folders=[],
            file_size=1000,
            mtime=0,
            available_doc_types=["financial", "other"],  # invented_type not here
            available_tags=[],
            taxonomy=[],
        )

        result = client.label_document(context)
        assert result.doc_type == "other"
        assert "Auto-corrected from 'invented_type'" in result.why

    def test_label_document_retry_on_json_error(self, config, mock_openai):
        """Test retry behavior on JSON parsing errors."""
        # First call returns invalid JSON, second returns valid
        mock_response_bad = Mock()
        mock_response_bad.choices = [Mock()]
        mock_response_bad.choices[0].message.content = "This is not JSON"

        mock_response_good = Mock()
        mock_response_good.choices = [Mock()]
        mock_response_good.choices[0].message.content = json.dumps({
            "doc_type": "other",
            "title": "Test",
            "canonical_filename": "test",
            "suggested_tags": [],
            "target_group_path": "test",
            "confidence": 0.7,
            "why": "test",
        })

        mock_openai.return_value.chat.completions.create.side_effect = [
            mock_response_bad,
            mock_response_good,
        ]

        client = LLMClient(config)
        context = LabelingContext(
            filename="test.pdf",
            parent_folders=[],
            file_size=1000,
            mtime=0,
            available_doc_types=["other"],
            available_tags=[],
            taxonomy=[],
        )

        result = client.label_document(context)
        assert result.doc_type == "other"
        # Should have been called twice (retry)
        assert mock_openai.return_value.chat.completions.create.call_count == 2

    def test_label_document_all_retries_exhausted(self, config, mock_openai):
        """Test error when all retries fail."""
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Not JSON"

        mock_openai.return_value.chat.completions.create.return_value = mock_response

        client = LLMClient(config)
        context = LabelingContext(
            filename="test.pdf",
            parent_folders=[],
            file_size=1000,
            mtime=0,
            available_doc_types=["other"],
            available_tags=[],
            taxonomy=[],
        )

        with pytest.raises(Exception) as exc_info:
            client.label_document(context)

        assert "Failed to label document" in str(exc_info.value)
        assert f"{config.llm.max_retries} attempts" in str(exc_info.value)

    def test_label_with_escalation_no_escalation_needed(self, config, mock_openai):
        """Test labeling without escalation when not needed."""
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = json.dumps({
            "doc_type": "photo",
            "title": "Family Photo",
            "canonical_filename": "2024-01-01-Media-Camera-Family_Photo",
            "suggested_tags": [],
            "target_group_path": "10 Family Photos",
            "date": "2024-01-01",
            "issuer": "iPhone",
            "confidence": 0.95,
            "why": "Clear family photo",
        })

        mock_openai.return_value.chat.completions.create.return_value = mock_response

        client = LLMClient(config)
        context = LabelingContext(
            filename="photo.jpg",
            parent_folders=[],
            file_size=1000,
            mtime=0,
            available_doc_types=["photo", "other"],
            available_tags=[],
            taxonomy=["10 Family Photos"],
        )

        result, escalated = client.label_with_escalation(context)

        assert result.doc_type == "photo"
        assert escalated is False
        # Only called once (no escalation)
        assert mock_openai.return_value.chat.completions.create.call_count == 1

    def test_label_with_escalation_triggered(self, config, mock_openai):
        """Test labeling with escalation triggered by low confidence."""
        # First response: low confidence
        mock_response_low = Mock()
        mock_response_low.choices = [Mock()]
        mock_response_low.choices[0].message.content = json.dumps({
            "doc_type": "other",
            "title": "Unknown",
            "canonical_filename": "test",
            "suggested_tags": [],
            "target_group_path": "98 Uncategorized",
            "confidence": 0.5,  # Low - triggers escalation
            "why": "Uncertain",
        })

        # Second response: better result from escalation model
        mock_response_high = Mock()
        mock_response_high.choices = [Mock()]
        mock_response_high.choices[0].message.content = json.dumps({
            "doc_type": "financial",
            "title": "Investment Statement",
            "canonical_filename": "2024-01-01-Financial-Vanguard-Statement",
            "suggested_tags": ["investment"],
            "target_group_path": "03 Financial",
            "date": "2024-01-01",
            "issuer": "Vanguard",
            "confidence": 0.9,
            "why": "Investment statement identified",
        })

        mock_openai.return_value.chat.completions.create.side_effect = [
            mock_response_low,
            mock_response_high,
        ]

        client = LLMClient(config)
        context = LabelingContext(
            filename="statement.pdf",
            parent_folders=[],
            file_size=1000,
            mtime=0,
            available_doc_types=["financial", "other"],
            available_tags=["investment"],
            taxonomy=["03 Financial"],
        )

        result, escalated = client.label_with_escalation(context)

        assert result.doc_type == "financial"
        assert result.confidence == 0.9
        assert escalated is True
        # Called twice (initial + escalation)
        assert mock_openai.return_value.chat.completions.create.call_count == 2

    def test_get_prompt_version_from_client(self, config, mock_openai):
        """Test getting prompt version from client."""
        client = LLMClient(config)
        version = client.get_prompt_version()
        assert isinstance(version, str)
        assert len(version) == 16
