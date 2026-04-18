"""Tag commands: list, show."""

import typer
from typing import Optional

from endnote_cli.core.config import resolve_library_path
from endnote_cli.core.reader import EndnoteLibrary

tag_cmd = typer.Typer()


def _get_lib(library: Optional[str]) -> EndnoteLibrary:
    path = resolve_library_path(library)
    return EndnoteLibrary(path)


@tag_cmd.command("list")
def list_tags(
    library: Optional[str] = typer.Option(None, "--library", "-l", help="Library name or path"),
):
    """List all tags with name, color, and usage count."""
    from rich.console import Console
    from rich.table import Table

    lib = _get_lib(library)
    with lib:
        tags = lib.list_tags()
        # Count usage for each tag
        usage = {}
        for tag in tags:
            ref_ids = lib.get_refs_by_tag(tag.group_id)
            usage[tag.group_id] = len(ref_ids)

    console = Console()
    table = Table(show_header=True, title="Tags")
    table.add_column("ID", justify="right", style="cyan")
    table.add_column("Name")
    table.add_column("Color")
    table.add_column("Usage", justify="right")

    for tag in tags:
        color_hex = f"#{tag.color}"
        table.add_row(
            str(tag.group_id),
            tag.name,
            f"[on {color_hex}]  [/on {color_hex}] {color_hex}",
            str(usage.get(tag.group_id, 0)),
        )

    console.print(table)


@tag_cmd.command()
def show(
    name_or_id: str = typer.Argument(..., help="Tag name or ID"),
    library: Optional[str] = typer.Option(None, "--library", "-l", help="Library name or path"),
    limit: int = typer.Option(50, "--limit", "-n", help="Max refs to show"),
):
    """List references with a specific tag."""
    from rich.console import Console
    from rich.table import Table

    lib = _get_lib(library)
    with lib:
        tags = lib.list_tags()

        # Resolve tag by ID or name
        tag = None
        if name_or_id.isdigit():
            tag_id = int(name_or_id)
            tag = next((t for t in tags if t.group_id == tag_id), None)
        if tag is None:
            tag = next((t for t in tags if t.name.lower() == name_or_id.lower()), None)

        if tag is None:
            typer.echo(f"Tag '{name_or_id}' not found.", err=True)
            raise typer.Exit(1)

        ref_ids = lib.get_refs_by_tag(tag.group_id)
        refs = []
        for rid in ref_ids[:limit]:
            ref = lib.get_ref(rid)
            if ref and ref.trash_state == 0:
                refs.append(ref)

    console = Console()
    table = Table(show_header=True, title=f"Tag: {tag.name} ({len(ref_ids)} refs)")
    table.add_column("ID", justify="right", style="cyan")
    table.add_column("Year", justify="center")
    table.add_column("First Author", max_width=25)
    table.add_column("Title", max_width=60)

    for ref in refs:
        table.add_row(
            str(ref.id),
            ref.year or "",
            ref.first_author_surname,
            (ref.title[:57] + "...") if len(ref.title) > 60 else ref.title,
        )

    console.print(table)
