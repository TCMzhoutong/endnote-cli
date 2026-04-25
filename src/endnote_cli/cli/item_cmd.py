"""Item commands: list, get, count."""

import typer
from typing import Optional

from endnote_cli.core.config import resolve_library_path
from endnote_cli.core.reader import EndnoteLibrary

item_cmd = typer.Typer()


def _get_lib(library: Optional[str]) -> EndnoteLibrary:
    path = resolve_library_path(library)
    return EndnoteLibrary(path)


@item_cmd.command("list")
def list_refs(
    library: Optional[str] = typer.Option(None, "--library", "-l", help="Library name or path"),
    limit: int = typer.Option(20, "--limit", "-n", help="Max number of refs to show"),
    offset: int = typer.Option(0, "--offset", help="Skip first N refs"),
    trashed: bool = typer.Option(False, "--trashed", help="Include trashed refs"),
):
    """List references as a table."""
    from rich.console import Console
    from rich.table import Table

    lib = _get_lib(library)
    with lib:
        refs = lib.list_refs(include_trashed=trashed, limit=limit, offset=offset)

    console = Console()
    table = Table(show_header=True, title=f"References (offset={offset}, limit={limit})")
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


@item_cmd.command()
def get(
    ref_id: int = typer.Argument(..., help="Reference ID"),
    library: Optional[str] = typer.Option(None, "--library", "-l", help="Library name or path"),
):
    """Print full metadata of a single reference."""
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table

    lib = _get_lib(library)
    with lib:
        ref = lib.get_ref(ref_id)

    if ref is None:
        typer.echo(f"Reference {ref_id} not found.", err=True)
        raise typer.Exit(1)

    console = Console()

    table = Table(show_header=False, box=None, pad_edge=False)
    table.add_column("Field", style="bold cyan", min_width=22)
    table.add_column("Value")

    fields = [
        ("ID", str(ref.id)),
        ("Type", ref.ref_type_name),
        ("Title", ref.title),
        ("Author(s)", "; ".join(ref.authors_list)),
        ("Year", ref.year),
        ("Journal", ref.journal),
        ("Volume", ref.volume),
        ("Number", ref.number),
        ("Pages", ref.pages),
        ("DOI", ref.doi),
        ("URL", ref.url),
        ("Publisher", ref.publisher),
        ("ISBN/ISSN", ref.isbn),
        ("Language", ref.language),
        ("Keywords", ref.keywords.replace("\n", "; ").replace("\r", "")),
        ("Label", ref.label),
        ("Read Status", ref.read_status),
        ("Rating", ref.rating),
        ("Abstract", ref.abstract[:200] + "..." if len(ref.abstract) > 200 else ref.abstract),
        ("Notes", ref.notes[:200] + "..." if len(ref.notes) > 200 else ref.notes),
        ("Research Notes", ref.research_notes[:200] + "..." if len(ref.research_notes) > 200 else ref.research_notes),
        ("Attachments", ", ".join(a.filename for a in ref.attachments) if ref.attachments else "(none)"),
        ("Tag IDs", ", ".join(str(t) for t in ref.tag_ids) if ref.tag_ids else "(none)"),
    ]

    for name, value in fields:
        if value and value.strip():
            table.add_row(name, value)

    console.print(Panel(table, title=f"Reference #{ref.id}"))


@item_cmd.command()
def count(
    library: Optional[str] = typer.Option(None, "--library", "-l", help="Library name or path"),
    trashed: bool = typer.Option(False, "--trashed", help="Include trashed refs"),
):
    """Print count of references."""
    lib = _get_lib(library)
    with lib:
        n = lib.count_refs(include_trashed=trashed)
    typer.echo(n)


@item_cmd.command()
def groups(
    ref_id: int = typer.Argument(..., help="Reference ID"),
    library: Optional[str] = typer.Option(None, "--library", "-l", help="Library name or path"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """List all groups (with parent GroupSet) that contain a given reference.

    Path format: 'GroupSet/Group' for parented groups, bare 'Group' name for
    orphan (unparented) groups. Use --json for machine-readable output.
    """
    import json as jsonmod
    from rich.console import Console
    from rich.table import Table

    lib = _get_lib(library)
    with lib:
        gs = lib.list_groups_for_ref(ref_id)
        sets = {s.set_id: s.name for s in lib.list_group_sets()}

    def path_for(g):
        if g.group_set_id and g.group_set_id in sets:
            return f"{sets[g.group_set_id]}/{g.name}"
        return g.name

    if json_output:
        out = [
            {
                "group_id": g.group_id,
                "group_name": g.name,
                "group_set_id": g.group_set_id,
                "group_set_name": sets.get(g.group_set_id) if g.group_set_id else None,
                "path": path_for(g),
            }
            for g in gs
        ]
        typer.echo(jsonmod.dumps(out, ensure_ascii=False, indent=2))
        return

    if not gs:
        typer.echo(f"Reference {ref_id} is not in any group.")
        return

    console = Console()
    table = Table(show_header=True, title=f"Groups for ref #{ref_id} ({len(gs)})")
    table.add_column("Group ID", justify="right", style="cyan")
    table.add_column("Path")

    for g in gs:
        table.add_row(str(g.group_id), path_for(g))

    console.print(table)
