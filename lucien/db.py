"""
SQLite database management for Lucien.

Handles schema creation, migrations, and core database operations.
"""

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Tuple

from pydantic import BaseModel


class FileRecord(BaseModel):
    """File record model."""

    id: Optional[int] = None
    path: str
    sha256: str
    size: int
    mime_type: Optional[str] = None
    mtime: int
    ctime: int
    scan_run_id: int
    created_at: Optional[int] = None


class ExtractionRecord(BaseModel):
    """Text extraction record model."""

    id: Optional[int] = None
    file_id: int
    method: str
    status: str
    output_path: Optional[str] = None
    error: Optional[str] = None
    extraction_run_id: int
    created_at: Optional[int] = None


class LabelRecord(BaseModel):
    """AI labeling record model."""

    id: Optional[int] = None
    file_id: int
    doc_type: str
    title: Optional[str] = None
    canonical_filename: Optional[str] = None
    suggested_tags: List[str] = []
    target_group_path: Optional[str] = None
    date: Optional[str] = None
    issuer: Optional[str] = None
    source: Optional[str] = None
    confidence: Optional[float] = None
    why: Optional[str] = None
    model_name: str
    prompt_hash: str
    labeling_run_id: int
    created_at: Optional[int] = None


class PlanRecord(BaseModel):
    """Materialization plan record model."""

    id: Optional[int] = None
    file_id: int
    label_id: Optional[int] = None
    operation: str
    source_path: str
    target_path: str
    target_filename: str
    tags: List[str] = []
    needs_review: bool = False
    plan_run_id: int
    created_at: Optional[int] = None


class RunRecord(BaseModel):
    """Run history record model."""

    id: Optional[int] = None
    run_type: str
    config: Optional[Dict[str, Any]] = None
    started_at: Optional[int] = None
    completed_at: Optional[int] = None
    status: str = "running"
    error: Optional[str] = None


# Schema version for migrations
SCHEMA_VERSION = 1

# SQLite schema
SCHEMA_SQL = """
-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at INTEGER DEFAULT (strftime('%s', 'now'))
);

-- Run history and versioning
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY,
    run_type TEXT NOT NULL,
    config TEXT,
    started_at INTEGER DEFAULT (strftime('%s', 'now')),
    completed_at INTEGER,
    status TEXT DEFAULT 'running',
    error TEXT
);

-- File inventory from source backup
CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY,
    path TEXT NOT NULL UNIQUE,
    sha256 TEXT NOT NULL,
    size INTEGER NOT NULL,
    mime_type TEXT,
    mtime INTEGER,
    ctime INTEGER,
    scan_run_id INTEGER REFERENCES runs(id),
    created_at INTEGER DEFAULT (strftime('%s', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_files_sha256 ON files(sha256);
CREATE INDEX IF NOT EXISTS idx_files_scan_run_id ON files(scan_run_id);

-- Text extraction results
CREATE TABLE IF NOT EXISTS extractions (
    id INTEGER PRIMARY KEY,
    file_id INTEGER NOT NULL REFERENCES files(id),
    method TEXT NOT NULL,
    status TEXT NOT NULL,
    output_path TEXT,
    error TEXT,
    extraction_run_id INTEGER REFERENCES runs(id),
    created_at INTEGER DEFAULT (strftime('%s', 'now')),
    UNIQUE(file_id, extraction_run_id)
);

CREATE INDEX IF NOT EXISTS idx_extractions_file_id ON extractions(file_id);
CREATE INDEX IF NOT EXISTS idx_extractions_status ON extractions(status);

-- AI labeling results
CREATE TABLE IF NOT EXISTS labels (
    id INTEGER PRIMARY KEY,
    file_id INTEGER NOT NULL REFERENCES files(id),
    doc_type TEXT NOT NULL,
    title TEXT,
    canonical_filename TEXT,
    suggested_tags TEXT,
    target_group_path TEXT,
    date TEXT,
    issuer TEXT,
    source TEXT,
    confidence REAL,
    why TEXT,
    model_name TEXT NOT NULL,
    prompt_hash TEXT NOT NULL,
    labeling_run_id INTEGER REFERENCES runs(id),
    created_at INTEGER DEFAULT (strftime('%s', 'now')),
    UNIQUE(file_id, labeling_run_id)
);

CREATE INDEX IF NOT EXISTS idx_labels_file_id ON labels(file_id);
CREATE INDEX IF NOT EXISTS idx_labels_doc_type ON labels(doc_type);

-- Materialization plans
CREATE TABLE IF NOT EXISTS plans (
    id INTEGER PRIMARY KEY,
    file_id INTEGER NOT NULL REFERENCES files(id),
    label_id INTEGER REFERENCES labels(id),
    operation TEXT NOT NULL,
    source_path TEXT NOT NULL,
    target_path TEXT NOT NULL,
    target_filename TEXT NOT NULL,
    tags TEXT,
    needs_review BOOLEAN DEFAULT 0,
    plan_run_id INTEGER REFERENCES runs(id),
    created_at INTEGER DEFAULT (strftime('%s', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_plans_file_id ON plans(file_id);
CREATE INDEX IF NOT EXISTS idx_plans_plan_run_id ON plans(plan_run_id);
"""


class Database:
    """SQLite database manager for Lucien."""

    def __init__(self, db_path: Path):
        """Initialize database connection."""
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    @contextmanager
    def _get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager for database connections."""
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        # Enable WAL mode for better concurrent access
        conn.execute("PRAGMA journal_mode=WAL")
        # Set busy timeout to handle concurrent writes
        conn.execute("PRAGMA busy_timeout=30000")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _ensure_schema(self) -> None:
        """Ensure database schema is up to date."""
        with self._get_connection() as conn:
            # Create tables
            conn.executescript(SCHEMA_SQL)

            # Check schema version
            cursor = conn.execute("SELECT version FROM schema_version ORDER BY version DESC LIMIT 1")
            row = cursor.fetchone()
            current_version = row[0] if row else 0

            # Apply migrations if needed
            if current_version < SCHEMA_VERSION:
                self._apply_migrations(conn, current_version, SCHEMA_VERSION)
                conn.execute("INSERT INTO schema_version (version) VALUES (?)", (SCHEMA_VERSION,))

    def _apply_migrations(self, conn: sqlite3.Connection, from_version: int, to_version: int) -> None:
        """Apply database migrations."""
        # Placeholder for future migrations
        # For now, we're at version 1, so no migrations needed
        pass

    # Run management
    def create_run(self, run_type: str, config: Optional[Dict[str, Any]] = None) -> int:
        """Create a new run record and return its ID."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO runs (run_type, config) VALUES (?, ?)",
                (run_type, json.dumps(config) if config else None)
            )
            return cursor.lastrowid

    def complete_run(self, run_id: int, error: Optional[str] = None) -> None:
        """Mark a run as completed."""
        status = "failed" if error else "completed"
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE runs SET completed_at = strftime('%s', 'now'), status = ?, error = ? WHERE id = ?",
                (status, error, run_id)
            )

    def get_run(self, run_id: int) -> Optional[RunRecord]:
        """Get run record by ID."""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,))
            row = cursor.fetchone()
            if row:
                data = dict(row)
                if data["config"]:
                    data["config"] = json.loads(data["config"])
                return RunRecord(**data)
            return None

    # File operations
    def insert_file(self, file: FileRecord) -> int:
        """Insert or update a file record. Returns file ID."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO files (path, sha256, size, mime_type, mtime, ctime, scan_run_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(path) DO UPDATE SET
                    sha256 = excluded.sha256,
                    size = excluded.size,
                    mime_type = excluded.mime_type,
                    mtime = excluded.mtime,
                    ctime = excluded.ctime,
                    scan_run_id = excluded.scan_run_id
                RETURNING id
                """,
                (file.path, file.sha256, file.size, file.mime_type, file.mtime, file.ctime, file.scan_run_id)
            )
            return cursor.fetchone()[0]

    def get_file_by_path(self, path: str) -> Optional[FileRecord]:
        """Get file record by path."""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM files WHERE path = ?", (path,))
            row = cursor.fetchone()
            if row:
                return FileRecord(**dict(row))
            return None

    def get_files_by_run(self, run_id: int) -> List[FileRecord]:
        """Get all files from a specific scan run."""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM files WHERE scan_run_id = ?", (run_id,))
            return [FileRecord(**dict(row)) for row in cursor.fetchall()]

    def get_all_files(self) -> List[FileRecord]:
        """Get all file records."""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM files ORDER BY path")
            return [FileRecord(**dict(row)) for row in cursor.fetchall()]

    # Extraction operations
    def insert_extraction(self, extraction: ExtractionRecord) -> int:
        """Insert extraction record. Returns extraction ID."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO extractions (file_id, method, status, output_path, error, extraction_run_id)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(file_id, extraction_run_id) DO UPDATE SET
                    method = excluded.method,
                    status = excluded.status,
                    output_path = excluded.output_path,
                    error = excluded.error
                RETURNING id
                """,
                (extraction.file_id, extraction.method, extraction.status, extraction.output_path,
                 extraction.error, extraction.extraction_run_id)
            )
            return cursor.fetchone()[0]

    def get_extraction(self, file_id: int, run_id: int) -> Optional[ExtractionRecord]:
        """Get extraction record for file and run."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM extractions WHERE file_id = ? AND extraction_run_id = ?",
                (file_id, run_id)
            )
            row = cursor.fetchone()
            if row:
                return ExtractionRecord(**dict(row))
            return None

    # Label operations
    def insert_label(self, label: LabelRecord) -> int:
        """Insert label record. Returns label ID."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO labels (
                    file_id, doc_type, title, canonical_filename, suggested_tags,
                    target_group_path, date, issuer, source, confidence, why,
                    model_name, prompt_hash, labeling_run_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(file_id, labeling_run_id) DO UPDATE SET
                    doc_type = excluded.doc_type,
                    title = excluded.title,
                    canonical_filename = excluded.canonical_filename,
                    suggested_tags = excluded.suggested_tags,
                    target_group_path = excluded.target_group_path,
                    date = excluded.date,
                    issuer = excluded.issuer,
                    source = excluded.source,
                    confidence = excluded.confidence,
                    why = excluded.why,
                    model_name = excluded.model_name,
                    prompt_hash = excluded.prompt_hash
                RETURNING id
                """,
                (
                    label.file_id, label.doc_type, label.title, label.canonical_filename,
                    json.dumps(label.suggested_tags), label.target_group_path, label.date,
                    label.issuer, label.source, label.confidence, label.why,
                    label.model_name, label.prompt_hash, label.labeling_run_id
                )
            )
            return cursor.fetchone()[0]

    def get_label(self, file_id: int, run_id: int) -> Optional[LabelRecord]:
        """Get label record for file and run."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM labels WHERE file_id = ? AND labeling_run_id = ?",
                (file_id, run_id)
            )
            row = cursor.fetchone()
            if row:
                data = dict(row)
                data["suggested_tags"] = json.loads(data["suggested_tags"]) if data["suggested_tags"] else []
                return LabelRecord(**data)
            return None

    # Plan operations
    def insert_plan(self, plan: PlanRecord) -> int:
        """Insert plan record. Returns plan ID."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO plans (
                    file_id, label_id, operation, source_path, target_path,
                    target_filename, tags, needs_review, plan_run_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    plan.file_id, plan.label_id, plan.operation, plan.source_path,
                    plan.target_path, plan.target_filename, json.dumps(plan.tags),
                    plan.needs_review, plan.plan_run_id
                )
            )
            return cursor.lastrowid

    def get_plans_by_run(self, run_id: int) -> List[PlanRecord]:
        """Get all plans from a specific plan run."""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM plans WHERE plan_run_id = ?", (run_id,))
            rows = cursor.fetchall()
            plans = []
            for row in rows:
                data = dict(row)
                data["tags"] = json.loads(data["tags"]) if data["tags"] else []
                plans.append(PlanRecord(**data))
            return plans

    def count_files_for_extraction(self, force: bool = False, skip_extensions: Optional[List[str]] = None) -> int:
        """
        Count files that need extraction.

        Args:
            force: If True, count all files even if already extracted
            skip_extensions: List of file extensions to skip (e.g., ['.jpg', '.png'])

        Returns:
            Number of files needing extraction
        """
        with self._get_connection() as conn:
            if force:
                query = "SELECT COUNT(*) FROM files f"
                params = []
            else:
                query = """
                    SELECT COUNT(*)
                    FROM files f
                    LEFT JOIN extractions e ON f.id = e.file_id AND e.status = 'success'
                    WHERE e.id IS NULL
                """
                params = []

            # Add extension filtering if skip_extensions provided
            if skip_extensions:
                # Build SQL to exclude files with skip extensions
                # Use LOWER() to make comparison case-insensitive
                extension_conditions = []
                for ext in skip_extensions:
                    # Simple LIKE pattern - no special characters to escape in extensions
                    # Match files ending with the extension (case-insensitive)
                    safe_ext = ext.lower()
                    extension_conditions.append(f"LOWER(f.path) NOT LIKE '%{safe_ext}'")

                if extension_conditions:
                    if "WHERE" in query:
                        query += " AND (" + " AND ".join(extension_conditions) + ")"
                    else:
                        query += " WHERE (" + " AND ".join(extension_conditions) + ")"

            cursor = conn.execute(query, params)
            return cursor.fetchone()[0]

    def count_previously_extracted_files(self) -> int:
        """
        Count files that were already successfully extracted.

        Returns:
            Number of files with successful extractions
        """
        with self._get_connection() as conn:
            query = """
                SELECT COUNT(DISTINCT f.id)
                FROM files f
                INNER JOIN extractions e ON f.id = e.file_id AND e.status = 'success'
            """
            cursor = conn.execute(query)
            return cursor.fetchone()[0]

    def count_files_with_skip_extensions(self, skip_extensions: Optional[List[str]] = None) -> int:
        """
        Count files that match skip extensions.

        Args:
            skip_extensions: List of file extensions to count (e.g., ['.jpg', '.png'])

        Returns:
            Number of files matching skip extensions
        """
        if not skip_extensions:
            return 0

        with self._get_connection() as conn:
            # Build SQL to match files with skip extensions
            extension_conditions = []
            for ext in skip_extensions:
                # Simple LIKE pattern - no special characters to escape in extensions
                safe_ext = ext.lower()
                extension_conditions.append(f"LOWER(f.path) LIKE '%{safe_ext}'")

            if not extension_conditions:
                return 0

            query = f"SELECT COUNT(*) FROM files f WHERE ({' OR '.join(extension_conditions)})"
            cursor = conn.execute(query)
            return cursor.fetchone()[0]

    def get_files_for_extraction(self, force: bool = False, limit: Optional[int] = None,
                                 offset: Optional[int] = None, batch_size: Optional[int] = None,
                                 skip_extensions: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Get files that need extraction.

        Args:
            force: If True, include all files even if already extracted
            limit: Maximum number of files to return (total)
            offset: Offset for pagination
            batch_size: Number of files to return in this batch (for memory efficiency)
            skip_extensions: List of file extensions to skip (e.g., ['.jpg', '.png'])

        Returns:
            List of file records as dictionaries
        """
        with self._get_connection() as conn:
            if force:
                # Get all files
                query = "SELECT f.id, f.path, f.sha256 FROM files f"
                params = []
            else:
                # Get files without successful extraction
                query = """
                    SELECT f.id, f.path, f.sha256
                    FROM files f
                    LEFT JOIN extractions e ON f.id = e.file_id AND e.status = 'success'
                    WHERE e.id IS NULL
                """
                params = []

            # Add extension filtering if skip_extensions provided
            if skip_extensions:
                # Build SQL to exclude files with skip extensions
                # Use LOWER() to make comparison case-insensitive
                extension_conditions = []
                for ext in skip_extensions:
                    # Simple LIKE pattern - no special characters to escape in extensions
                    # Match files ending with the extension (case-insensitive)
                    safe_ext = ext.lower()
                    extension_conditions.append(f"LOWER(f.path) NOT LIKE '%{safe_ext}'")

                if extension_conditions:
                    if "WHERE" in query:
                        query += " AND (" + " AND ".join(extension_conditions) + ")"
                    else:
                        query += " WHERE (" + " AND ".join(extension_conditions) + ")"

            # Add ORDER BY before LIMIT/OFFSET
            query += " ORDER BY f.path" if "ORDER BY" not in query else ""

            # Apply pagination if batch_size is specified
            if batch_size:
                query += " LIMIT ?"
                params.append(batch_size)
                if offset is not None:
                    query += " OFFSET ?"
                    params.append(offset)
            elif limit:
                query += " LIMIT ?"
                params.append(limit)

            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def record_extraction(self, file_id: int, run_id: int, method: str, status: str,
                         output_path: Optional[str] = None, error: Optional[str] = None) -> int:
        """
        Record an extraction result.

        Args:
            file_id: File ID
            run_id: Extraction run ID
            method: Extraction method used
            status: Extraction status ('success', 'failed', 'skipped')
            output_path: Path to extracted text sidecar
            error: Error message if extraction failed

        Returns:
            Extraction record ID
        """
        extraction = ExtractionRecord(
            file_id=file_id,
            method=method,
            status=status,
            output_path=output_path,
            error=error,
            extraction_run_id=run_id
        )
        return self.insert_extraction(extraction)

    def get_extraction_stats(self, run_id: Optional[int] = None) -> Dict[str, int]:
        """
        Get extraction statistics.

        Args:
            run_id: Optional run ID to filter stats

        Returns:
            Dictionary with extraction counts by status
        """
        with self._get_connection() as conn:
            if run_id:
                query = """
                    SELECT status, COUNT(*) as count
                    FROM extractions
                    WHERE extraction_run_id = ?
                    GROUP BY status
                """
                params = (run_id,)
            else:
                query = """
                    SELECT status, COUNT(*) as count
                    FROM extractions
                    GROUP BY status
                """
                params = ()

            cursor = conn.execute(query, params)
            stats = {row["status"]: row["count"] for row in cursor.fetchall()}

            # Ensure all status types are present
            for status in ["success", "failed", "skipped"]:
                if status not in stats:
                    stats[status] = 0

            return stats

    def get_sample_files_for_extraction(self, force: bool = False, skip_extensions: Optional[List[str]] = None, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get a sample of files that need extraction for debugging.

        Args:
            force: If True, include all files even if already extracted
            skip_extensions: List of file extensions to skip
            limit: Number of sample files to return

        Returns:
            List of file records with extraction status
        """
        with self._get_connection() as conn:
            if force:
                query = """
                    SELECT f.id, f.path,
                           (SELECT COUNT(*) FROM extractions e WHERE e.file_id = f.id AND e.status = 'success') as success_count,
                           (SELECT COUNT(*) FROM extractions e WHERE e.file_id = f.id) as total_extractions
                    FROM files f
                """
                params = []
            else:
                query = """
                    SELECT f.id, f.path,
                           (SELECT COUNT(*) FROM extractions e WHERE e.file_id = f.id AND e.status = 'success') as success_count,
                           (SELECT COUNT(*) FROM extractions e WHERE e.file_id = f.id) as total_extractions
                    FROM files f
                    LEFT JOIN extractions e ON f.id = e.file_id AND e.status = 'success'
                    WHERE e.id IS NULL
                """
                params = []

            # Add extension filtering
            if skip_extensions:
                extension_conditions = []
                for ext in skip_extensions:
                    # Simple LIKE pattern - no special characters to escape in extensions
                    safe_ext = ext.lower()
                    extension_conditions.append(f"LOWER(f.path) NOT LIKE '%{safe_ext}'")

                if extension_conditions:
                    if "WHERE" in query:
                        query += " AND (" + " AND ".join(extension_conditions) + ")"
                    else:
                        query += " WHERE (" + " AND ".join(extension_conditions) + ")"

            query += f" ORDER BY f.path LIMIT {limit}"

            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    # Labeling operations
    def get_files_for_labeling(
        self,
        force: bool = False,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get files that need labeling (have successful extraction but no label).

        Args:
            force: If True, include all files with extraction (even if already labeled)
            limit: Maximum number of files to return

        Returns:
            List of file records with extraction info
        """
        with self._get_connection() as conn:
            if force:
                # Get all files with successful extraction (deduplicated by file_id)
                query = """
                    SELECT f.id, f.path, f.sha256, f.size, f.mime_type, f.mtime,
                           MAX(e.output_path) as extraction_path, MAX(e.method) as extraction_method
                    FROM files f
                    INNER JOIN extractions e ON f.id = e.file_id AND e.status = 'success'
                    GROUP BY f.id
                    ORDER BY f.path
                """
                params = []
            else:
                # Get files with extraction but no label (deduplicated by file_id)
                query = """
                    SELECT f.id, f.path, f.sha256, f.size, f.mime_type, f.mtime,
                           MAX(e.output_path) as extraction_path, MAX(e.method) as extraction_method
                    FROM files f
                    INNER JOIN extractions e ON f.id = e.file_id AND e.status = 'success'
                    LEFT JOIN labels l ON f.id = l.file_id
                    WHERE l.id IS NULL
                    GROUP BY f.id
                    ORDER BY f.path
                """
                params = []

            if limit:
                query += " LIMIT ?"
                params.append(limit)

            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def count_files_for_labeling(self, force: bool = False) -> int:
        """
        Count files that need labeling.

        Args:
            force: If True, count all files with extraction

        Returns:
            Number of files needing labeling
        """
        with self._get_connection() as conn:
            if force:
                query = """
                    SELECT COUNT(DISTINCT f.id)
                    FROM files f
                    INNER JOIN extractions e ON f.id = e.file_id AND e.status = 'success'
                """
            else:
                query = """
                    SELECT COUNT(DISTINCT f.id)
                    FROM files f
                    INNER JOIN extractions e ON f.id = e.file_id AND e.status = 'success'
                    LEFT JOIN labels l ON f.id = l.file_id
                    WHERE l.id IS NULL
                """
            cursor = conn.execute(query)
            return cursor.fetchone()[0]

    def get_labeling_stats(self, run_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Get labeling statistics.

        Args:
            run_id: Optional run ID to filter stats

        Returns:
            Dictionary with labeling counts and breakdowns
        """
        with self._get_connection() as conn:
            stats = {}

            # Base query filter
            run_filter = "WHERE labeling_run_id = ?" if run_id else ""
            params = (run_id,) if run_id else ()

            # Total labels
            cursor = conn.execute(f"SELECT COUNT(*) FROM labels {run_filter}", params)
            stats["total"] = cursor.fetchone()[0]

            # By doc_type
            cursor = conn.execute(
                f"SELECT doc_type, COUNT(*) as count FROM labels {run_filter} GROUP BY doc_type ORDER BY count DESC",
                params
            )
            stats["by_doc_type"] = {row["doc_type"]: row["count"] for row in cursor.fetchall()}

            # By model
            cursor = conn.execute(
                f"SELECT model_name, COUNT(*) as count FROM labels {run_filter} GROUP BY model_name",
                params
            )
            stats["by_model"] = {row["model_name"]: row["count"] for row in cursor.fetchall()}

            # Confidence distribution
            cursor = conn.execute(
                f"SELECT AVG(confidence) as avg_conf, MIN(confidence) as min_conf, MAX(confidence) as max_conf FROM labels {run_filter}",
                params
            )
            row = cursor.fetchone()
            if row and row["avg_conf"] is not None:
                stats["confidence"] = {
                    "avg": round(row["avg_conf"], 3),
                    "min": round(row["min_conf"], 3),
                    "max": round(row["max_conf"], 3),
                }
            else:
                stats["confidence"] = {"avg": 0, "min": 0, "max": 0}

            # Low confidence count (< 0.7)
            cursor = conn.execute(
                f"SELECT COUNT(*) FROM labels WHERE confidence < 0.7 {('AND labeling_run_id = ?' if run_id else '')}",
                params
            )
            stats["low_confidence_count"] = cursor.fetchone()[0]

            return stats

    def record_label(
        self,
        file_id: int,
        run_id: int,
        doc_type: str,
        title: str,
        canonical_filename: str,
        suggested_tags: List[str],
        target_group_path: str,
        confidence: float,
        why: str,
        model_name: str,
        prompt_hash: str,
        date: Optional[str] = None,
        issuer: Optional[str] = None,
        source: Optional[str] = None,
    ) -> int:
        """
        Record a labeling result.

        Returns:
            Label record ID
        """
        label = LabelRecord(
            file_id=file_id,
            doc_type=doc_type,
            title=title,
            canonical_filename=canonical_filename,
            suggested_tags=suggested_tags,
            target_group_path=target_group_path,
            date=date,
            issuer=issuer,
            source=source,
            confidence=confidence,
            why=why,
            model_name=model_name,
            prompt_hash=prompt_hash,
            labeling_run_id=run_id,
        )
        return self.insert_label(label)

    def get_latest_label(self, file_id: int) -> Optional[LabelRecord]:
        """Get the most recent label for a file."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM labels WHERE file_id = ? ORDER BY created_at DESC LIMIT 1",
                (file_id,)
            )
            row = cursor.fetchone()
            if row:
                data = dict(row)
                data["suggested_tags"] = json.loads(data["suggested_tags"]) if data["suggested_tags"] else []
                return LabelRecord(**data)
            return None

    # Statistics and queries
    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics."""
        with self._get_connection() as conn:
            stats = {}
            stats["total_files"] = conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
            stats["total_extractions"] = conn.execute("SELECT COUNT(*) FROM extractions WHERE status = 'success'").fetchone()[0]
            stats["total_labels"] = conn.execute("SELECT COUNT(*) FROM labels").fetchone()[0]
            stats["total_plans"] = conn.execute("SELECT COUNT(*) FROM plans").fetchone()[0]
            stats["total_runs"] = conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]

            # Recent runs
            cursor = conn.execute("""
                SELECT run_type, COUNT(*) as count
                FROM runs
                WHERE status = 'completed'
                GROUP BY run_type
            """)
            stats["runs_by_type"] = {row["run_type"]: row["count"] for row in cursor.fetchall()}

            return stats
