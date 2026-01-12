"""
Plan generation (Phase 3: Plan Generation).

Generates reviewable transformation plans from label data.

TODO: Implement in Milestone 4 (v0.4)
"""

import csv
import json
from pathlib import Path
from typing import List, Optional

from .config import LucienSettings
from .db import Database, PlanRecord, LabelRecord, FileRecord


class Planner:
    """Generates materialization plans from label data."""

    def __init__(self, config: LucienSettings, db: Database):
        """Initialize planner with config and database."""
        self.config = config
        self.db = db

    def generate_canonical_filename(self, label: LabelRecord, file_record: FileRecord) -> str:
        """
        Generate canonical filename from label data.

        Format: YYYY-MM-DD__Domain__Issuer__Title.ext
        """
        # TODO: Implement canonical filename generation
        # Parse label.canonical_filename or construct from label fields
        # Apply naming config (separator, format)
        pass

    def generate_target_path(self, label: LabelRecord) -> Path:
        """
        Generate target path in staging mirror from label taxonomy.

        Returns:
            Path relative to staging_root
        """
        # TODO: Implement target path generation
        # Use label.target_group_path
        # Create directory structure based on taxonomy
        pass

    def should_needs_review(self, label: LabelRecord) -> bool:
        """
        Determine if file needs manual review.

        Flags files for review based on:
        - Low confidence
        - Missing critical fields
        - Uncategorized doc_type
        """
        # TODO: Implement review logic
        if label.confidence and label.confidence < 0.5:
            return True
        if label.doc_type in ["other", "uncategorized"]:
            return True
        return False

    def generate_plan(
        self,
        labeling_run_id: int,
        output_dir: Optional[Path] = None,
    ) -> int:
        """
        Generate materialization plan from labels.

        Args:
            labeling_run_id: Run ID of labeling operation
            output_dir: Directory for plan outputs (uses config if None)

        Returns:
            Plan run ID
        """
        # TODO: Implement plan generation
        # 1. Fetch all labels from labeling_run_id
        # 2. For each label, generate plan record
        # 3. Write plan.jsonl
        # 4. Write plan.csv
        # 5. Optionally write apply.sh
        raise NotImplementedError("Plan generation not yet implemented (Milestone 4)")

    def export_plan_jsonl(self, plan_run_id: int, output_path: Path) -> None:
        """Export plan to JSONL format."""
        # TODO: Implement JSONL export
        pass

    def export_plan_csv(self, plan_run_id: int, output_path: Path) -> None:
        """Export plan to CSV format for human review."""
        # TODO: Implement CSV export
        # Columns: file_id, source_path, target_path, target_filename, doc_type, tags, confidence, needs_review
        pass

    def import_plan_csv(self, csv_path: Path) -> int:
        """
        Import edited plan from CSV.

        Allows user to edit CSV in Numbers/Excel and re-import.

        Returns:
            New plan run ID
        """
        # TODO: Implement CSV import
        # Parse CSV
        # Validate changes
        # Create new plan run with updated records
        raise NotImplementedError("Plan CSV import not yet implemented (Milestone 4)")
