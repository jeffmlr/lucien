"""
Lucien CLI using Typer.

Command-line interface for all pipeline stages.
"""

import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

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
        help="Create user config at ~/.config/lucien/config.yaml",
    ),
):
    """
    Initialize a configuration file with defaults.
    """
    try:
        config = LucienSettings()

        if user:
            output = Path.home() / ".config/lucien/config.yaml"

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
):
    """
    Phase 1: Extract text from documents (NOT YET IMPLEMENTED).

    Extracts text from PDFs and documents using Docling and other extractors.
    """
    console.print("[yellow]⚠ Text extraction not yet implemented[/]")
    console.print("This will be part of Milestone 2 (v0.2)")
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
