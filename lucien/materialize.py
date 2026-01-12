"""
Staging mirror materialization (Phase 4: Materialize Staging Mirror).

Creates the staging library from approved plans.

TODO: Implement in Milestone 4 (v0.4)
"""

import os
import shutil
from pathlib import Path
from typing import Optional

from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

from .config import LucienSettings
from .db import Database, PlanRecord
from .tags_macos import apply_finder_tags


class Materializer:
    """Materializes staging mirror from plans."""

    def __init__(self, config: LucienSettings, db: Database):
        """Initialize materializer with config and database."""
        self.config = config
        self.db = db

    def copy_file(self, source: Path, target: Path) -> None:
        """Copy file to target location."""
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)

    def hardlink_file(self, source: Path, target: Path) -> None:
        """Create hardlink to file at target location."""
        target.parent.mkdir(parents=True, exist_ok=True)
        os.link(source, target)

    def materialize_plan(
        self,
        plan_run_id: int,
        mode: Optional[str] = None,
        apply_tags: Optional[bool] = None,
        dry_run: bool = False,
    ) -> int:
        """
        Materialize staging mirror from plan.

        Args:
            plan_run_id: Plan run ID to materialize
            mode: 'copy' or 'hardlink' (uses config if None)
            apply_tags: Apply macOS Finder tags (uses config if None)
            dry_run: If True, don't actually create files

        Returns:
            Number of files materialized
        """
        # Use config defaults if not specified
        if mode is None:
            mode = self.config.materialize.default_mode
        if apply_tags is None:
            apply_tags = self.config.materialize.apply_tags

        # Validate mode
        if mode not in ["copy", "hardlink"]:
            raise ValueError(f"Invalid mode: {mode}. Must be 'copy' or 'hardlink'")

        # Fetch plan records
        plans = self.db.get_plans_by_run(plan_run_id)

        if not plans:
            raise ValueError(f"No plans found for run ID: {plan_run_id}")

        materialized_count = 0
        error_count = 0

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TextColumn("[cyan]{task.fields[current_file]}"),
        ) as progress:
            task = progress.add_task(
                f"[cyan]Materializing {len(plans)} files...",
                total=len(plans),
                current_file=""
            )

            for plan in plans:
                progress.update(task, current_file=Path(plan.source_path).name)

                try:
                    source = Path(plan.source_path)
                    target = self.config.staging_root / plan.target_path / plan.target_filename

                    if not dry_run:
                        # Create target
                        if mode == "copy":
                            self.copy_file(source, target)
                        else:  # hardlink
                            self.hardlink_file(source, target)

                        # Apply tags if requested
                        if apply_tags and plan.tags:
                            apply_finder_tags(target, plan.tags)

                    materialized_count += 1

                except Exception as e:
                    error_count += 1
                    # TODO: Log error properly
                    continue

                progress.advance(task)

        return materialized_count

    def materialize_from_jsonl(
        self,
        jsonl_path: Path,
        mode: Optional[str] = None,
        apply_tags: Optional[bool] = None,
        dry_run: bool = False,
    ) -> int:
        """
        Materialize directly from JSONL plan file.

        Useful for edited plans that haven't been re-imported to DB.

        Args:
            jsonl_path: Path to plan.jsonl file
            mode: 'copy' or 'hardlink'
            apply_tags: Apply macOS Finder tags
            dry_run: If True, don't actually create files

        Returns:
            Number of files materialized
        """
        # TODO: Implement JSONL materialization
        # Parse JSONL
        # For each record, materialize file
        raise NotImplementedError("JSONL materialization not yet implemented (Milestone 4)")


def materialize_plan(
    plan_run_id: int,
    config: Optional[LucienSettings] = None,
    db: Optional[Database] = None,
    mode: Optional[str] = None,
    apply_tags: Optional[bool] = None,
    dry_run: bool = False,
) -> int:
    """
    Convenience function to materialize a plan.

    Args:
        plan_run_id: Plan run ID to materialize
        config: Configuration (loads default if None)
        db: Database instance (creates from config if None)
        mode: 'copy' or 'hardlink'
        apply_tags: Apply macOS Finder tags
        dry_run: If True, don't actually create files

    Returns:
        Number of files materialized
    """
    if config is None:
        config = LucienSettings.load()

    if db is None:
        db = Database(config.index_db)

    materializer = Materializer(config, db)
    return materializer.materialize_plan(plan_run_id, mode, apply_tags, dry_run)
