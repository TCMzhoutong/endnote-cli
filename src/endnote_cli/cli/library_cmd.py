"""Library management commands: list, info, set-default, set-dir."""

import typer
from pathlib import Path
from typing import Optional

from endnote_cli.core.config import (
    find_libraries,
    get_library_dir,
    resolve_library_path,
    set_default_library,
    set_library_dir,
)

library_cmd = typer.Typer()


@library_cmd.command("list")
def list_libs(
    directory: Optional[str] = typer.Option(None, "--dir", "-d", help="Directory to scan (default: configured library_dir)"),
):
    """List all .enl files in the library directory."""
    from rich.console import Console
    from rich.table import Table

    libs = find_libraries(directory)
    lib_dir = directory or get_library_dir() or "."

    console = Console()

    if not libs:
        console.print(f"No .enl files found in: {lib_dir}")
        return

    table = Table(title=f"Libraries in {lib_dir}")
    table.add_column("#", justify="right", style="dim")
    table.add_column("Name")
    table.add_column("Path")
    table.add_column("Size", justify="right")

    for i, p in enumerate(libs, 1):
        size_mb = p.stat().st_size / (1024 * 1024)
        table.add_row(str(i), p.stem, str(p), f"{size_mb:.1f} MB")

    console.print(table)


@library_cmd.command()
def info(
    name: str = typer.Argument(..., help="Library name or path"),
):
    """Show info for a specific library."""
    from rich.console import Console
    from rich.table import Table
    from endnote_cli.core.reader import EndnoteLibrary

    path = resolve_library_path(name)
    lib = EndnoteLibrary(path)
    with lib:
        li = lib.get_info()

    console = Console()
    table = Table(title=f"Library: {li.path}", show_header=True)
    table.add_column("Metric", style="bold")
    table.add_column("Value", justify="right")

    table.add_row("Total references", str(li.total_refs))
    table.add_row("Trashed references", str(li.trashed_refs))
    table.add_row("Groups", str(li.groups_count))
    table.add_row("Group sets", str(li.group_sets_count))
    table.add_row("Tags", str(li.tags_count))
    table.add_row("PDFs attached", str(li.pdf_count))
    pdf_pct = f"{li.pdf_count / li.total_refs * 100:.1f}%" if li.total_refs else "N/A"
    table.add_row("PDF coverage", pdf_pct)
    table.add_row("DOIs present", str(li.doi_count))
    doi_pct = f"{li.doi_count / li.total_refs * 100:.1f}%" if li.total_refs else "N/A"
    table.add_row("DOI coverage", doi_pct)
    table.add_row("With abstract", str(li.refs_with_abstract))

    console.print(table)


@library_cmd.command("set-default")
def set_default(
    name_or_path: str = typer.Argument(..., help="Library name or full path to set as default"),
):
    """Set the default library."""
    # Resolve to verify it exists
    path = resolve_library_path(name_or_path)
    set_default_library(str(path))
    typer.echo(f"Default library set to: {path}")


@library_cmd.command("set-dir")
def set_dir(
    path: Path = typer.Argument(..., help="Directory containing .enl files", exists=True),
):
    """Set the library directory (where to look for .enl files)."""
    set_library_dir(str(path.resolve()))
    typer.echo(f"Library directory set to: {path.resolve()}")
