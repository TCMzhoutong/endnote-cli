"""Group commands: list, tree, show."""

import typer
from typing import Optional

from endnote_cli.core.config import resolve_library_path
from endnote_cli.core.reader import EndnoteLibrary

group_cmd = typer.Typer()


def _get_lib(library: Optional[str]) -> EndnoteLibrary:
    path = resolve_library_path(library)
    return EndnoteLibrary(path)


@group_cmd.command("list")
def list_groups(
    library: Optional[str] = typer.Option(None, "--library", "-l", help="Library name or path"),
):
    """List all groups with member counts."""
    from rich.console import Console
    from rich.table import Table

    lib = _get_lib(library)
    with lib:
        groups = lib.list_groups()

    console = Console()
    table = Table(show_header=True, title="Groups")
    table.add_column("ID", justify="right", style="cyan")
    table.add_column("Name")
    table.add_column("Members", justify="right")
    table.add_column("Set ID", justify="right")

    for g in groups:
        table.add_row(
            str(g.group_id),
            g.name,
            str(len(g.member_ids)),
            str(g.group_set_id) if g.group_set_id is not None else "",
        )

    console.print(table)


@group_cmd.command()
def tree(
    library: Optional[str] = typer.Option(None, "--library", "-l", help="Library name or path"),
):
    """Tree display showing GroupSet -> Group hierarchy."""
    from rich.console import Console
    from rich.tree import Tree

    lib = _get_lib(library)
    with lib:
        group_tree = lib.get_group_tree()

    console = Console()
    root = Tree("[bold]Library Groups[/bold]")

    for gs in group_tree:
        branch = root.add(f"[bold yellow]{gs.name}[/bold yellow] (set {gs.set_id})")
        for g in gs.groups:
            branch.add(f"{g.name} [dim]({len(g.member_ids)} refs)[/dim]")

    console.print(root)


@group_cmd.command()
def show(
    name: str = typer.Argument(..., help="Group name"),
    library: Optional[str] = typer.Option(None, "--library", "-l", help="Library name or path"),
    limit: int = typer.Option(50, "--limit", "-n", help="Max refs to show"),
):
    """List all references in a named group."""
    from rich.console import Console
    from rich.table import Table

    lib = _get_lib(library)
    with lib:
        group = lib.get_group_by_name(name)
        if group is None:
            typer.echo(f"Group '{name}' not found.", err=True)
            raise typer.Exit(1)

        refs = []
        for rid in group.member_ids[:limit]:
            ref = lib.get_ref(rid)
            if ref and ref.trash_state == 0:
                refs.append(ref)

    console = Console()
    table = Table(show_header=True, title=f"Group: {group.name} ({len(group.member_ids)} total)")
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
