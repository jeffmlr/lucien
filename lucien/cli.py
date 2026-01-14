"""
Lucien CLI using Typer.

Command-line interface for all pipeline stages.
"""

import gc
import json
import logging
import multiprocessing
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

        # Ensure directories exist
        config.ensure_directories()

        # Initialize database
        database = Database(config.index_db)

        # Create extraction run
        run_id = database.create_run("extract", config.model_dump(mode="json"))

        console.print(f"\n[bold cyan]Starting text extraction[/]")
        console.print(f"[bold cyan]Database:[/] {config.index_db}")
        console.print(f"[bold cyan]Output:[/] {config.extracted_text_dir}")
        if force:
            console.print("[yellow]Force mode: Re-extracting all files[/]")
        if limit:
            console.print(f"[yellow]Limit: Processing first {limit} files[/]\n")

        # Initialize pipeline
        pipeline = ExtractionPipeline(config, database)

        # Count files to process (for progress bar)
        total_files = pipeline.count_files_for_extraction(force=force)
        if limit:
            total_files = min(total_files, limit)

        if total_files == 0:
            console.print("[green]✓ No files need extraction[/]")
            database.complete_run(run_id)
            sys.exit(0)

        # Determine number of workers
        import os
        if workers is None:
            workers = os.cpu_count() or 1
        workers = max(1, min(workers, os.cpu_count() or 1))  # Clamp between 1 and CPU count

        console.print(f"[cyan]Files to process: {total_files}[/]")
        console.print(f"[cyan]Parallel workers: {workers}[/]")
        console.print("[yellow]Using subprocess isolation to prevent memory leaks[/]\n")

        # Extract files with progress bar (process in parallel subprocesses for memory isolation)
        stats = {"success": 0, "failed": 0, "skipped": 0}
        batch_size = 100  # Process 100 files at a time
        
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
        import sys
        try:
            # Just verify it's a function
            if not callable(extract_file_for_pool):
                raise ValueError("extract_file_for_pool is not callable")
            print(f"DEBUG MAIN: Worker function imported successfully", file=sys.stderr, flush=True)
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
            table.add_column("Status", style="yellow", width=12)
            table.add_column("File", style="white", width=60)
            table.add_column("Time", style="dim", width=10)
            
            # Show status for each worker slot
            for worker_id in range(workers):
                if worker_id in worker_status:
                    file_name, status, elapsed = worker_status[worker_id]
                    status_color = {
                        "processing": "yellow",
                        "completed": "green",
                        "hung": "red",
                        "idle": "dim"
                    }.get(status, "white")
                    table.add_row(
                        f"#{worker_id+1}",
                        f"[{status_color}]{status}[/]",
                        file_name[:58] + "..." if len(file_name) > 58 else file_name,
                        f"{elapsed:.1f}s" if elapsed else "--"
                    )
                else:
                    table.add_row(f"#{worker_id+1}", "[dim]idle[/]", "--", "--")
            
            # Overall stats
            total_completed = stats["success"] + stats["failed"] + stats["skipped"]
            overall_pct = (total_completed / total_files * 100) if total_files > 0 else 0
            
            return Panel(
                Group(
                    table,
                    Text(f"\n[cyan]Overall: {total_completed:,}/{total_files:,} ({overall_pct:.1f}%) | "
                         f"Success: {stats['success']:,} | Failed: {stats['failed']:,} | Skipped: {stats['skipped']:,}[/]")
                ),
                title="[bold cyan]Worker Status[/]",
                border_style="cyan"
            )
        
        # Use Live to show both progress and worker status together
        def render_display() -> Group:
            """Render both progress and worker status."""
            # Create a simple progress indicator
            total_completed = stats["success"] + stats["failed"] + stats["skipped"]
            overall_pct = (total_completed / total_files * 100) if total_files > 0 else 0
            progress_text = Text(f"[cyan]Progress: {total_completed:,}/{total_files:,} ({overall_pct:.1f}%)[/]")
            
            return Group(
                progress_text,
                render_worker_status()
            )
        
        with Live(render_display(), console=console, refresh_per_second=2) as live:
            # Use a continuous queue model: create ONE pool that persists, feed tasks continuously
            # Workers pick up new tasks as soon as they finish, maximizing utilization
            import sys
            import queue as queue_module
            from collections import deque
            
            print(f"DEBUG MAIN: Creating persistent pool with {workers} workers", file=sys.stderr, flush=True)
            with multiprocessing.Pool(processes=workers) as pool:
                # Track active jobs: async_result -> (file_info, submission_time, worker_slot)
                active_jobs = {}  # Map async_result -> (file_info, submission_time, worker_slot)
                worker_assignments = {}  # Map async_result -> worker_slot
                next_worker_slot = 0
                results_received = 0
                HUNG_WORKER_TIMEOUT = 300.0  # 5 minutes - if a worker takes longer, consider it hung
                
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
                
                print(f"DEBUG MAIN: Started {len(active_jobs)} initial jobs, {len(task_queue)} tasks queued", file=sys.stderr, flush=True)
                
                # Main processing loop: continuously check for completed jobs and submit new ones
                loop_iterations = 0
                last_log_time = time.time()
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
                            if batches_loaded % 10 == 0:
                                print(f"DEBUG MAIN: Loaded {batches_loaded} batches, queue has {len(task_queue)} tasks", file=sys.stderr, flush=True)
                        except StopIteration:
                            pass  # No more batches, continue processing what's in queue
                    
                    # Log loop activity every 2 seconds
                    if current_time - last_log_time > 2.0:
                        print(f"DEBUG: Loop iteration #{loop_iterations}, {len(active_jobs)} active, {len(task_queue)} queued, {results_received} received", file=sys.stderr, flush=True)
                        last_log_time = current_time
                    
                    # Check for completed results and immediately assign new work
                    completed_results = []
                    hung_workers = []
                    
                    for async_result in list(active_jobs.keys()):
                        if async_result.ready():
                            try:
                                file_info, result_dict = async_result.get(timeout=0)
                                completed_results.append((async_result, file_info, result_dict))
                            except multiprocessing.TimeoutError:
                                print(f"DEBUG: Unexpected timeout getting result", file=sys.stderr, flush=True)
                            except Exception as e:
                                print(f"DEBUG: Error getting result: {type(e).__name__}: {e}", file=sys.stderr, flush=True)
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
                                    elif elapsed > 30.0:  # Show warning if taking > 30 seconds
                                        worker_status[worker_slot] = (file_path.name, "processing (slow)", elapsed)
                                    else:
                                        worker_status[worker_slot] = (file_path.name, "processing", elapsed)
                    
                    # Handle hung workers - mark as failed and free up the worker slot
                    for async_result, file_info, elapsed in hung_workers:
                        file_path = Path(file_info["path"])
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
                        
                        # Log every 100th result
                        if results_received % 100 == 0:
                            console.print(f"[dim]DEBUG: Received result #{results_received}: {file_path.name[:50]}[/]")
                        
                        # Record result in database
                        db_start = time.time()
                        try:
                            database.record_extraction(
                                file_id=file_info["id"],
                                run_id=run_id,
                                method=result_dict["method"],
                                status=result_dict["status"],
                                output_path=result_dict["output_path"],
                                error=result_dict["error"]
                            )
                            db_time = time.time() - db_start
                            if db_time > 0.1:  # Log slow DB writes
                                console.print(f"[dim]DEBUG: Slow DB write: {db_time:.2f}s for {file_path.name[:50]}[/]")
                        except Exception as e:
                            console.print(f"[yellow]Warning: Failed to record extraction for {file_path.name}: {e}[/]")

                        # Update stats
                        stats[result_dict["status"]] += 1
                    
                    # Update worker status display
                    if loop_iterations % 5 == 0 or completed_results:  # Update every 5 iterations or when results arrive
                        live.update(render_display())
                    
                    # Sleep to allow workers to make progress and avoid busy-waiting
                    if completed_results:
                        time.sleep(0.05)  # Short sleep when processing results
                    else:
                        time.sleep(0.1)  # Short sleep when waiting for results
                
                # Wait for any remaining active jobs to complete
                print(f"DEBUG MAIN: Waiting for {len(active_jobs)} remaining jobs to complete", file=sys.stderr, flush=True)
                while active_jobs:
                    current_time = time.time()
                    completed_results = []
                    
                    for async_result in list(active_jobs.keys()):
                        if async_result.ready():
                            try:
                                file_info, result_dict = async_result.get(timeout=0)
                                completed_results.append((async_result, file_info, result_dict))
                            except Exception as e:
                                print(f"DEBUG: Error getting final result: {type(e).__name__}: {e}", file=sys.stderr, flush=True)
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

                        # Update stats
                        stats[result_dict["status"]] += 1
                    
                    if completed_results:
                        live.update(render_display())
                    else:
                        time.sleep(0.1)
                
                # Force garbage collection
                gc.collect()

        # Display statistics
        console.print(f"\n[bold green]✓ Extraction complete[/]")
        console.print(f"  [green]Successful:[/] {stats['success']}")
        console.print(f"  [yellow]Skipped:[/] {stats['skipped']}")
        console.print(f"  [red]Failed:[/] {stats['failed']}")

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
        help="Model name to use (default: from config)",
    ),
):
    """
    Phase 2: AI labeling with LLM (NOT YET IMPLEMENTED).

    Uses LM Studio to label and categorize documents.
    """
    console.print("[yellow]⚠ AI labeling not yet implemented[/]")
    console.print("This will be part of Milestone 3 (v0.3)")
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
