"""
Labeling pipeline for orchestrating AI document labeling.

Manages context building, LLM interaction, and result storage.
"""

import gzip
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from ..config import LucienSettings
from ..db import Database
from .client import LLMClient
from .models import LabelOutput, LabelingContext
from .prompts import get_prompt_version


class LabelingPipeline:
    """Pipeline for labeling documents with AI."""

    def __init__(self, config: LucienSettings, database: Database):
        """Initialize the labeling pipeline."""
        self.config = config
        self.database = database
        self.llm_client = LLMClient(config)
        self.prompt_version = get_prompt_version()

    def _read_extracted_text(self, extraction_path: str) -> Optional[str]:
        """Read extracted text from sidecar file."""
        if not extraction_path:
            return None

        path = Path(extraction_path)
        if not path.exists():
            return None

        try:
            if path.suffix == '.gz':
                with gzip.open(path, 'rt', encoding='utf-8') as f:
                    return f.read()
            else:
                with open(path, 'r', encoding='utf-8') as f:
                    return f.read()
        except Exception:
            return None

    def _build_context(self, file_info: Dict[str, Any]) -> LabelingContext:
        """Build labeling context from file info."""
        file_path = Path(file_info["path"])

        # Get parent folder names for context
        parent_folders = list(file_path.parent.parts[-5:])  # Last 5 folder names

        # Read extracted text
        extracted_text = self._read_extracted_text(file_info.get("extraction_path"))

        return LabelingContext(
            filename=file_path.name,
            parent_folders=parent_folders,
            extracted_text=extracted_text,
            file_size=file_info.get("size", 0),
            mime_type=file_info.get("mime_type"),
            mtime=file_info.get("mtime", 0),
            available_doc_types=self.config.doc_types,
            available_tags=self.config.tags,
            taxonomy=self.config.taxonomy.top_level,
            family_members=self.config.taxonomy.family_members,
        )

    def label_file(
        self,
        file_info: Dict[str, Any],
        run_id: int,
        use_escalation: bool = True,
    ) -> Tuple[LabelOutput, bool, Optional[str]]:
        """
        Label a single file.

        Args:
            file_info: File information dict from database
            run_id: Labeling run ID
            use_escalation: Whether to use automatic escalation

        Returns:
            Tuple of (LabelOutput, escalated: bool, error: Optional[str])
        """
        try:
            # Build context
            context = self._build_context(file_info)

            # Label with escalation if enabled
            if use_escalation:
                label, escalated = self.llm_client.label_with_escalation(context)
            else:
                label = self.llm_client.label_document(context, use_escalation=False)
                escalated = False

            # Determine model used
            if escalated:
                model_name = self.config.llm.escalation_model
            else:
                model_name = self.config.llm.default_model

            # Record in database
            self.database.record_label(
                file_id=file_info["id"],
                run_id=run_id,
                doc_type=label.doc_type,
                title=label.title,
                canonical_filename=label.canonical_filename,
                suggested_tags=label.suggested_tags,
                target_group_path=label.target_group_path,
                confidence=label.confidence,
                why=label.why,
                model_name=model_name,
                prompt_hash=self.prompt_version,
                date=label.date,
                issuer=label.issuer,
                source=label.source,
            )

            return label, escalated, None

        except Exception as e:
            return None, False, str(e)

    def get_files_for_labeling(
        self,
        force: bool = False,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Get files that need labeling."""
        return self.database.get_files_for_labeling(force=force, limit=limit)

    def count_files_for_labeling(self, force: bool = False) -> int:
        """Count files that need labeling."""
        return self.database.count_files_for_labeling(force=force)

    def check_lm_studio_connection(self) -> Tuple[bool, str]:
        """
        Check if LM Studio is running and accessible.

        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            # Try to list models - this will fail if LM Studio isn't running
            models = self.llm_client.client.models.list()
            model_ids = [m.id for m in models.data] if models.data else []

            if not model_ids:
                return False, "LM Studio is running but no models are loaded. Please load a model in LM Studio."

            # Check if our configured models are available
            default_model = self.config.llm.default_model
            escalation_model = self.config.llm.escalation_model

            missing = []
            if default_model not in model_ids:
                missing.append(f"default model '{default_model}'")
            if escalation_model not in model_ids:
                missing.append(f"escalation model '{escalation_model}'")

            if missing:
                available = ", ".join(model_ids[:5])
                return False, f"Missing {', '.join(missing)}. Available: {available}"

            return True, f"Connected. Models available: {default_model}, {escalation_model}"

        except Exception as e:
            error_msg = str(e)
            if "Connection refused" in error_msg or "Failed to establish" in error_msg:
                return False, f"Cannot connect to LM Studio at {self.config.llm.base_url}. Is LM Studio running?"
            return False, f"Error connecting to LM Studio: {error_msg}"
