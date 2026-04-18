"""Search commands: quick, advanced."""

import typer
from typing import Optional, List

from endnote_cli.core.config import resolve_library_path
from endnote_cli.core.reader import EndnoteLibrary
from endnote_cli.core.search import (
    quick_search,
    search,
    SearchQuery,
    Condition,
    Operator,
    BooleanOp,
)

search_cmd = typer.Typer()


def _get_lib(library: Optional[str]) -> EndnoteLibrary:
    path = resolve_library_path(library)
    return EndnoteLibrary(path)


def _print_refs(refs, title: str = "Results"):
    from rich.console import Console
    from rich.table import Table

    console = Console()
    table = Table(show_header=True, title=f"{title} ({len(refs)} found)")
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


@search_cmd.command()
def quick(
    query: str = typer.Argument(..., help="Search text (matches title/author/abstract/keywords)"),
    library: Optional[str] = typer.Option(None, "--library", "-l", help="Library name or path"),
    limit: int = typer.Option(20, "--limit", "-n", help="Max results"),
    group: Optional[str] = typer.Option(None, "--group", "-g", help="Restrict to a group"),
):
    """Quick search across title, author, abstract, and keywords."""
    lib = _get_lib(library)
    with lib:
        refs = quick_search(lib, query, limit=limit, group_name=group)

    _print_refs(refs, title=f"Quick search: {query}")


@search_cmd.command()
def advanced(
    library: Optional[str] = typer.Option(None, "--library", "-l", help="Library name or path"),
    field: List[str] = typer.Option(..., "--field", "-f", help="Field name(s) for each condition"),
    op: List[str] = typer.Option(
        ..., "--op", "-o",
        help="Operator(s): contains, is, lt, lte, gt, gte, begins-with, ends-with, word-begins",
    ),
    value: List[str] = typer.Option(..., "--value", "-v", help="Value(s) for each condition"),
    bool_op: List[str] = typer.Option(
        [], "--bool", "-b",
        help="Boolean op(s) between conditions: and, or, not. "
             "Provide N-1 values for N conditions (first condition has no boolean prefix).",
    ),
    limit: int = typer.Option(20, "--limit", "-n", help="Max results"),
    group: Optional[str] = typer.Option(None, "--group", "-g", help="Restrict to a group"),
):
    """Multi-field search with boolean logic.

    Use repeated --field/--op/--value triplets for each condition.
    Use --bool between conditions (N-1 values for N conditions).

    Example:
        endnote-cli search advanced -f title -o contains -v "machine learning"
            -f year -o gte -v 2020 --bool and
    """
    if len(field) != len(op) or len(field) != len(value):
        typer.echo("Error: --field, --op, and --value must have the same count.", err=True)
        raise typer.Exit(1)

    if len(bool_op) != max(0, len(field) - 1):
        typer.echo(
            f"Error: expected {max(0, len(field) - 1)} --bool values for {len(field)} conditions, "
            f"got {len(bool_op)}.",
            err=True,
        )
        raise typer.Exit(1)

    # Build conditions
    conditions = []
    for i in range(len(field)):
        try:
            operator = Operator(op[i])
        except ValueError:
            typer.echo(f"Error: unknown operator '{op[i]}'.", err=True)
            raise typer.Exit(1)

        cond = Condition(field=field[i], operator=operator, value=value[i])

        if i == 0:
            conditions.append((None, cond))
        else:
            try:
                b = BooleanOp(bool_op[i - 1])
            except ValueError:
                typer.echo(f"Error: unknown boolean op '{bool_op[i - 1]}'.", err=True)
                raise typer.Exit(1)
            conditions.append((b, cond))

    sq = SearchQuery(conditions=conditions)
    lib = _get_lib(library)
    with lib:
        refs = search(lib, sq, limit=limit, group_name=group)

    _print_refs(refs, title="Advanced search")
