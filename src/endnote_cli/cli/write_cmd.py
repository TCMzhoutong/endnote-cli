"""Write commands: note, keyword, status, rating, label, tag, field, attach, clear, rename-pdf."""

import re
import typer
from pathlib import Path
from typing import Optional

from endnote_cli.core.config import resolve_library_path
from endnote_cli.core.reader import EndnoteLibrary
from endnote_cli.core.writer import EndnoteWriter

write_cmd = typer.Typer()


def _get_writer(library: Optional[str]) -> EndnoteWriter:
    path = resolve_library_path(library)
    return EndnoteWriter(path)


@write_cmd.command()
def note(
    ref_id: int = typer.Argument(..., help="Reference ID"),
    file_or_text: str = typer.Argument(..., help="Text content or path to a .txt/.md file"),
    library: Optional[str] = typer.Option(None, "--library", "-l", help="Library name or path"),
    append: bool = typer.Option(False, "--append", "-a", help="Append instead of overwrite"),
):
    """Write to research_notes field."""
    # If it looks like a file path, read its content
    p = Path(file_or_text)
    if p.exists() and p.is_file():
        text = p.read_text(encoding="utf-8")
    else:
        text = file_or_text

    writer = _get_writer(library)
    with writer:
        if append:
            writer.append_research_notes(ref_id, text)
        else:
            writer.write_research_notes(ref_id, text)

    typer.echo(f"{'Appended to' if append else 'Wrote'} research_notes for ref {ref_id}.")


@write_cmd.command()
def keyword(
    ref_id: int = typer.Argument(..., help="Reference ID"),
    kw: str = typer.Argument(..., help="Keyword to add or remove"),
    library: Optional[str] = typer.Option(None, "--library", "-l", help="Library name or path"),
    remove: bool = typer.Option(False, "--remove", "-r", help="Remove keyword instead of adding"),
):
    """Add or remove a keyword."""
    writer = _get_writer(library)
    with writer:
        if remove:
            writer.remove_keyword(ref_id, kw)
            typer.echo(f"Removed keyword '{kw}' from ref {ref_id}.")
        else:
            writer.append_keyword(ref_id, kw)
            typer.echo(f"Added keyword '{kw}' to ref {ref_id}.")


@write_cmd.command()
def status(
    ref_id: int = typer.Argument(..., help="Reference ID"),
    value: str = typer.Argument(..., help="Read status value (1=read, 0=unread, ''=unset)"),
    library: Optional[str] = typer.Option(None, "--library", "-l", help="Library name or path"),
):
    """Set read_status for a reference."""
    writer = _get_writer(library)
    with writer:
        writer.write_read_status(ref_id, value)
    typer.echo(f"Set read_status={value} for ref {ref_id}.")


@write_cmd.command()
def rating(
    ref_id: int = typer.Argument(..., help="Reference ID"),
    value: str = typer.Argument(..., help="Rating value"),
    library: Optional[str] = typer.Option(None, "--library", "-l", help="Library name or path"),
):
    """Set rating for a reference."""
    writer = _get_writer(library)
    with writer:
        writer.write_rating(ref_id, value)
    typer.echo(f"Set rating={value} for ref {ref_id}.")


@write_cmd.command()
def label(
    ref_id: int = typer.Argument(..., help="Reference ID"),
    value: str = typer.Argument(..., help="Label value"),
    library: Optional[str] = typer.Option(None, "--library", "-l", help="Library name or path"),
):
    """Set label for a reference."""
    writer = _get_writer(library)
    with writer:
        writer.write_label(ref_id, value)
    typer.echo(f"Set label='{value}' for ref {ref_id}.")


@write_cmd.command()
def tag(
    ref_id: int = typer.Argument(..., help="Reference ID"),
    tag_id: int = typer.Argument(..., help="Tag (color label) ID"),
    library: Optional[str] = typer.Option(None, "--library", "-l", help="Library name or path"),
    remove: bool = typer.Option(False, "--remove", "-r", help="Remove tag instead of adding"),
):
    """Add or remove a color tag."""
    writer = _get_writer(library)
    with writer:
        if remove:
            writer.remove_tag(ref_id, tag_id)
            typer.echo(f"Removed tag {tag_id} from ref {ref_id}.")
        else:
            writer.write_tag(ref_id, tag_id)
            typer.echo(f"Added tag {tag_id} to ref {ref_id}.")


@write_cmd.command()
def field(
    ref_id: int = typer.Argument(..., help="Reference ID"),
    field_name: str = typer.Argument(..., help="Field name (must be a safe-write field)"),
    value: str = typer.Argument(..., help="Value to write"),
    library: Optional[str] = typer.Option(None, "--library", "-l", help="Library name or path"),
):
    """Write a value to any safe field (research_notes, notes, keywords, custom_1..7, etc.)."""
    writer = _get_writer(library)
    with writer:
        writer.write_field(ref_id, field_name, value)
    typer.echo(f"Set {field_name}='{value[:50]}{'...' if len(value) > 50 else ''}' for ref {ref_id}.")


@write_cmd.command()
def attach(
    ref_id: int = typer.Argument(..., help="Reference ID"),
    file: Path = typer.Argument(..., help="File to attach", exists=True),
    library: Optional[str] = typer.Option(None, "--library", "-l", help="Library name or path"),
):
    """Add an attachment to a reference."""
    writer = _get_writer(library)
    with writer:
        rel_path = writer.add_attachment(ref_id, file)
    typer.echo(f"Attached {file.name} to ref {ref_id} (path: {rel_path}).")


@write_cmd.command()
def clear(
    ref_id: int = typer.Argument(..., help="Reference ID"),
    field_name: str = typer.Argument(..., help="Field name to clear"),
    library: Optional[str] = typer.Option(None, "--library", "-l", help="Library name or path"),
):
    """Clear (empty) a safe field."""
    writer = _get_writer(library)
    with writer:
        writer.clear_field(ref_id, field_name)
    typer.echo(f"Cleared {field_name} for ref {ref_id}.")


@write_cmd.command("rename-pdf")
def rename_pdf(
    ref_id: int = typer.Argument(None, help="Reference ID (for single rename)"),
    library: Optional[str] = typer.Option(None, "--library", "-l", help="Library name or path"),
    group: Optional[str] = typer.Option(None, "--group", "-g", help="Rename all PDFs in a group"),
    all: bool = typer.Option(False, "--all", "-a", help="Rename all PDFs in the library"),
    pattern: str = typer.Option(
        "{author}_{year}_{title}",
        "--pattern", "-p",
        help="Naming pattern. Variables: {author}, {year}, {title}, {doi}, {id}",
    ),
    title_len: int = typer.Option(40, "--title-len", help="Max title length in filename"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show renames without executing"),
):
    """Rename main PDF files to a standardized pattern.

    Default pattern: Author_Year_TitleShort.pdf
    """
    lib_path = resolve_library_path(library)

    # Collect ref IDs
    with EndnoteLibrary(lib_path) as lib:
        if ref_id is not None and not group and not all:
            ref_ids = [ref_id]
        elif group:
            g = lib.get_group_by_name(group)
            if not g:
                typer.echo(f"Group '{group}' not found.", err=True)
                raise typer.Exit(1)
            ref_ids = g.member_ids
        elif all:
            ref_ids = [r.id for r in lib.list_refs()]
        else:
            typer.echo("Specify a ref ID, --group, or --all.", err=True)
            raise typer.Exit(1)

        # Build rename plan
        # Each entry: (ref_id, file_pos, old_name, new_name, warning)
        plan = []
        warnings = []
        for rid in ref_ids:
            ref = lib.get_ref(rid)
            if not ref or ref.trash_state != 0:
                continue

            attachments = lib.get_attachments(rid)
            pdfs = [a for a in attachments if a.is_pdf]
            if not pdfs:
                continue

            main_pdf = lib.get_main_pdf(rid)
            if not main_pdf:
                continue

            # ── Two-level verification ──
            warning = None

            # Check 1: pos=0 is supplement → get_main_pdf switched to another file
            if len(pdfs) > 1:
                pos0 = pdfs[0]
                if pos0.is_supplement and main_pdf.file_pos != 0:
                    warning = (
                        f"pos=0 is supplement ({pos0.filename}), "
                        f"using pos={main_pdf.file_pos} ({main_pdf.filename}) instead"
                    )

                # Check 2: multiple non-supplement PDFs (ambiguous main file)
                non_supp = [p for p in pdfs if not p.is_supplement]
                if len(non_supp) > 1:
                    warning = (
                        f"multiple candidate PDFs: "
                        + ", ".join(f"pos={p.file_pos} {p.filename}" for p in non_supp)
                    )

            # Build new filename
            author = re.sub(r"[^a-zA-Z\u4e00-\u9fff]", "", ref.first_author_surname)
            title_short = ref.title[:title_len].strip() if ref.title else "Untitled"
            title_short = re.sub(r'[<>:"/\\|?*\r\n]', "", title_short)
            doi_safe = ref.doi.replace("/", "_").replace(".", "_") if ref.doi else ""

            new_name = pattern.format(
                author=author, year=ref.year, title=title_short,
                doi=doi_safe, id=ref.id,
            )
            new_name = re.sub(r'[<>:"/\\|?*]', "_", new_name)
            new_name += ".pdf"

            if main_pdf.filename != new_name:
                plan.append((rid, main_pdf.file_pos, main_pdf.filename, new_name, warning))
                if warning:
                    warnings.append((rid, warning))

    # Execute or dry-run
    if not plan:
        typer.echo("No PDFs to rename.")
        return

    if dry_run:
        typer.echo(f"Dry run: {len(plan)} rename(s), {len(warnings)} warning(s)\n")
        for rid, pos, old, new, warning in plan:
            marker = "  ⚠ " if warning else "  "
            typer.echo(f"{marker}ref {rid}: {old} → {new}")
            if warning:
                typer.echo(f"       WARNING: {warning}")
        if warnings:
            typer.echo(f"\n{len(warnings)} ref(s) need manual review (marked with ⚠).")
            typer.echo("These will be SKIPPED during actual execution unless you use --force.")
        return

    renamed = 0
    skipped = 0
    errors = 0
    with EndnoteWriter(lib_path) as w:
        for rid, pos, old, new, warning in plan:
            if warning:
                typer.echo(f"  SKIP ref {rid}: {warning}")
                skipped += 1
                continue
            try:
                w.rename_attachment(rid, pos, new)
                renamed += 1
            except Exception as e:
                typer.echo(f"  ERROR ref {rid}: {e}", err=True)
                errors += 1

    typer.echo(f"\nRenamed {renamed}, skipped {skipped} (need review), errors {errors}.")
