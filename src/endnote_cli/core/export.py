"""Export references in various formats: BibTeX, RIS, JSON, CSV, XML, citations."""

from __future__ import annotations

import csv
import io
import json
import re
import shutil
from pathlib import Path
from typing import Optional
from xml.etree.ElementTree import Element, SubElement, tostring, indent

from .models import Reference
from .reader import EndnoteLibrary


# ── BibTeX ──────────────────────────────────────────────────────

def _bibtex_escape(text: str) -> str:
    return text.replace("&", r"\&").replace("_", r"\_").replace("%", r"\%")


def _make_cite_key(ref: Reference) -> str:
    surname = re.sub(r"[^a-zA-Z]", "", ref.first_author_surname)
    title_word = ""
    if ref.title:
        words = re.findall(r"[A-Za-z]+", ref.title)
        # Pick first significant word (skip short articles)
        for w in words:
            if len(w) > 3:
                title_word = w.capitalize()
                break
        if not title_word and words:
            title_word = words[0].capitalize()
    return f"{surname}{ref.year}{title_word}"


def ref_to_bibtex(ref: Reference) -> str:
    key = _make_cite_key(ref)
    type_map = {0: "article", 1: "book", 2: "incollection", 3: "inproceedings"}
    bib_type = type_map.get(ref.reference_type, "misc")

    lines = [f"@{bib_type}{{{key},"]

    field_map = [
        ("title", ref.title),
        ("author", " and ".join(ref.authors_list)),
        ("year", ref.year),
        ("journal", ref.journal),
        ("volume", ref.volume),
        ("number", ref.number),
        ("pages", ref.pages),
        ("doi", ref.doi),
        ("url", ref.url),
        ("abstract", ref.abstract),
        ("keywords", ref.keywords.replace("\n", ", ").replace("\r", ", ")),
        ("publisher", ref.publisher),
        ("isbn", ref.isbn),
        ("language", ref.language),
        ("note", ref.notes),
    ]

    for field_name, value in field_map:
        if value and value.strip():
            lines.append(f"  {field_name} = {{{_bibtex_escape(value.strip())}}},")

    lines.append("}")
    return "\n".join(lines)


def refs_to_bibtex(refs: list[Reference]) -> str:
    return "\n\n".join(ref_to_bibtex(r) for r in refs)


# ── RIS ─────────────────────────────────────────────────────────

def ref_to_ris(ref: Reference) -> str:
    type_map = {0: "JOUR", 1: "BOOK", 2: "CHAP", 3: "CONF"}
    ris_type = type_map.get(ref.reference_type, "GEN")

    lines = [f"TY  - {ris_type}"]

    for author in ref.authors_list:
        lines.append(f"AU  - {author}")

    field_map = [
        ("TI", ref.title),
        ("T2", ref.journal),
        ("PY", ref.year),
        ("VL", ref.volume),
        ("IS", ref.number),
        ("SP", ref.pages),
        ("DO", ref.doi),
        ("UR", ref.url),
        ("AB", ref.abstract),
        ("PB", ref.publisher),
        ("SN", ref.isbn),
        ("LA", ref.language),
        ("N1", ref.notes),
        ("N2", ref.research_notes),
    ]

    for tag, value in field_map:
        if value and value.strip():
            lines.append(f"{tag}  - {value.strip()}")

    # Keywords as separate KW lines
    if ref.keywords:
        for kw in ref.keywords.replace("\r", "\n").split("\n"):
            kw = kw.strip()
            if kw:
                lines.append(f"KW  - {kw}")

    lines.append("ER  - ")
    return "\n".join(lines)


def refs_to_ris(refs: list[Reference]) -> str:
    return "\n\n".join(ref_to_ris(r) for r in refs)


# ── JSON ────────────────────────────────────────────────────────

def ref_to_dict(ref: Reference) -> dict:
    return {
        "id": ref.id,
        "type": ref.ref_type_name,
        "title": ref.title,
        "authors": ref.authors_list,
        "year": ref.year,
        "journal": ref.journal,
        "volume": ref.volume,
        "number": ref.number,
        "pages": ref.pages,
        "doi": ref.doi,
        "url": ref.url,
        "abstract": ref.abstract,
        "keywords": [k.strip() for k in ref.keywords.replace("\r", "\n").split("\n") if k.strip()],
        "language": ref.language,
        "publisher": ref.publisher,
        "isbn": ref.isbn,
        "notes": ref.notes,
        "research_notes": ref.research_notes,
        "read_status": ref.read_status,
        "rating": ref.rating,
        "label": ref.label,
        "added_to_library": ref.added_to_library,
        "record_last_updated": ref.record_last_updated,
        "attachments": [
            {"filename": a.filename, "path": a.file_path, "is_pdf": a.is_pdf}
            for a in ref.attachments
        ],
        "tag_ids": ref.tag_ids,
    }


def refs_to_json(refs: list[Reference], pretty: bool = True) -> str:
    data = [ref_to_dict(r) for r in refs]
    return json.dumps(data, ensure_ascii=False, indent=2 if pretty else None)


# ── CSV ─────────────────────────────────────────────────────────

CSV_COLUMNS = [
    "id", "title", "authors", "year", "journal", "volume", "number",
    "pages", "doi", "url", "keywords", "language", "type",
]


def refs_to_csv(refs: list[Reference]) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=CSV_COLUMNS)
    writer.writeheader()
    for ref in refs:
        writer.writerow({
            "id": ref.id,
            "title": ref.title,
            "authors": "; ".join(ref.authors_list),
            "year": ref.year,
            "journal": ref.journal,
            "volume": ref.volume,
            "number": ref.number,
            "pages": ref.pages,
            "doi": ref.doi,
            "url": ref.url,
            "keywords": "; ".join(
                k.strip() for k in ref.keywords.replace("\r", "\n").split("\n") if k.strip()
            ),
            "language": ref.language,
            "type": ref.ref_type_name,
        })
    return output.getvalue()


# ── Citation formatting ─────────────────────────────────────────

def format_citation(ref: Reference, style: str = "apa7") -> str:
    authors = ref.authors_list
    if not authors:
        author_str = "Unknown"
    elif len(authors) == 1:
        author_str = authors[0]
    elif len(authors) == 2:
        author_str = f"{authors[0]} & {authors[1]}"
    elif len(authors) <= 5:
        author_str = ", ".join(authors[:-1]) + f", & {authors[-1]}"
    else:
        author_str = f"{authors[0]} et al."

    year = ref.year or "n.d."
    title = ref.title or "Untitled"
    journal = ref.journal or ""

    match style:
        case "apa7":
            parts = [f"{author_str} ({year}). {title}."]
            if journal:
                vol = f", {ref.volume}" if ref.volume else ""
                num = f"({ref.number})" if ref.number else ""
                pages = f", {ref.pages}" if ref.pages else ""
                parts.append(f" *{journal}*{vol}{num}{pages}.")
            if ref.doi:
                parts.append(f" https://doi.org/{ref.doi}")
            return "".join(parts)

        case "harvard":
            parts = [f"{author_str} ({year}) '{title}',"]
            if journal:
                parts.append(f" *{journal}*")
                if ref.volume:
                    parts.append(f", vol. {ref.volume}")
                if ref.number:
                    parts.append(f", no. {ref.number}")
                if ref.pages:
                    parts.append(f", pp. {ref.pages}")
            parts.append(".")
            return "".join(parts)

        case "vancouver":
            parts = [f"{author_str}. {title}."]
            if journal:
                parts.append(f" {journal}. {year}")
                if ref.volume:
                    parts.append(f";{ref.volume}")
                if ref.number:
                    parts.append(f"({ref.number})")
                if ref.pages:
                    parts.append(f":{ref.pages}")
            parts.append(".")
            return "".join(parts)

        case "ieee":
            if authors:
                initials = []
                for a in authors[:3]:
                    parts_a = a.replace(",", " ").split()
                    if len(parts_a) >= 2:
                        initials.append(f"{parts_a[1][0]}. {parts_a[0]}")
                    else:
                        initials.append(a)
                author_str = ", ".join(initials)
                if len(authors) > 3:
                    author_str += " et al."
            parts = [f'{author_str}, "{title},"']
            if journal:
                parts.append(f" *{journal}*")
                if ref.volume:
                    parts.append(f", vol. {ref.volume}")
                if ref.number:
                    parts.append(f", no. {ref.number}")
                if ref.pages:
                    parts.append(f", pp. {ref.pages}")
                parts.append(f", {year}")
            parts.append(".")
            return "".join(parts)

        case _:
            return f"{author_str} ({year}). {title}. {journal}."


# ── Endnote XML export ──────────────────────────────────────────

def ref_to_xml_element(ref: Reference) -> Element:
    """Convert a Reference to an Endnote XML <record> element."""
    record = Element("record")

    SubElement(record, "rec-number").text = str(ref.id)

    ref_type = SubElement(record, "ref-type")
    ref_type.set("name", ref.ref_type_name)
    ref_type.text = str(ref.reference_type)

    contributors = SubElement(record, "contributors")
    authors_el = SubElement(contributors, "authors")
    for a in ref.authors_list:
        SubElement(authors_el, "author").text = a

    if ref.secondary_author:
        sec_authors = SubElement(contributors, "secondary-authors")
        for a in ref.secondary_author.replace("\r", "\n").split("\n"):
            if a.strip():
                SubElement(sec_authors, "author").text = a.strip()

    titles = SubElement(record, "titles")
    SubElement(titles, "title").text = ref.title
    if ref.journal:
        SubElement(titles, "secondary-title").text = ref.journal
    if ref.tertiary_title:
        SubElement(titles, "tertiary-title").text = ref.tertiary_title

    if ref.pages:
        SubElement(record, "pages").text = ref.pages
    if ref.volume:
        SubElement(record, "volume").text = ref.volume
    if ref.number:
        SubElement(record, "number").text = ref.number

    dates = SubElement(record, "dates")
    SubElement(dates, "year").text = ref.year
    if ref.date:
        SubElement(dates, "pub-dates").text = ref.date

    if ref.isbn:
        SubElement(record, "isbn").text = ref.isbn
    if ref.abstract:
        SubElement(record, "abstract").text = ref.abstract
    if ref.notes:
        SubElement(record, "notes").text = ref.notes
    if ref.research_notes:
        SubElement(record, "research-notes").text = ref.research_notes
    if ref.doi:
        SubElement(record, "electronic-resource-num").text = ref.doi
    if ref.url:
        urls = SubElement(record, "urls")
        related = SubElement(urls, "related-urls")
        SubElement(related, "url").text = ref.url
    if ref.keywords:
        kws = SubElement(record, "keywords")
        for kw in ref.keywords.replace("\r", "\n").split("\n"):
            if kw.strip():
                SubElement(kws, "keyword").text = kw.strip()
    if ref.language:
        SubElement(record, "language").text = ref.language
    if ref.publisher:
        SubElement(record, "publisher").text = ref.publisher

    return record


def refs_to_xml(refs: list[Reference], library_name: str = "") -> str:
    """Export references as Endnote XML."""
    root = Element("xml")
    records = SubElement(root, "records")
    for ref in refs:
        records.append(ref_to_xml_element(ref))
    indent(root, space="  ")
    xml_decl = '<?xml version="1.0" encoding="UTF-8"?>\n'
    return xml_decl + tostring(root, encoding="unicode")


def export_group_xml(
    lib: EndnoteLibrary,
    group_set_name: Optional[str] = None,
    group_name: Optional[str] = None,
    output_dir: str | Path = ".",
) -> list[Path]:
    """Export references as XML files organized by group hierarchy.

    Returns list of created files.
    """
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    created = []

    tree = lib.get_group_tree()

    for gs in tree:
        # Filter by group set name if specified
        if group_set_name and gs.name.lower() != group_set_name.lower():
            continue

        for g in gs.groups:
            # Filter by group name if specified
            if group_name and g.name.lower() != group_name.lower():
                continue

            if not g.member_ids:
                continue

            # Fetch full references
            refs = []
            for rid in g.member_ids:
                ref = lib.get_ref(rid)
                if ref and ref.trash_state == 0:
                    refs.append(ref)

            if not refs:
                continue

            # Build filename: "GroupSet-Group.xml"
            safe_set = re.sub(r'[<>:"/\\|?*]', '_', gs.name)
            safe_group = re.sub(r'[<>:"/\\|?*]', '_', g.name)
            filename = f"{safe_set}-{safe_group}.xml" if gs.name != "(未分类)" else f"{safe_group}.xml"

            filepath = output / filename
            xml_content = refs_to_xml(refs, library_name=f"{gs.name}/{g.name}")
            filepath.write_text(xml_content, encoding="utf-8")
            created.append(filepath)

    return created


# ── PDF copy ────────────────────────────────────────────────────

def copy_pdf(
    lib: EndnoteLibrary,
    ref: Reference,
    dest_dir: str | Path,
    rename: bool = True,
) -> Optional[Path]:
    """Copy the main PDF of a reference to dest_dir.

    If rename=True, renames to Author_Year_TitleShort.pdf
    Returns the destination path, or None if no PDF found.
    """
    main_pdf = lib.get_main_pdf(ref.id)
    if main_pdf is None:
        return None

    source = lib.resolve_attachment_path(main_pdf)
    if source is None:
        return None

    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)

    if rename:
        # Build normalized filename
        surname = re.sub(r"[^a-zA-Z\u4e00-\u9fff]", "", ref.first_author_surname)
        title_short = ref.title[:40].strip() if ref.title else "Untitled"
        title_short = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]", "", title_short)
        filename = f"{surname}_{ref.year}_{title_short}.pdf"
    else:
        filename = main_pdf.filename

    target = dest / filename
    # Avoid overwrite
    if target.exists():
        stem = target.stem
        i = 1
        while target.exists():
            target = dest / f"{stem}_{i}.pdf"
            i += 1

    shutil.copy2(str(source), str(target))
    return target
