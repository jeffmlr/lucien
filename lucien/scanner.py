"""
Filesystem scanner (Phase 0: Scan/Index).

Recursively crawls a source backup directory, computes hashes,
and stores file metadata in the database.
"""

import hashlib
import mimetypes
from pathlib import Path
from typing import Generator, Optional

from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

from .config import LucienSettings
from .db import Database, FileRecord


class FileScanner:
    """Scans filesystem and indexes files."""

    def __init__(self, config: LucienSettings, db: Database):
        """Initialize scanner with config and database."""
        self.config = config
        self.db = db

    def should_skip_directory(self, dir_path: Path) -> bool:
        """Check if directory should be skipped based on config."""
        dir_name = dir_path.name
        return dir_name in self.config.scan.skip_dirs

    def compute_hash(self, file_path: Path, algorithm: str = "sha256") -> str:
        """Compute file hash using specified algorithm."""
        hash_func = hashlib.new(algorithm)
        with open(file_path, "rb") as f:
            # Read in chunks to handle large files
            for chunk in iter(lambda: f.read(8192), b""):
                hash_func.update(chunk)
        return hash_func.hexdigest()

    def get_mime_type(self, file_path: Path) -> Optional[str]:
        """Get MIME type for file."""
        mime_type, _ = mimetypes.guess_type(str(file_path))
        return mime_type

    def scan_file(self, file_path: Path, run_id: int) -> Optional[FileRecord]:
        """
        Scan a single file and return a FileRecord.

        Returns None if file cannot be accessed.
        """
        try:
            stat = file_path.stat()

            # Compute hash (expensive operation)
            sha256 = self.compute_hash(file_path, self.config.scan.hash_algorithm)

            # Get MIME type
            mime_type = self.get_mime_type(file_path)

            return FileRecord(
                path=str(file_path),
                sha256=sha256,
                size=stat.st_size,
                mime_type=mime_type,
                mtime=int(stat.st_mtime),
                ctime=int(stat.st_ctime),
                scan_run_id=run_id,
            )
        except (OSError, PermissionError) as e:
            # Log error and skip file
            return None

    def iter_files(self, root_path: Path) -> Generator[Path, None, None]:
        """
        Recursively iterate over files in directory tree.

        Skips directories based on config.
        """
        if not root_path.exists():
            raise FileNotFoundError(f"Source root does not exist: {root_path}")

        if not root_path.is_dir():
            raise NotADirectoryError(f"Source root is not a directory: {root_path}")

        def _walk(path: Path) -> Generator[Path, None, None]:
            """Recursive walker with skip logic."""
            try:
                for item in path.iterdir():
                    if item.is_dir():
                        if self.should_skip_directory(item):
                            continue
                        if self.config.scan.follow_symlinks or not item.is_symlink():
                            yield from _walk(item)
                    elif item.is_file():
                        if self.config.scan.follow_symlinks or not item.is_symlink():
                            yield item
            except PermissionError:
                # Skip directories we can't access
                pass

        yield from _walk(root_path)

    def scan(
        self,
        root_path: Optional[Path] = None,
        dry_run: bool = False,
    ) -> int:
        """
        Scan directory tree and index files in database.

        Args:
            root_path: Root directory to scan (uses config.source_root if None)
            dry_run: If True, don't write to database

        Returns:
            Number of files indexed
        """
        if root_path is None:
            if self.config.source_root is None:
                raise ValueError("source_root must be provided in config or as argument")
            root_path = self.config.source_root

        root_path = Path(root_path)

        # Create run record
        run_id = self.db.create_run("scan", config={"root_path": str(root_path)})

        indexed_count = 0
        error_count = 0

        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                TextColumn("[cyan]{task.fields[current_file]}"),
            ) as progress:
                # First pass: count files (memory-efficient, just counting)
                task = progress.add_task(
                    "[cyan]Counting files...",
                    total=None,
                    current_file=""
                )

                # Count files without loading all paths into memory
                total = sum(1 for _ in self.iter_files(root_path))

                progress.update(task, description=f"[cyan]Scanning {total} files...", total=total)

                # Second pass: scan and index (process incrementally)
                for file_path in self.iter_files(root_path):
                    progress.update(task, current_file=str(file_path.name))

                    file_record = self.scan_file(file_path, run_id)

                    if file_record:
                        if not dry_run:
                            self.db.insert_file(file_record)
                        indexed_count += 1
                    else:
                        error_count += 1

                    progress.advance(task)

            # Complete run
            if not dry_run:
                self.db.complete_run(run_id)

            return indexed_count

        except Exception as e:
            # Mark run as failed
            if not dry_run:
                self.db.complete_run(run_id, error=str(e))
            raise


def scan_directory(
    root_path: Path,
    config: Optional[LucienSettings] = None,
    db: Optional[Database] = None,
    dry_run: bool = False,
) -> int:
    """
    Convenience function to scan a directory.

    Args:
        root_path: Root directory to scan
        config: Configuration (loads default if None)
        db: Database instance (creates from config if None)
        dry_run: If True, don't write to database

    Returns:
        Number of files indexed
    """
    if config is None:
        config = LucienSettings.load()

    if db is None:
        db = Database(config.index_db)

    scanner = FileScanner(config, db)
    return scanner.scan(root_path, dry_run=dry_run)
