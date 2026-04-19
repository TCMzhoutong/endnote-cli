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


@write_cmd.command("journal-tags")
def journal_tags(
    library: Optional[str] = typer.Option(None, "--library", "-l", help="Library name or path"),
    group: Optional[str] = typer.Option(None, "--group", "-g", help="Only process refs in this group"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show plan without writing"),
    refresh: bool = typer.Option(
        False, "--refresh",
        help="Remove existing `N区YY年` / `预印本` tags on each ref before re-applying",
    ),
    refresh_data: bool = typer.Option(
        False, "--refresh-data",
        help="Re-download the ranking CSVs (otherwise cached copy is used)",
    ),
):
    """Auto-tag refs with their journal's CAS zone.

    Tag names:
      - `新锐N区` from the New-Elite 2026 table (XR2026)
      - `N区25年` from the CAS 2025 table (FQBJCR2025)
      - `预印本` if the journal contains 'arxiv'

    Colors: 1=red, 2=orange, 3=green, 4=gray, preprint=gray.

    Data fetched from github.com/hitfyd/ShowJCR on first use, cached under
    ~/.endnote-cli/jcr_cache/.
    """
    from endnote_cli.core import jcr

    lib_path = resolve_library_path(library)

    typer.echo("Loading ranking data…")
    xr = jcr.load("XR2026", force_refresh=refresh_data)
    fq = jcr.load("FQBJCR2025", force_refresh=refresh_data)
    typer.echo(f"  XR2026:     {len(xr.by_name):>6} journals / {len(xr.by_issn):>6} ISSNs")
    typer.echo(f"  FQBJCR2025: {len(fq.by_name):>6} journals / {len(fq.by_issn):>6} ISSNs")

    zone_color = {1: "red", 2: "orange", 3: "green", 4: "gray"}
    zone_tag_re = re.compile(r"^(?:新锐[1-4]区|[1-4]区\d+年)$")

    # Collect refs in scope
    with EndnoteLibrary(lib_path) as lib:
        if group:
            g = lib.get_group_by_name(group)
            if not g:
                typer.echo(f"Group '{group}' not found.", err=True)
                raise typer.Exit(1)
            refs = [r for r in (lib.get_ref(i) for i in g.member_ids)
                    if r and r.trash_state == 0]
        else:
            refs = lib.list_refs()
        existing_tags = {t.name: t.group_id for t in lib.list_tags()}
        # current tag ids per ref (for --refresh diffing)
        cur_tags = {r.id: set(r.tag_ids) for r in refs}

    # Build plan
    plan: list[tuple[int, list[str], str]] = []  # (ref_id, tag_names, journal_preview)
    unmatched: list[tuple[int, str]] = []

    for r in refs:
        journal = r.secondary_title or ""
        issn = r.isbn or ""
        tags: list[str] = []
        if "arxiv" in journal.lower():
            tags.append("预印本")
        else:
            h1 = xr.lookup(journal, issn)
            if h1:
                tags.append(f"新锐{h1.zone}区")
            h2 = fq.lookup(journal, issn)
            if h2:
                tags.append(f"{h2.zone}区25年")
        if tags:
            plan.append((r.id, tags, journal[:60]))
        elif journal.strip():
            unmatched.append((r.id, journal[:80]))

    # Report
    typer.echo(f"\nScope: {len(refs)} refs  |  tagged: {len(plan)}  |  unmatched: {len(unmatched)}")
    breakdown: dict[tuple[str, ...], int] = {}
    for _, tags, _ in plan:
        breakdown[tuple(sorted(tags))] = breakdown.get(tuple(sorted(tags)), 0) + 1
    typer.echo("\nBy tag combination:")
    for tset, n in sorted(breakdown.items(), key=lambda kv: (-kv[1], kv[0])):
        typer.echo(f"  {', '.join(tset):<30} × {n}")

    if dry_run:
        typer.echo("\nSample (first 10 tagged):")
        for rid, tags, j in plan[:10]:
            typer.echo(f"  #{rid:>5}  [{','.join(tags):<18}]  {j}")
        if unmatched:
            typer.echo("\nSample unmatched (first 15):")
            for rid, j in unmatched[:15]:
                typer.echo(f"  #{rid:>5}  {j}")
        typer.echo("\n(dry-run — nothing written)")
        return

    # Apply
    needed_tag_names: set[str] = set()
    for _, tags, _ in plan:
        needed_tag_names.update(tags)

    added_links = 0
    removed_links = 0
    created_tags = 0

    with EndnoteWriter(lib_path) as w:
        # Ensure all needed tags exist
        for name in sorted(needed_tag_names):
            if name in existing_tags:
                continue
            if name == "预印本":
                color = "gray"
            else:
                m = re.search(r"[1-4]", name)
                color = zone_color[int(m.group(0))] if m else "gray"
            tid = w.create_tag(name, color)
            existing_tags[name] = tid
            created_tags += 1
            typer.echo(f"Created tag '{name}' (id={tid}, color={color})")

        all_zone_tag_ids = {tid for n, tid in existing_tags.items()
                            if n == "预印本" or zone_tag_re.match(n)}

        for rid, tags, _ in plan:
            want_ids = {existing_tags[n] for n in tags}
            have_ids = cur_tags.get(rid, set())
            if refresh:
                for tid in (have_ids & all_zone_tag_ids) - want_ids:
                    w.remove_tag(rid, tid)
                    removed_links += 1
            for tid in want_ids - have_ids:
                w.write_tag(rid, tid)
                added_links += 1

    typer.echo(
        f"\nDone. Created {created_tags} tag(s); added {added_links} tag-link(s)"
        + (f"; removed {removed_links} stale tag-link(s)" if refresh else "")
        + "."
    )


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
