"""CLI entry point for endnote-cli."""

import typer

from .app_cmd import app_cmd
from .item_cmd import item_cmd
from .group_cmd import group_cmd
from .tag_cmd import tag_cmd
from .search_cmd import search_cmd
from .export_cmd import export_cmd
from .write_cmd import write_cmd
from .library_cmd import library_cmd

app = typer.Typer(
    name="endnote-cli",
    help="CLI & MCP server for reading/searching/exporting EndNote libraries.",
    no_args_is_help=True,
)

app.add_typer(app_cmd, name="app", help="Check connectivity and library info")
app.add_typer(item_cmd, name="item", help="List, get, and count references")
app.add_typer(group_cmd, name="group", help="List and browse groups")
app.add_typer(tag_cmd, name="tag", help="List and browse color tags")
app.add_typer(search_cmd, name="search", help="Search references")
app.add_typer(export_cmd, name="export", help="Export references (BibTeX, RIS, JSON, CSV, XML, PDF)")
app.add_typer(write_cmd, name="write", help="Write to safe fields (notes, tags, attachments)")
app.add_typer(library_cmd, name="library", help="Manage multiple libraries")


@app.command()
def mcp():
    """Start MCP server for Claude Code / Claude Desktop."""
    try:
        from endnote_cli.mcp.server import serve
        serve()
    except ImportError:
        typer.echo("MCP dependencies not installed. Run: pip install 'endnote-cli[mcp]'")
        raise typer.Exit(1)
