"""Export commands: bibtex, ris, json, csv, citation, xml, pdf."""

import typer
from pathlib import Path
from typing import Optional

from endnote_cli.core.config import resolve_library_path
from endnote_cli.core.reader import EndnoteLibrary
from endnote_cli.core.export import (
    refs_to_bibtex,
    refs_to_ris,
    refs_to_json,
    refs_to_csv,
    format_citation,
    export_group_xml,
    copy_pdf,
)

export_cmd = typer.Typer()


def _get_lib(library: Optional[str]) -> EndnoteLibrary:
    path = resolve_library_path(library)
    return EndnoteLibrary(path)


def _collect_refs(lib: EndnoteLibrary, id: Optional[int], group: Optional[str], all: bool):
    """Collect references by ID, group, or all."""
    if id is not None:
        ref = lib.get_ref(id)
        if ref is None:
            typer.echo(f"Reference {id} not found.", err=True)
            raise typer.Exit(1)
        return [ref]
    elif group:
        g = lib.get_group_by_name(group)
        if g is None:
            typer.echo(f"Group '{group}' not found.", err=True)
            raise typer.Exit(1)
        refs = []
        for rid in g.member_ids:
            ref = lib.get_ref(rid)
            if ref and ref.trash_state == 0:
                refs.append(ref)
        return refs
    elif all:
        return lib.list_refs()
    else:
        typer.echo("Specify --id, --group, or --all.", err=True)
        raise typer.Exit(1)


def _output(text: str, output: Optional[Path]):
    if output:
        output.write_text(text, encoding="utf-8")
        typer.echo(f"Written to {output}")
    else:
        typer.echo(text)


@export_cmd.command()
def bibtex(
    library: Optional[str] = typer.Option(None, "--library", "-l", help="Library name or path"),
    id: Optional[int] = typer.Option(None, "--id", help="Export single ref by ID"),
    group: Optional[str] = typer.Option(None, "--group", "-g", help="Export all refs in a group"),
    all: bool = typer.Option(False, "--all", "-a", help="Export all refs"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file path"),
):
    """Export references as BibTeX."""
    lib = _get_lib(library)
    with lib:
        refs = _collect_refs(lib, id, group, all)
    _output(refs_to_bibtex(refs), output)


@export_cmd.command()
def ris(
    library: Optional[str] = typer.Option(None, "--library", "-l", help="Library name or path"),
    id: Optional[int] = typer.Option(None, "--id", help="Export single ref by ID"),
    group: Optional[str] = typer.Option(None, "--group", "-g", help="Export all refs in a group"),
    all: bool = typer.Option(False, "--all", "-a", help="Export all refs"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file path"),
):
    """Export references as RIS."""
    lib = _get_lib(library)
    with lib:
        refs = _collect_refs(lib, id, group, all)
    _output(refs_to_ris(refs), output)


@export_cmd.command("json")
def json_export(
    library: Optional[str] = typer.Option(None, "--library", "-l", help="Library name or path"),
    id: Optional[int] = typer.Option(None, "--id", help="Export single ref by ID"),
    group: Optional[str] = typer.Option(None, "--group", "-g", help="Export all refs in a group"),
    all: bool = typer.Option(False, "--all", "-a", help="Export all refs"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file path"),
    compact: bool = typer.Option(False, "--compact", help="Compact JSON (no indentation)"),
):
    """Export references as JSON."""
    lib = _get_lib(library)
    with lib:
        refs = _collect_refs(lib, id, group, all)
    _output(refs_to_json(refs, pretty=not compact), output)


@export_cmd.command("csv")
def csv_export(
    library: Optional[str] = typer.Option(None, "--library", "-l", help="Library name or path"),
    group: Optional[str] = typer.Option(None, "--group", "-g", help="Export all refs in a group"),
    all: bool = typer.Option(False, "--all", "-a", help="Export all refs"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file path"),
):
    """Export references as CSV."""
    lib = _get_lib(library)
    with lib:
        refs = _collect_refs(lib, None, group, all)
    _output(refs_to_csv(refs), output)


@export_cmd.command()
def citation(
    ref_id: int = typer.Argument(..., help="Reference ID"),
    library: Optional[str] = typer.Option(None, "--library", "-l", help="Library name or path"),
    style: str = typer.Option("apa7", "--style", "-s", help="Citation style: apa7, harvard, vancouver, ieee"),
):
    """Format a single reference as a citation string."""
    lib = _get_lib(library)
    with lib:
        ref = lib.get_ref(ref_id)
    if ref is None:
        typer.echo(f"Reference {ref_id} not found.", err=True)
        raise typer.Exit(1)
    typer.echo(format_citation(ref, style=style))


@export_cmd.command()
def xml(
    library: Optional[str] = typer.Option(None, "--library", "-l", help="Library name or path"),
    group_set: Optional[str] = typer.Option(None, "--group-set", help="Filter by group set name"),
    group: Optional[str] = typer.Option(None, "--group", "-g", help="Filter by group name"),
    output_dir: Path = typer.Option(".", "--output-dir", "-o", help="Output directory"),
):
    """Export references as Endnote XML files organized by group hierarchy."""
    lib = _get_lib(library)
    with lib:
        created = export_group_xml(lib, group_set_name=group_set, group_name=group, output_dir=output_dir)

    if created:
        for f in created:
            typer.echo(f"Created: {f}")
        typer.echo(f"\n{len(created)} file(s) exported.")
    else:
        typer.echo("No matching groups with references found.")


@export_cmd.command()
def pdf(
    ref_id: int = typer.Argument(None, help="Reference ID (for single export)"),
    dest: Path = typer.Argument(".", help="Destination directory"),
    library: Optional[str] = typer.Option(None, "--library", "-l", help="Library name or path"),
    group: Optional[str] = typer.Option(None, "--group", "-g", help="Export PDFs for all refs in a group"),
    all: bool = typer.Option(False, "--all", "-a", help="Export all PDFs"),
    rename: bool = typer.Option(True, "--rename/--no-rename", help="Rename PDFs to Author_Year_Title format"),
):
    """Copy main PDF(s) to a destination directory."""
    lib = _get_lib(library)
    with lib:
        if ref_id is not None and not group and not all:
            ref = lib.get_ref(ref_id)
            if ref is None:
                typer.echo(f"Reference {ref_id} not found.", err=True)
                raise typer.Exit(1)
            result = copy_pdf(lib, ref, dest, rename=rename)
            if result:
                typer.echo(f"Copied: {result}")
            else:
                typer.echo("No PDF found for this reference.", err=True)
                raise typer.Exit(1)
        else:
            # Batch mode
            if group:
                g = lib.get_group_by_name(group)
                if g is None:
                    typer.echo(f"Group '{group}' not found.", err=True)
                    raise typer.Exit(1)
                refs = []
                for rid in g.member_ids:
                    ref = lib.get_ref(rid)
                    if ref and ref.trash_state == 0:
                        refs.append(ref)
            elif all:
                refs = lib.list_refs()
            else:
                typer.echo("Specify a ref ID, --group, or --all.", err=True)
                raise typer.Exit(1)

            copied = 0
            skipped = 0
            for ref in refs:
                result = copy_pdf(lib, ref, dest, rename=rename)
                if result:
                    copied += 1
                else:
                    skipped += 1

            typer.echo(f"Copied {copied} PDF(s), skipped {skipped} (no PDF).")
