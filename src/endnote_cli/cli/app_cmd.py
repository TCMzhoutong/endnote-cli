"""App-level commands: ping, info."""

import typer
from typing import Optional

from endnote_cli.core.config import resolve_library_path
from endnote_cli.core.reader import EndnoteLibrary

app_cmd = typer.Typer()


def _get_lib(library: Optional[str]) -> EndnoteLibrary:
    path = resolve_library_path(library)
    return EndnoteLibrary(path)


@app_cmd.command()
def ping(
    library: Optional[str] = typer.Option(None, "--library", "-l", help="Library name or path"),
):
    """Check if library is accessible."""
    try:
        lib = _get_lib(library)
        with lib:
            _ = lib.count_refs()
        typer.echo(f"OK: {lib.path}")
    except Exception as e:
        typer.echo(f"FAIL: {e}", err=True)
        raise typer.Exit(1)


@app_cmd.command()
def info(
    library: Optional[str] = typer.Option(None, "--library", "-l", help="Library name or path"),
):
    """Print library summary info."""
    from rich.console import Console
    from rich.table import Table

    lib = _get_lib(library)
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
