"""
Lucien CLI using Typer.

Command-line interface for all pipeline stages.
"""

import gc
import json
import logging
import multiprocessing
import re
import sys
import threading
import time
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console, Group
from rich.table import Table
from rich.live import Live
from rich.panel import Panel
from rich.text import Text

from . import __version__
from .config import LucienSettings
from .db import Database
from .scanner import FileScanner

app = typer.Typer(
    name="lucien",
    help="Lucien: Library Builder System - Transform backups into organized, DEVONthink-ready libraries",
    add_completion=False,
)

console = Console()


def version_callback(value: bool):
    """Show version and exit."""
    if value:
        console.print(f"Lucien version {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        "-v",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit",
    ),
):
    """Lucien: Library Builder System"""
    pass


@app.command()
def scan(
    root: Path = typer.Argument(
        ...,
        help="Root directory of source backup to scan",
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        resolve_path=True,
    ),
    db: Optional[Path] = typer.Option(
        None,
        "--db",
        help="Database path (default: from config)",
    ),
    config_file: Optional[Path] = typer.Option(
        None,
        "--config",
        "-c",
        help="Config file path",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Don't write to database, just count files",
    ),
):
    """
    Phase 0: Scan and index files from source backup.

    Recursively scans the source directory, computes hashes,
    and stores file metadata in the database.
    """
    try:
        # Load config
        if config_file:
            config = LucienSettings.load_from_yaml(config_file)
        else:
            config = LucienSettings.load()

        # Override db path if provided
        if db:
            config.index_db = db

        # Ensure directories exist
        config.ensure_directories()

        # Initialize database
        database = Database(config.index_db)

        # Scan
        console.print(f"\n[bold cyan]Scanning source:[/] {root}")
        console.print(f"[bold cyan]Database:[/] {config.index_db}")
        if dry_run:
            console.print("[yellow]Dry run mode - no changes will be saved[/]\n")

        scanner = FileScanner(config, database)
        count = scanner.scan(root, dry_run=dry_run)

        console.print(f"\n[bold green]✓ Indexed {count} files[/]")

        # Show stats
        if not dry_run:
            stats = database.get_stats()
            console.print(f"[dim]Total files in database: {stats['total_files']}[/]")

    except Exception as e:
        console.print(f"[bold red]Error:[/] {e}")
        sys.exit(1)


@app.command()
def stats(
    db: Optional[Path] = typer.Option(
        None,
        "--db",
        help="Database path (default: from config)",
    ),
    config_file: Optional[Path] = typer.Option(
        None,
        "--config",
        "-c",
        help="Config file path",
    ),
):
    """
    Show database statistics.
    """
    try:
        # Load config
        if config_file:
            config = LucienSettings.load_from_yaml(config_file)
        else:
            config = LucienSettings.load()

        # Override db path if provided
        if db:
            config.index_db = db

        # Initialize database
        database = Database(config.index_db)

        # Get stats
        stats = database.get_stats()

        # Display stats in a table
        table = Table(title="Lucien Database Statistics", show_header=True, header_style="bold cyan")
        table.add_column("Metric", style="cyan")
        table.add_column("Count", justify="right", style="green")

        table.add_row("Total Files", str(stats["total_files"]))
        table.add_row("Successful Extractions", str(stats["total_extractions"]))
        table.add_row("Total Labels", str(stats["total_labels"]))
        table.add_row("Total Plans", str(stats["total_plans"]))
        table.add_row("Total Runs", str(stats["total_runs"]))

        console.print()
        console.print(table)
        console.print()

        # Runs by type
        if stats.get("runs_by_type"):
            console.print("[bold cyan]Runs by Type:[/]")
            for run_type, count in stats["runs_by_type"].items():
                console.print(f"  {run_type}: {count}")

    except Exception as e:
        console.print(f"[bold red]Error:[/] {e}")
        sys.exit(1)


@app.command()
def init_config(
    output: Path = typer.Option(
        Path.cwd() / "lucien.yaml",
        "--output",
        "-o",
        help="Output config file path",
    ),
    user: bool = typer.Option(
        False,
        "--user",
        help="Create user config at ~/.lucien/config.yaml",
    ),
):
    """
    Initialize a configuration file with defaults.
    """
    try:
        config = LucienSettings()

        if user:
            output = Path.home() / ".lucien/config.yaml"

        if output.exists():
            overwrite = typer.confirm(f"Config file exists at {output}. Overwrite?")
            if not overwrite:
                console.print("[yellow]Cancelled[/]")
                raise typer.Exit()

        config.save_to_yaml(output)
        console.print(f"[bold green]✓ Config file created:[/] {output}")
        console.print("\n[cyan]Next steps:[/]")
        console.print("1. Edit the config file to set your source_root and other preferences")
        console.print("2. Run: lucien scan <source_root>")

    except Exception as e:
        console.print(f"[bold red]Error:[/] {e}")
        sys.exit(1)


@app.command()
def extract(
    db: Optional[Path] = typer.Option(
        None,
        "--db",
        help="Database path (default: from config)",
    ),
    config_file: Optional[Path] = typer.Option(
        None,
        "--config",
        "-c",
        help="Config file path",
    ),
    output_dir: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output directory for extracted text (default: from config)",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Re-extract files that were already processed",
    ),
    limit: Optional[int] = typer.Option(
        None,
        "--limit",
        help="Limit number of files to process (for testing)",
    ),
    workers: Optional[int] = typer.Option(
        None,
        "--workers",
        "-j",
        help="Number of parallel workers (default: number of CPU cores)",
    ),
    no_docling: bool = typer.Option(
        False,
        "--no-docling",
        help="Disable Docling extractor (reduces memory usage from ~10GB to ~100MB per worker)",
    ),
):
    """
    Phase 1: Extract text from documents.

    Extracts text from PDFs, Office documents, and text files using
    Docling (primary), pypdf (fallback), and plain text extractors.
    """
    try:
        from .pipeline import ExtractionPipeline

        # Load config
        if config_file:
            config = LucienSettings.load_from_yaml(config_file)
        else:
            config = LucienSettings.load()

        # Override paths if provided
        if db:
            config.index_db = db
        if output_dir:
            config.extracted_text_dir = output_dir

        # Override extraction settings
        if no_docling:
            config.extraction.use_docling = False

        # Ensure directories exist
        config.ensure_directories()

        # Initialize database
        database = Database(config.index_db)

        # Create extraction run
        run_id = database.create_run("extract", config.model_dump(mode="json"))

        console.print(f"\n[bold cyan]Starting text extraction[/]")
        console.print(f"[bold cyan]Database:[/] {config.index_db}")
        console.print(f"[bold cyan]Output:[/] {config.extracted_text_dir}")
        if limit:
            console.print(f"[yellow]Limit: Processing first {limit} files[/]")

        # Initialize pipeline
        pipeline = ExtractionPipeline(config, database)

        # Count files to process (for progress bar)
        total_files = pipeline.count_files_for_extraction(force=force)
        if limit:
            total_files = min(total_files, limit)

        # Get diagnostic counts
        previously_extracted = database.count_previously_extracted_files()
        skip_extension_count = database.count_files_with_skip_extensions(config.extraction.skip_extensions)
        total_in_db = database.get_stats()["total_files"]

        # Show diagnostic information
        console.print(f"\n[bold cyan]Database Summary:[/]")
        console.print(f"  Total files in database: {total_in_db:,}")
        console.print(f"  Previously extracted: {previously_extracted:,}")
        console.print(f"  Filtered by skip extensions: {skip_extension_count:,}")
        console.print(f"  [bold]Files to process: {total_files:,}[/]")

        if total_files == 0:
            console.print("\n[green]✓ No files need extraction[/]")
            database.complete_run(run_id)
            sys.exit(0)

        # Determine number of workers
        import os
        if workers is None:
            workers = os.cpu_count() or 1
        workers = max(1, min(workers, os.cpu_count() or 1))  # Clamp between 1 and CPU count

        console.print(f"\n[cyan]Parallel workers: {workers}[/]")
        if force:
            console.print("[yellow]Force mode: Re-extracting all files (ignoring previous extractions)[/]")

        # Show extractor configuration
        if config.extraction.use_docling:
            console.print("[cyan]Using Docling (high quality, ~2-5GB RAM per worker)[/]")
            console.print("[cyan]Workers restart every 20 files to prevent memory accumulation[/]")
            console.print("[yellow]Note: Complex PDFs may take 5-10 minutes to process[/]")
        else:
            console.print("[yellow]Docling disabled - using pypdf/vision-ocr (~100MB RAM per worker)[/]")

        console.print("[yellow]Using subprocess isolation to prevent memory leaks[/]\n")

        # Extract files with progress bar (process in parallel subprocesses for memory isolation)
        # Track detailed stats with reasons
        stats = {
            "success": 0,
            "success_methods": {},  # method -> count
            "failed": 0,
            "failed_reasons": {},  # reason -> count
            "skipped": 0,
            "skipped_reasons": {},  # reason -> count
        }
        batch_size = 100  # Process 100 files at a time

        def categorize_reason(error_msg: str) -> str:
            """Categorize an error message into a displayable reason."""
            if not error_msg:
                return "Unknown"
            # Categorize common patterns
            if "in skip list" in error_msg:
                # Extract extension from "Extension .jpg in skip list"
                match = re.search(r'Extension (\.\w+)', error_msg)
                if match:
                    return f"Skipped: {match.group(1)} in skip list"
                return "Skipped: Extension in skip list"
            elif "No extractor available" in error_msg:
                return "Skipped: No extractor available"
            elif "Docling timed out" in error_msg:
                return "Failed: Docling timeout (hung on complex PDF)"
            elif "All extractors failed" in error_msg:
                # Try to extract the actual error
                match = re.search(r'Last error: (.+)', error_msg)
                if match:
                    last_error = match.group(1)[:60]  # Truncate long errors
                    return f"Failed: {last_error}"
                return "Failed: All extractors failed"
            elif "Worker hung" in error_msg:
                return "Failed: Worker timeout"
            elif "Worker error" in error_msg:
                return "Failed: Worker error"
            else:
                # Truncate long error messages
                return f"Failed: {error_msg[:60]}"
        
        # Import worker function
        from .extract_worker import extract_file_worker

        # Prepare config paths for subprocess workers
        config_file_path = None
        if config_file:
            config_file_path = config_file
        elif hasattr(config, '_config_file_path'):
            config_file_path = config._config_file_path

        # Set up multiprocessing
        import multiprocessing
        if multiprocessing.get_start_method(allow_none=True) != 'spawn':
            try:
                multiprocessing.set_start_method('spawn', force=True)
            except RuntimeError:
                pass  # Already set

        # Import pool worker function
        from .extract_worker import extract_file_for_pool
        
        # Test that worker function is importable and callable
        try:
            # Just verify it's a function
            if not callable(extract_file_for_pool):
                raise ValueError("extract_file_for_pool is not callable")
        except Exception as e:
            console.print(f"[bold red]Error: Failed to import worker function: {e}[/]")
            sys.exit(1)

        # Create worker status display
        worker_status = {}  # worker_id -> (file_name, status, elapsed_time)

        def render_worker_status() -> Panel:
            """Render current status of all workers."""
            # Create table showing worker status
            table = Table.grid(padding=(0, 2))
            table.add_column("Worker", style="cyan", width=8)
            table.add_column("Status", style="yellow", width=15)
            table.add_column("File", style="white", width=55)
            table.add_column("Time", style="dim", width=10)

            # Show status for each worker slot
            for worker_id in range(workers):
                if worker_id in worker_status:
                    file_name, status, elapsed = worker_status[worker_id]
                    # Normalize status - remove "(slow)" suffix and handle it via color
                    is_slow = "(slow)" in status
                    base_status = status.replace(" (slow)", "").replace("(slow)", "")

                    status_color = {
                        "processing": "yellow" if not is_slow else "yellow3",
                        "completed": "green",
                        "hung": "red",
                        "idle": "dim"
                    }.get(base_status, "white")

                    # Truncate file name to fit column
                    display_name = file_name[:53] + "..." if len(file_name) > 53 else file_name

                    # Format time with indicator for slow tasks
                    time_str = f"{elapsed:.1f}s" if elapsed else "--"
                    if is_slow and elapsed:
                        time_str = f"[yellow]{time_str}[/]"

                    table.add_row(
                        f"#{worker_id+1}",
                        f"[{status_color}]{base_status}[/]",
                        display_name,
                        time_str
                    )
                else:
                    table.add_row(f"#{worker_id+1}", "[dim]idle[/]", "--", "--")

            # Overall stats with breakdowns
            total_completed = stats["success"] + stats["failed"] + stats["skipped"]
            overall_pct = (total_completed / total_files * 100) if total_files > 0 else 0

            # Build detailed status text
            status_lines = [
                Text(f"Overall: {total_completed:,}/{total_files:,} ({overall_pct:.1f}%) | "
                     f"Success: {stats['success']:,} | Failed: {stats['failed']:,} | Skipped: {stats['skipped']:,}")
            ]

            # Show top 3 success methods if any
            if stats["success_methods"]:
                top_methods = sorted(stats["success_methods"].items(), key=lambda x: x[1], reverse=True)[:3]
                methods_str = ", ".join([f"{method}: {count}" for method, count in top_methods])
                status_lines.append(Text(f"  Methods: {methods_str}", style="dim green"))

            # Show top 3 skip reasons if any
            if stats["skipped_reasons"]:
                top_skips = sorted(stats["skipped_reasons"].items(), key=lambda x: x[1], reverse=True)[:3]
                skips_str = ", ".join([f"{reason.replace('Skipped: ', '')}: {count}" for reason, count in top_skips])
                status_lines.append(Text(f"  Skip: {skips_str}", style="dim yellow"))

            # Show top 3 fail reasons if any
            if stats["failed_reasons"]:
                top_fails = sorted(stats["failed_reasons"].items(), key=lambda x: x[1], reverse=True)[:3]
                fails_str = ", ".join([f"{reason.replace('Failed: ', '')[:30]}: {count}" for reason, count in top_fails])
                status_lines.append(Text(f"  Fail: {fails_str}", style="dim red"))

            return Panel(
                Group(
                    table,
                    Text(""),  # Spacing
                    *status_lines
                ),
                title="Worker Status",
                border_style="cyan"
            )
        
        # Use Live to show both progress and worker status together
        def render_display() -> Group:
            """Render both progress and worker status."""
            # Create a simple progress indicator
            total_completed = stats["success"] + stats["failed"] + stats["skipped"]
            overall_pct = (total_completed / total_files * 100) if total_files > 0 else 0
            progress_text = Text(f"Progress: {total_completed:,}/{total_files:,} ({overall_pct:.1f}%)", style="cyan")
            
            return Group(
                progress_text,
                render_worker_status()
            )
        
        with Live(render_display(), console=console, refresh_per_second=4, screen=False) as live:
            # Use a continuous queue model: create ONE pool that persists, feed tasks continuously
            # Workers pick up new tasks as soon as they finish, maximizing utilization
            import queue as queue_module
            from collections import deque

            # Restart workers after N files to prevent memory accumulation
            # This is critical for Docling which loads heavy ML models
            # Workers grow from ~2GB -> ~5GB over 20 files, so restart frequently
            # The timeout is long enough (10 min) that slow PDFs won't be interrupted
            if config.extraction.use_docling:
                maxtasksperchild = 20  # Restart worker after 20 files to keep memory in check
            else:
                maxtasksperchild = 200  # Can process more files without Docling

            with multiprocessing.Pool(processes=workers, maxtasksperchild=maxtasksperchild) as pool:
                # Track active jobs: async_result -> (file_info, submission_time, worker_slot)
                active_jobs = {}  # Map async_result -> (file_info, submission_time, worker_slot)
                worker_assignments = {}  # Map async_result -> worker_slot
                next_worker_slot = 0
                results_received = 0
                # Docling can be slow on complex PDFs (OCR, tables, etc.)
                # 10 minutes should be enough for even the most complex documents
                HUNG_WORKER_TIMEOUT = 600.0  # 10 minutes - if a worker takes longer, consider it hung
                
                # Create a queue of pending tasks (file_info dicts)
                task_queue = deque()
                
                # Function to submit next task to an available worker
                def submit_next_task():
                    """Submit the next task from the queue to the pool."""
                    if not task_queue:
                        return None
                    
                    file_info = task_queue.popleft()
                    pool_arg = (file_info, config_file_path, config.index_db, config.extracted_text_dir)
                    async_result = pool.apply_async(extract_file_for_pool, args=(pool_arg,))
                    
                    # Assign to a worker slot (round-robin)
                    nonlocal next_worker_slot
                    worker_slot = next_worker_slot % workers
                    next_worker_slot += 1
                    submission_time = time.time()
                    
                    active_jobs[async_result] = (file_info, submission_time, worker_slot)
                    worker_assignments[async_result] = worker_slot
                    
                    # Update worker status to show it's processing
                    file_path = Path(file_info["path"])
                    worker_status[worker_slot] = (file_path.name, "processing", 0.0)
                    
                    return async_result
                
                # Pre-fill queue with initial batch and start workers
                # Load enough tasks to keep workers busy (2-3x worker count)
                initial_queue_size = workers * 3
                batch_iterator = pipeline.iter_files_for_extraction(force=force, limit=limit, batch_size=batch_size)
                
                # Load initial batches into queue
                for batch in batch_iterator:
                    for file_info in batch:
                        task_queue.append(file_info)
                    if len(task_queue) >= initial_queue_size:
                        break
                
                # Start initial workers (fill all worker slots)
                for _ in range(min(workers, len(task_queue))):
                    submit_next_task()
                
                # Main processing loop: continuously check for completed jobs and submit new ones
                loop_iterations = 0
                batch_start_time = time.time()
                batches_loaded = 1
                
                while active_jobs or task_queue:
                    loop_iterations += 1
                    current_time = time.time()
                    
                    # Load more batches if queue is getting low (keep it at least 2x workers)
                    if len(task_queue) < workers * 2:
                        try:
                            batch = next(batch_iterator)
                            for file_info in batch:
                                task_queue.append(file_info)
                            batches_loaded += 1
                        except StopIteration:
                            pass  # No more batches, continue processing what's in queue
                    
                    # Check for completed results and immediately assign new work
                    completed_results = []
                    hung_workers = []
                    
                    for async_result in list(active_jobs.keys()):
                        if async_result.ready():
                            try:
                                file_info, result_dict = async_result.get(timeout=0)
                                completed_results.append((async_result, file_info, result_dict))
                            except multiprocessing.TimeoutError:
                                pass  # Shouldn't happen with timeout=0
                            except Exception as e:
                                # Only log actual errors, not routine exceptions
                                import sys
                                if "Error retrieving result" not in str(e):
                                    print(f"ERROR: Error getting result: {type(e).__name__}: {e}", file=sys.stderr, flush=True)
                                # Mark as failed
                                if async_result in active_jobs:
                                    file_info, _, _ = active_jobs[async_result]
                                    result_dict = {
                                        "status": "failed",
                                        "method": "unknown",
                                        "output_path": None,
                                        "error": f"Error retrieving result: {type(e).__name__}: {e}",
                                    }
                                    completed_results.append((async_result, file_info, result_dict))
                        else:
                            # Check if this worker is hung (taking too long) and update elapsed time
                            if async_result in active_jobs:
                                file_info, submission_time, worker_slot = active_jobs[async_result]
                                elapsed = current_time - submission_time
                                
                                # Update worker status with current elapsed time
                                if async_result in worker_assignments:
                                    file_path = Path(file_info["path"])
                                    # Mark as hung if taking too long (but still processing)
                                    if elapsed > HUNG_WORKER_TIMEOUT:
                                        worker_status[worker_slot] = (file_path.name, "hung", elapsed)
                                        hung_workers.append((async_result, file_info, elapsed))
                                    elif elapsed > 120.0:  # Show warning if taking > 2 minutes
                                        worker_status[worker_slot] = (file_path.name, "processing (slow)", elapsed)
                                    else:
                                        worker_status[worker_slot] = (file_path.name, "processing", elapsed)
                    
                    # Handle hung workers - mark as failed and free up the worker slot
                    for async_result, file_info, elapsed in hung_workers:
                        file_path = Path(file_info["path"])
                        # Only log if truly hung (not just slow)
                        if elapsed > HUNG_WORKER_TIMEOUT:
                            import sys
                            print(f"WARNING: Worker hung on {file_path.name[:80]} after {elapsed:.1f}s - marking as failed", file=sys.stderr, flush=True)
                        # Try to get the result one more time (non-blocking)
                        try:
                            if async_result.ready():
                                file_info, result_dict = async_result.get(timeout=0)
                                completed_results.append((async_result, file_info, result_dict))
                            else:
                                # Worker is truly hung - mark as failed
                                result_dict = {
                                    "status": "failed",
                                    "method": "unknown",
                                    "output_path": None,
                                    "error": f"Worker hung after {elapsed:.1f}s",
                                }
                                completed_results.append((async_result, file_info, result_dict))
                        except Exception as e:
                            # Mark as failed
                            result_dict = {
                                "status": "failed",
                                "method": "unknown",
                                "output_path": None,
                                "error": f"Worker error: {type(e).__name__}: {e}",
                            }
                            completed_results.append((async_result, file_info, result_dict))
                    
                    # Process completed results and immediately assign new work
                    for async_result, file_info, result_dict in completed_results:
                        results_received += 1
                        file_path = Path(file_info["path"])
                        
                        # Free up the worker slot and remove from active jobs
                        if async_result in worker_assignments:
                            worker_slot = worker_assignments[async_result]
                            if async_result in active_jobs:
                                _, submission_time, _ = active_jobs[async_result]
                                elapsed = current_time - submission_time
                                worker_status[worker_slot] = (file_path.name, "completed", elapsed)
                            del worker_assignments[async_result]
                        if async_result in active_jobs:
                            del active_jobs[async_result]
                        
                        # Immediately assign new work to this worker slot if tasks are available
                        if task_queue:
                            submit_next_task()
                        
                        # Removed verbose debug logging to avoid screen tear with Rich display
                        
                        # Record result in database
                        try:
                            database.record_extraction(
                                file_id=file_info["id"],
                                run_id=run_id,
                                method=result_dict["method"],
                                status=result_dict["status"],
                                output_path=result_dict["output_path"],
                                error=result_dict["error"]
                            )
                        except Exception as e:
                            console.print(f"[yellow]Warning: Failed to record extraction for {file_path.name}: {e}[/]")

                        # Update stats with reasons
                        status = result_dict["status"]
                        stats[status] += 1

                        if status == "success":
                            method = result_dict["method"]
                            stats["success_methods"][method] = stats["success_methods"].get(method, 0) + 1
                        elif status == "skipped":
                            reason = categorize_reason(result_dict.get("error", "Unknown"))
                            stats["skipped_reasons"][reason] = stats["skipped_reasons"].get(reason, 0) + 1
                        elif status == "failed":
                            reason = categorize_reason(result_dict.get("error", "Unknown"))
                            stats["failed_reasons"][reason] = stats["failed_reasons"].get(reason, 0) + 1
                    
                    # Update worker status display (less frequently to avoid redraw issues)
                    if completed_results or loop_iterations % 10 == 0:  # Update when results arrive or every 10 iterations
                        live.update(render_display())
                    
                    # Sleep to allow workers to make progress and avoid busy-waiting
                    if completed_results:
                        time.sleep(0.05)  # Short sleep when processing results
                    else:
                        time.sleep(0.1)  # Short sleep when waiting for results
                
                # Wait for any remaining active jobs to complete
                while active_jobs:
                    current_time = time.time()
                    completed_results = []
                    
                    for async_result in list(active_jobs.keys()):
                        if async_result.ready():
                            try:
                                file_info, result_dict = async_result.get(timeout=0)
                                completed_results.append((async_result, file_info, result_dict))
                            except Exception as e:
                                # Only log actual errors
                                import sys
                                print(f"ERROR: Error getting final result: {type(e).__name__}: {e}", file=sys.stderr, flush=True)
                                if async_result in active_jobs:
                                    file_info, _, _ = active_jobs[async_result]
                                    result_dict = {
                                        "status": "failed",
                                        "method": "unknown",
                                        "output_path": None,
                                        "error": f"Error retrieving result: {type(e).__name__}: {e}",
                                    }
                                    completed_results.append((async_result, file_info, result_dict))
                    
                    # Process completed results
                    for async_result, file_info, result_dict in completed_results:
                        results_received += 1
                        file_path = Path(file_info["path"])
                        
                        if async_result in worker_assignments:
                            worker_slot = worker_assignments[async_result]
                            if async_result in active_jobs:
                                _, submission_time, _ = active_jobs[async_result]
                                elapsed = current_time - submission_time
                                worker_status[worker_slot] = (file_path.name, "completed", elapsed)
                            del worker_assignments[async_result]
                        if async_result in active_jobs:
                            del active_jobs[async_result]
                        
                        # Record result in database
                        try:
                            database.record_extraction(
                                file_id=file_info["id"],
                                run_id=run_id,
                                method=result_dict["method"],
                                status=result_dict["status"],
                                output_path=result_dict["output_path"],
                                error=result_dict["error"]
                            )
                        except Exception as e:
                            console.print(f"[yellow]Warning: Failed to record extraction for {file_path.name}: {e}[/]")

                        # Update stats with reasons
                        status = result_dict["status"]
                        stats[status] += 1

                        if status == "success":
                            method = result_dict["method"]
                            stats["success_methods"][method] = stats["success_methods"].get(method, 0) + 1
                        elif status == "skipped":
                            reason = categorize_reason(result_dict.get("error", "Unknown"))
                            stats["skipped_reasons"][reason] = stats["skipped_reasons"].get(reason, 0) + 1
                        elif status == "failed":
                            reason = categorize_reason(result_dict.get("error", "Unknown"))
                            stats["failed_reasons"][reason] = stats["failed_reasons"].get(reason, 0) + 1
                    
                    if completed_results:
                        live.update(render_display())
                    else:
                        time.sleep(0.1)
                
                # Force garbage collection
                gc.collect()

        # Display comprehensive statistics
        console.print(f"\n[bold green]✓ Extraction complete[/]\n")

        # Create summary table
        summary_table = Table(title="Extraction Summary", show_header=True, header_style="bold cyan", width=100)
        summary_table.add_column("Category", style="cyan", width=20)
        summary_table.add_column("Count", justify="right", style="white", width=10)
        summary_table.add_column("Details", style="dim", width=65)

        # Add overall stats
        total_processed = stats['success'] + stats['failed'] + stats['skipped']
        summary_table.add_row(
            "[bold]Total Processed[/]",
            f"[bold]{total_processed:,}[/]",
            ""
        )

        if previously_extracted > 0:
            summary_table.add_row(
                "Previously Extracted",
                f"{previously_extracted:,}",
                "[dim]Files already successfully extracted in prior runs[/]"
            )

        # Success breakdown
        if stats['success'] > 0:
            summary_table.add_row(
                "[green]Successful[/]",
                f"[green]{stats['success']:,}[/]",
                ""
            )
            # Show method breakdown
            for method, count in sorted(stats['success_methods'].items(), key=lambda x: x[1], reverse=True):
                summary_table.add_row(
                    "",
                    f"[dim]{count:,}[/]",
                    f"[dim green]→ via {method}[/]"
                )

        # Skipped breakdown
        if stats['skipped'] > 0:
            summary_table.add_row(
                "[yellow]Skipped[/]",
                f"[yellow]{stats['skipped']:,}[/]",
                ""
            )
            # Show skip reasons
            for reason, count in sorted(stats['skipped_reasons'].items(), key=lambda x: x[1], reverse=True):
                summary_table.add_row(
                    "",
                    f"[dim]{count:,}[/]",
                    f"[dim yellow]→ {reason.replace('Skipped: ', '')}[/]"
                )

        # Failed breakdown
        if stats['failed'] > 0:
            summary_table.add_row(
                "[red]Failed[/]",
                f"[red]{stats['failed']:,}[/]",
                ""
            )
            # Show fail reasons
            for reason, count in sorted(stats['failed_reasons'].items(), key=lambda x: x[1], reverse=True):
                summary_table.add_row(
                    "",
                    f"[dim]{count:,}[/]",
                    f"[dim red]→ {reason.replace('Failed: ', '')}[/]"
                )

        console.print(summary_table)
        console.print()

        # Complete run
        database.complete_run(run_id)

    except Exception as e:
        console.print(f"[bold red]Error:[/] {e}")
        if 'database' in locals() and 'run_id' in locals():
            database.complete_run(run_id, error=str(e))
        sys.exit(1)


@app.command()
def label(
    db: Optional[Path] = typer.Option(
        None,
        "--db",
        help="Database path (default: from config)",
    ),
    config_file: Optional[Path] = typer.Option(
        None,
        "--config",
        "-c",
        help="Config file path",
    ),
    model: Optional[str] = typer.Option(
        None,
        "--model",
        help="Override default model name",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Re-label files that were already labeled",
    ),
    limit: Optional[int] = typer.Option(
        None,
        "--limit",
        help="Limit number of files to label (for testing)",
    ),
    no_escalate: bool = typer.Option(
        False,
        "--no-escalate",
        help="Disable automatic model escalation",
    ),
):
    """
    Phase 2: AI labeling with LLM.

    Uses LM Studio to label and categorize documents based on their
    extracted text. Requires LM Studio to be running with a model loaded.
    """
    try:
        from .llm import LabelingPipeline

        # Load config
        if config_file:
            config = LucienSettings.load_from_yaml(config_file)
        else:
            config = LucienSettings.load()

        # Override settings
        if db:
            config.index_db = db
        if model:
            config.llm.default_model = model

        # Ensure directories exist
        config.ensure_directories()

        # Initialize database
        database = Database(config.index_db)

        # Initialize pipeline
        pipeline = LabelingPipeline(config, database)

        # Check LM Studio connection
        console.print(f"\n[bold cyan]Checking LM Studio connection...[/]")
        success, message = pipeline.check_lm_studio_connection()
        if not success:
            console.print(f"[bold red]Error:[/] {message}")
            console.print("\n[yellow]To fix this:[/]")
            console.print("1. Start LM Studio")
            console.print("2. Load a model (e.g., qwen2.5-7b-instruct)")
            console.print("3. Enable the local server in LM Studio settings")
            sys.exit(1)

        console.print(f"[green]✓[/] {message}")

        # Count files to process
        total_files = pipeline.count_files_for_labeling(force=force)
        if limit:
            total_files = min(total_files, limit)

        console.print(f"\n[bold cyan]Starting AI labeling[/]")
        console.print(f"[bold cyan]Database:[/] {config.index_db}")
        console.print(f"[bold cyan]Default model:[/] {config.llm.default_model}")
        console.print(f"[bold cyan]Escalation model:[/] {config.llm.escalation_model}")
        console.print(f"[bold cyan]Escalation threshold:[/] {config.llm.escalation_threshold}")
        if limit:
            console.print(f"[yellow]Limit: Processing first {limit} files[/]")
        if no_escalate:
            console.print("[yellow]Escalation disabled[/]")
        if force:
            console.print("[yellow]Force mode: Re-labeling all files[/]")

        if total_files == 0:
            console.print("\n[green]✓ No files need labeling[/]")
            console.print("[dim]All extracted files already have labels. Use --force to re-label.[/]")
            sys.exit(0)

        console.print(f"\n[bold]Files to label: {total_files:,}[/]\n")

        # Create labeling run
        run_id = database.create_run("label", config.model_dump(mode="json"))

        # Get files to label
        files = pipeline.get_files_for_labeling(force=force, limit=limit)

        # Track statistics
        stats = {
            "success": 0,
            "failed": 0,
            "escalated": 0,
            "by_doc_type": {},
            "errors": [],
        }

        # Track last result for display
        last_result = {
            "file": None,
            "label": None,  # Full LabelOutput object
            "escalated": False,
            "error": None,
        }
        current_file = {"name": None}

        def render_label_status() -> Panel:
            """Render current labeling status."""
            # Main status table
            table = Table.grid(padding=(0, 2))
            table.add_column("Label", style="cyan", width=18)
            table.add_column("Value", style="white", width=90)

            # Current file being processed
            if current_file["name"]:
                display_name = current_file["name"][:85] + "..." if len(current_file["name"]) > 85 else current_file["name"]
                table.add_row("Processing:", f"[yellow]{display_name}[/]")
            else:
                table.add_row("Processing:", "[dim]waiting...[/]")

            # Last result - detailed view
            if last_result["file"]:
                display_name = last_result["file"][:85] + "..." if len(last_result["file"]) > 85 else last_result["file"]

                if last_result["error"]:
                    table.add_row("", "")  # Spacer
                    table.add_row("[bold]Last Result:[/]", f"[red]{display_name}[/]")
                    table.add_row("Error:", f"[red]{last_result['error'][:80]}[/]")
                else:
                    label = last_result["label"]
                    escalated = last_result["escalated"]

                    # Confidence color
                    conf = label.confidence
                    if conf >= 0.85:
                        conf_style = "bold green"
                    elif conf >= 0.7:
                        conf_style = "green"
                    else:
                        conf_style = "yellow"

                    table.add_row("", "")  # Spacer
                    table.add_row("[bold]Last Result:[/]", f"[green]{display_name}[/]")

                    # Type and confidence with escalation marker
                    escalate_marker = " [yellow](escalated)[/]" if escalated else ""
                    table.add_row("Type:", f"[bold]{label.doc_type}[/]{escalate_marker}")
                    table.add_row("Confidence:", f"[{conf_style}]{conf:.0%}[/]")

                    # Title
                    title_display = label.title[:85] + "..." if len(label.title) > 85 else label.title
                    table.add_row("Title:", title_display)

                    # Canonical filename
                    filename_display = label.canonical_filename[:85] + "..." if len(label.canonical_filename) > 85 else label.canonical_filename
                    table.add_row("Filename:", f"[dim]{filename_display}[/]")

                    # Target path
                    table.add_row("Target:", f"[cyan]{label.target_group_path}[/]")

                    # Date and issuer on same line if both present
                    meta_parts = []
                    if label.date:
                        meta_parts.append(f"[white]{label.date}[/]")
                    if label.issuer:
                        meta_parts.append(f"[white]{label.issuer}[/]")
                    if meta_parts:
                        table.add_row("Date/Issuer:", " | ".join(meta_parts))

                    # Tags
                    if label.suggested_tags:
                        tags_str = ", ".join(label.suggested_tags[:6])
                        if len(label.suggested_tags) > 6:
                            tags_str += f" (+{len(label.suggested_tags) - 6} more)"
                        table.add_row("Tags:", f"[magenta]{tags_str}[/]")

                    # Why (reasoning) - truncated
                    why_display = label.why[:100] + "..." if len(label.why) > 100 else label.why
                    table.add_row("Why:", f"[dim italic]{why_display}[/]")
            else:
                table.add_row("", "")
                table.add_row("[bold]Last Result:[/]", "[dim]--[/]")

            # Overall stats
            total_completed = stats["success"] + stats["failed"]
            overall_pct = (total_completed / total_files * 100) if total_files > 0 else 0

            status_lines = [
                Text(""),  # Spacer
                Text(f"Progress: {total_completed:,}/{total_files:,} ({overall_pct:.1f}%) | "
                     f"Success: {stats['success']:,} | Failed: {stats['failed']:,} | Escalated: {stats['escalated']:,}",
                     style="bold")
            ]

            # Show top doc types if any
            if stats["by_doc_type"]:
                top_types = sorted(stats["by_doc_type"].items(), key=lambda x: x[1], reverse=True)[:5]
                types_str = ", ".join([f"{dtype}: {count}" for dtype, count in top_types])
                status_lines.append(Text(f"  Types: {types_str}", style="dim green"))

            return Panel(
                Group(
                    table,
                    *status_lines
                ),
                title="Labeling Status",
                border_style="cyan"
            )

        with Live(render_label_status(), console=console, refresh_per_second=4, screen=False) as live:
            for file_info in files:
                file_path = Path(file_info["path"])
                current_file["name"] = file_path.name
                live.update(render_label_status())

                # Label the file
                label_result, escalated, error = pipeline.label_file(
                    file_info,
                    run_id,
                    use_escalation=not no_escalate,
                )

                # Update last result
                last_result["file"] = file_path.name
                last_result["error"] = error

                if error:
                    stats["failed"] += 1
                    stats["errors"].append((file_path.name, error))
                    last_result["label"] = None
                    last_result["escalated"] = False
                else:
                    stats["success"] += 1
                    if escalated:
                        stats["escalated"] += 1
                    # Track doc types
                    doc_type = label_result.doc_type
                    stats["by_doc_type"][doc_type] = stats["by_doc_type"].get(doc_type, 0) + 1
                    last_result["label"] = label_result
                    last_result["escalated"] = escalated

                live.update(render_label_status())

        # Complete run
        database.complete_run(run_id)

        # Display results
        console.print(f"\n[bold green]✓ Labeling complete[/]\n")

        # Summary table
        summary_table = Table(title="Labeling Summary", show_header=True, header_style="bold cyan")
        summary_table.add_column("Metric", style="cyan")
        summary_table.add_column("Count", justify="right", style="green")

        summary_table.add_row("Total Processed", str(stats["success"] + stats["failed"]))
        summary_table.add_row("[green]Successful[/]", f"[green]{stats['success']}[/]")
        summary_table.add_row("[yellow]Escalated[/]", f"[yellow]{stats['escalated']}[/]")
        summary_table.add_row("[red]Failed[/]", f"[red]{stats['failed']}[/]")

        console.print(summary_table)

        # Doc type breakdown
        if stats["by_doc_type"]:
            console.print("\n[bold cyan]Document Types:[/]")
            sorted_types = sorted(stats["by_doc_type"].items(), key=lambda x: x[1], reverse=True)
            for doc_type, count in sorted_types[:10]:  # Top 10
                console.print(f"  {doc_type}: {count}")
            if len(sorted_types) > 10:
                console.print(f"  ... and {len(sorted_types) - 10} more types")

        # Show errors if any
        if stats["errors"]:
            console.print(f"\n[bold red]Errors ({len(stats['errors'])}):[/]")
            for filename, error in stats["errors"][:5]:
                console.print(f"  {filename}: {error[:60]}")
            if len(stats["errors"]) > 5:
                console.print(f"  ... and {len(stats['errors']) - 5} more errors")

        # Show sample results
        console.print("\n[bold cyan]Sample Results:[/]")
        labeling_stats = database.get_labeling_stats(run_id)
        console.print(f"  Average confidence: {labeling_stats['confidence']['avg']:.2f}")
        console.print(f"  Low confidence (<0.7): {labeling_stats['low_confidence_count']}")

    except Exception as e:
        console.print(f"[bold red]Error:[/] {e}")
        import traceback
        traceback.print_exc()
        if 'database' in locals() and 'run_id' in locals():
            database.complete_run(run_id, error=str(e))
        sys.exit(1)


@app.command()
def plan(
    db: Optional[Path] = typer.Option(
        None,
        "--db",
        help="Database path (default: from config)",
    ),
    config_file: Optional[Path] = typer.Option(
        None,
        "--config",
        "-c",
        help="Config file path",
    ),
    output_dir: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output directory for plan files",
    ),
):
    """
    Phase 3: Generate materialization plan (NOT YET IMPLEMENTED).

    Generates plan.jsonl and plan.csv for review.
    """
    console.print("[yellow]⚠ Plan generation not yet implemented[/]")
    console.print("This will be part of Milestone 4 (v0.4)")
    sys.exit(1)


@app.command()
def materialize(
    plan_file: Path = typer.Argument(
        ...,
        help="Plan file (JSONL or CSV) to materialize",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
    ),
    staging: Optional[Path] = typer.Option(
        None,
        "--staging",
        help="Staging directory (default: from config)",
    ),
    mode: Optional[str] = typer.Option(
        None,
        "--mode",
        help="Copy mode: 'copy' or 'hardlink' (default: from config)",
    ),
    apply_tags: bool = typer.Option(
        True,
        "--apply-tags/--no-tags",
        help="Apply macOS Finder tags",
    ),
    config_file: Optional[Path] = typer.Option(
        None,
        "--config",
        "-c",
        help="Config file path",
    ),
):
    """
    Phase 4: Materialize staging mirror (NOT YET IMPLEMENTED).

    Creates staging library from approved plan.
    """
    console.print("[yellow]⚠ Materialization not yet implemented[/]")
    console.print("This will be part of Milestone 4 (v0.4)")
    sys.exit(1)


def main_cli():
    """Main CLI entry point."""
    app()


if __name__ == "__main__":
    main_cli()
