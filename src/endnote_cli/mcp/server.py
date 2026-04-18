"""MCP server exposing EndNote library operations as tools."""

from __future__ import annotations

from typing import Optional

from fastmcp import FastMCP

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
from endnote_cli.core.writer import EndnoteWriter
from endnote_cli.core.export import (
    ref_to_dict,
    ref_to_bibtex,
    ref_to_ris,
    refs_to_bibtex,
    refs_to_json,
    format_citation,
    export_group_xml,
    copy_pdf,
)

mcp = FastMCP(name="endnote")


def _lib(library: Optional[str] = None) -> EndnoteLibrary:
    path = resolve_library_path(library)
    return EndnoteLibrary(path)


# ── Library info ────────────────────────────────────────────────

@mcp.tool()
def library_info(library: Optional[str] = None) -> dict:
    """Get overview statistics for the EndNote library."""
    with _lib(library) as lib:
        info = lib.get_info()
    return {
        "path": info.path,
        "total_refs": info.total_refs,
        "trashed_refs": info.trashed_refs,
        "groups": info.groups_count,
        "group_sets": info.group_sets_count,
        "tags": info.tags_count,
        "pdfs": info.pdf_count,
        "dois": info.doi_count,
        "with_abstract": info.refs_with_abstract,
    }


# ── Item operations ─────────────────────────────────────────────

@mcp.tool()
def item_get(ref_id: int, library: Optional[str] = None) -> dict:
    """Get full metadata for a single reference by ID."""
    with _lib(library) as lib:
        ref = lib.get_ref(ref_id)
    if ref is None:
        return {"error": f"Reference {ref_id} not found"}
    return ref_to_dict(ref)


@mcp.tool()
def item_list(
    limit: int = 20,
    offset: int = 0,
    library: Optional[str] = None,
) -> list[dict]:
    """List references with pagination."""
    with _lib(library) as lib:
        refs = lib.list_refs(limit=limit, offset=offset)
    return [{"id": r.id, "author": r.first_author_surname, "year": r.year,
             "title": r.title[:80], "doi": r.doi} for r in refs]


@mcp.tool()
def item_count(library: Optional[str] = None) -> int:
    """Count total references in the library."""
    with _lib(library) as lib:
        return lib.count_refs()


# ── Search ──────────────────────────────────────────────────────

@mcp.tool()
def search_quick(
    query: str,
    limit: int = 20,
    group: Optional[str] = None,
    library: Optional[str] = None,
) -> list[dict]:
    """Quick keyword search across title, author, abstract, keywords."""
    with _lib(library) as lib:
        refs = quick_search(lib, query, limit=limit, group_name=group)
    return [{"id": r.id, "author": r.first_author_surname, "year": r.year,
             "title": r.title[:80], "doi": r.doi} for r in refs]


@mcp.tool()
def search_advanced(
    conditions: list[dict],
    limit: int = 20,
    group: Optional[str] = None,
    library: Optional[str] = None,
) -> list[dict]:
    """Advanced multi-field search with boolean logic.

    Args:
        conditions: List of condition dicts. Each has:
            - field: column name (e.g. "title", "year", "doi", "journal")
            - op: operator ("contains", "is", "lt", "lte", "gt", "gte",
                   "begins-with", "ends-with", "word-begins")
            - value: search value
            - bool: boolean connector ("and", "or", "not"). Omit for first condition.
        limit: Max results to return.
        group: Restrict search to a named group.

    Example:
        conditions=[
            {"field": "title", "op": "contains", "value": "knowledge graph"},
            {"field": "year", "op": "gte", "value": "2024", "bool": "and"},
        ]
    """
    parsed = []
    for i, c in enumerate(conditions):
        op = Operator(c["op"])
        cond = Condition(field=c["field"], operator=op, value=c["value"])
        if i == 0:
            parsed.append((None, cond))
        else:
            b = BooleanOp(c.get("bool", "and"))
            parsed.append((b, cond))

    sq = SearchQuery(conditions=parsed)
    with _lib(library) as lib:
        refs = search(lib, sq, limit=limit, group_name=group)
    return [{"id": r.id, "author": r.first_author_surname, "year": r.year,
             "title": r.title[:80], "doi": r.doi} for r in refs]


# ── Groups ──────────────────────────────────────────────────────

@mcp.tool()
def group_list(library: Optional[str] = None) -> list[dict]:
    """List all groups with member counts."""
    with _lib(library) as lib:
        groups = lib.list_groups()
    return [{"id": g.group_id, "name": g.name, "members": len(g.member_ids),
             "group_set_id": g.group_set_id} for g in groups]


@mcp.tool()
def group_tree(library: Optional[str] = None) -> list[dict]:
    """Get the full group hierarchy: GroupSet → Groups."""
    with _lib(library) as lib:
        tree = lib.get_group_tree()
    return [
        {
            "set_name": gs.name,
            "set_id": gs.set_id,
            "groups": [
                {"id": g.group_id, "name": g.name, "members": len(g.member_ids)}
                for g in gs.groups
            ],
        }
        for gs in tree
    ]


@mcp.tool()
def group_show(
    name: str,
    library: Optional[str] = None,
) -> list[dict]:
    """List all references in a named group."""
    with _lib(library) as lib:
        g = lib.get_group_by_name(name)
        if g is None:
            return [{"error": f"Group '{name}' not found"}]
        refs = []
        for rid in g.member_ids:
            ref = lib.get_ref(rid)
            if ref and ref.trash_state == 0:
                refs.append({"id": ref.id, "author": ref.first_author_surname,
                             "year": ref.year, "title": ref.title[:80]})
    return refs


# ── Tags ────────────────────────────────────────────────────────

@mcp.tool()
def tag_list(library: Optional[str] = None) -> list[dict]:
    """List all color tags."""
    with _lib(library) as lib:
        tags = lib.list_tags()
    return [{"id": t.group_id, "name": t.name, "color": f"#{t.color}"} for t in tags]


# ── Export ──────────────────────────────────────────────────────

@mcp.tool()
def export_bibtex(ref_id: int, library: Optional[str] = None) -> str:
    """Export a single reference as BibTeX."""
    with _lib(library) as lib:
        ref = lib.get_ref(ref_id)
    if ref is None:
        return f"Reference {ref_id} not found"
    return ref_to_bibtex(ref)


@mcp.tool()
def export_ris(ref_id: int, library: Optional[str] = None) -> str:
    """Export a single reference as RIS."""
    with _lib(library) as lib:
        ref = lib.get_ref(ref_id)
    if ref is None:
        return f"Reference {ref_id} not found"
    return ref_to_ris(ref)


@mcp.tool()
def export_citation(
    ref_id: int,
    style: str = "apa7",
    library: Optional[str] = None,
) -> str:
    """Format a reference as a citation string.

    Styles: apa7, harvard, vancouver, ieee.
    """
    with _lib(library) as lib:
        ref = lib.get_ref(ref_id)
    if ref is None:
        return f"Reference {ref_id} not found"
    return format_citation(ref, style=style)


@mcp.tool()
def export_json(
    ref_id: int,
    library: Optional[str] = None,
) -> dict:
    """Export a single reference as JSON metadata."""
    with _lib(library) as lib:
        ref = lib.get_ref(ref_id)
    if ref is None:
        return {"error": f"Reference {ref_id} not found"}
    return ref_to_dict(ref)


# ── Write operations ────────────────────────────────────────────

@mcp.tool()
def write_research_notes(
    ref_id: int,
    text: str,
    append: bool = False,
    library: Optional[str] = None,
) -> str:
    """Write or append to the research_notes field of a reference."""
    path = resolve_library_path(library)
    with EndnoteWriter(path) as w:
        if append:
            w.append_research_notes(ref_id, text)
        else:
            w.write_research_notes(ref_id, text)
    return f"OK: research_notes updated for ref {ref_id}"


@mcp.tool()
def write_keyword(
    ref_id: int,
    keyword: str,
    remove: bool = False,
    library: Optional[str] = None,
) -> str:
    """Add or remove a keyword from a reference."""
    path = resolve_library_path(library)
    with EndnoteWriter(path) as w:
        if remove:
            w.remove_keyword(ref_id, keyword)
            return f"OK: keyword '{keyword}' removed from ref {ref_id}"
        else:
            w.append_keyword(ref_id, keyword)
            return f"OK: keyword '{keyword}' added to ref {ref_id}"


@mcp.tool()
def write_tag(
    ref_id: int,
    tag_id: int,
    remove: bool = False,
    library: Optional[str] = None,
) -> str:
    """Add or remove a color tag from a reference."""
    path = resolve_library_path(library)
    with EndnoteWriter(path) as w:
        if remove:
            w.remove_tag(ref_id, tag_id)
            return f"OK: tag {tag_id} removed from ref {ref_id}"
        else:
            w.write_tag(ref_id, tag_id)
            return f"OK: tag {tag_id} added to ref {ref_id}"


@mcp.tool()
def write_field(
    ref_id: int,
    field: str,
    value: str,
    library: Optional[str] = None,
) -> str:
    """Write a value to any safe field (research_notes, notes, label, custom_1-7, etc.)."""
    path = resolve_library_path(library)
    with EndnoteWriter(path) as w:
        w.write_field(ref_id, field, value)
    return f"OK: {field} updated for ref {ref_id}"


@mcp.tool()
def add_attachment(
    ref_id: int,
    file_path: str,
    library: Optional[str] = None,
) -> str:
    """Attach a file to a reference (copies file into .Data/PDF/ directory)."""
    path = resolve_library_path(library)
    with EndnoteWriter(path) as w:
        rel = w.add_attachment(ref_id, file_path)
    return f"OK: attached as {rel}"


# ── PDF locate ──────────────────────────────────────────────────

@mcp.tool()
def pdf_locate(ref_id: int, library: Optional[str] = None) -> list[dict]:
    """List all file attachments for a reference with full paths."""
    with _lib(library) as lib:
        attachments = lib.get_attachments(ref_id)
        result = []
        for a in attachments:
            full_path = lib.resolve_attachment_path(a)
            result.append({
                "pos": a.file_pos,
                "filename": a.filename,
                "extension": a.extension,
                "is_pdf": a.is_pdf,
                "is_supplement": a.is_supplement,
                "full_path": str(full_path) if full_path else None,
                "relative_path": a.file_path,
            })
    return result


def serve():
    """Start the MCP server."""
    mcp.run()
