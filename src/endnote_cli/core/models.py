"""Data models for EndNote library entities."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Reference:
    """A single reference (row in refs table)."""

    id: int
    reference_type: int = 0  # 0=Journal, 1=Book, 2=BookSection, 3=Conference...
    trash_state: int = 0
    author: str = ""
    year: str = ""
    title: str = ""
    pages: str = ""
    secondary_title: str = ""  # Journal / Book Title
    volume: str = ""
    number: str = ""
    number_of_volumes: str = ""
    secondary_author: str = ""  # Editor
    place_published: str = ""
    publisher: str = ""
    subsidiary_author: str = ""
    edition: str = ""
    keywords: str = ""
    type_of_work: str = ""
    date: str = ""
    abstract: str = ""
    label: str = ""
    url: str = ""
    tertiary_title: str = ""  # Series / Conference Name
    tertiary_author: str = ""
    notes: str = ""
    isbn: str = ""
    custom_1: str = ""
    custom_2: str = ""
    custom_3: str = ""
    custom_4: str = ""
    alternate_title: str = ""
    accession_number: str = ""
    call_number: str = ""
    short_title: str = ""
    custom_5: str = ""
    custom_6: str = ""
    section: str = ""
    original_publication: str = ""
    reprint_edition: str = ""
    reviewed_item: str = ""
    author_address: str = ""
    caption: str = ""
    custom_7: str = ""
    electronic_resource_number: str = ""  # DOI
    translated_author: str = ""
    translated_title: str = ""
    name_of_database: str = ""
    database_provider: str = ""
    research_notes: str = ""
    language: str = ""
    access_date: str = ""
    last_modified_date: str = ""
    read_status: str = ""
    rating: str = ""
    added_to_library: int = 0  # Unix timestamp
    record_last_updated: int = 0  # Unix timestamp

    # Populated after query
    attachments: list[Attachment] = field(default_factory=list)
    tag_ids: list[int] = field(default_factory=list)

    @property
    def doi(self) -> str:
        return self.electronic_resource_number

    @property
    def journal(self) -> str:
        return self.secondary_title

    @property
    def keywords_list(self) -> list[str]:
        """Split keywords by Endnote's \\r separator."""
        if not self.keywords:
            return []
        return [k.strip() for k in self.keywords.split("\r") if k.strip()]

    @property
    def authors_list(self) -> list[str]:
        """Split author field into individual names."""
        if not self.author:
            return []
        # EndNote stores authors with \r (CR) separator
        return [a.strip() for a in self.author.split("\r") if a.strip()]

    @property
    def first_author_surname(self) -> str:
        authors = self.authors_list
        if not authors:
            return "Unknown"
        # Handle "Last, First" format
        first = authors[0]
        if "," in first:
            return first.split(",")[0].strip()
        # Handle "First Last" format
        parts = first.strip().split()
        return parts[-1] if parts else "Unknown"

    @property
    def ref_type_name(self) -> str:
        type_map = {
            0: "Journal Article",
            1: "Book",
            2: "Book Section",
            3: "Conference Proceedings",
            4: "Conference Paper",
            29: "Electronic Article",
            36: "Online Database",
            47: "Preprint",
        }
        return type_map.get(self.reference_type, f"Type {self.reference_type}")


# Columns in refs table that map to Reference fields (order matters for SELECT *)
REFS_COLUMNS = [
    "id", "trash_state", "text_styles", "reference_type",
    "author", "year", "title", "pages", "secondary_title",
    "volume", "number", "number_of_volumes", "secondary_author",
    "place_published", "publisher", "subsidiary_author", "edition",
    "keywords", "type_of_work", "date", "abstract", "label", "url",
    "tertiary_title", "tertiary_author", "notes", "isbn",
    "custom_1", "custom_2", "custom_3", "custom_4",
    "alternate_title", "accession_number", "call_number", "short_title",
    "custom_5", "custom_6", "section", "original_publication",
    "reprint_edition", "reviewed_item", "author_address", "caption",
    "custom_7", "electronic_resource_number", "translated_author",
    "translated_title", "name_of_database", "database_provider",
    "research_notes", "language", "access_date", "last_modified_date",
    "record_properties", "added_to_library", "record_last_updated",
    "reserved3", "fulltext_downloads", "read_status", "rating",
    "reserved7", "reserved8", "reserved9", "reserved10",
]

# Fields safe to SELECT for building a Reference object
REFS_SELECT_FIELDS = [
    "id", "reference_type", "trash_state",
    "author", "year", "title", "pages", "secondary_title",
    "volume", "number", "number_of_volumes", "secondary_author",
    "place_published", "publisher", "subsidiary_author", "edition",
    "keywords", "type_of_work", "date", "abstract", "label", "url",
    "tertiary_title", "tertiary_author", "notes", "isbn",
    "custom_1", "custom_2", "custom_3", "custom_4",
    "alternate_title", "accession_number", "call_number", "short_title",
    "custom_5", "custom_6", "section", "original_publication",
    "reprint_edition", "reviewed_item", "author_address", "caption",
    "custom_7", "electronic_resource_number", "translated_author",
    "translated_title", "name_of_database", "database_provider",
    "research_notes", "language", "access_date", "last_modified_date",
    "read_status", "rating",
    "added_to_library", "record_last_updated",
]

# Fields that are safe to UPDATE.
#
# The `refs__refs_ord_AU` trigger calls EN_MAKE_SORT_KEY on
# title / author / year, so updates to those three must be avoided.
# Every other TEXT column on `refs` that isn't derived / indexed is
# safe — the writer bypasses the sort-key trigger inside a tx anyway.
SAFE_WRITE_FIELDS = {
    "research_notes", "notes", "keywords", "read_status", "rating",
    "label", "caption",
    "custom_1", "custom_2", "custom_3", "custom_4",
    "custom_5", "custom_6", "custom_7",
    "translated_title", "translated_author",
}

# Human-readable aliases for search
FIELD_ALIASES = {
    "doi": "electronic_resource_number",
    "journal": "secondary_title",
    "editor": "secondary_author",
    "series": "tertiary_title",
    "issn": "isbn",
    "address": "author_address",
    "database": "name_of_database",
    "provider": "database_provider",
}

# All searchable TEXT fields
SEARCHABLE_FIELDS = {f for f in REFS_SELECT_FIELDS if f not in (
    "id", "reference_type", "trash_state", "added_to_library", "record_last_updated",
)} | set(FIELD_ALIASES.keys())


@dataclass
class Attachment:
    """A file attached to a reference (row in file_res)."""

    refs_id: int
    file_path: str  # relative path: "{hash_dir}/{filename}"
    file_type: int  # 1 = regular attachment
    file_pos: int  # order index

    @property
    def filename(self) -> str:
        return self.file_path.split("/")[-1] if "/" in self.file_path else self.file_path

    @property
    def extension(self) -> str:
        return self.filename.rsplit(".", 1)[-1].lower() if "." in self.filename else ""

    @property
    def is_pdf(self) -> bool:
        return self.extension == "pdf"

    @property
    def is_supplement(self) -> bool:
        name_lower = self.filename.lower()
        return any(kw in name_lower for kw in (
            "supplement", "supp-", "supp0", "supp1", "supp2",
            "mmc1", "mmc2", "mmc3",
            "supporting_information", "supporting-information",
            "appendix",
            "_app1", "_app2", "-app1", "-app2",
        ))


@dataclass
class Tag:
    """A color tag (row in tag_groups)."""

    group_id: int
    name: str
    color: str  # hex color, e.g. "de3131"
    created: Optional[int] = None
    modified: Optional[int] = None


@dataclass
class Group:
    """A custom group (row in groups)."""

    group_id: int
    name: str
    uuid: str = ""
    member_ids: list[int] = field(default_factory=list)
    created: Optional[int] = None
    modified: Optional[int] = None
    group_set_id: Optional[int] = None  # which GroupSet this belongs to


@dataclass
class GroupSet:
    """A group set (parent folder for groups), stored in misc table."""

    set_id: int  # subcode in misc
    name: str
    uuid: str = ""
    groups: list[Group] = field(default_factory=list)


@dataclass
class LibraryInfo:
    """Summary statistics for a library."""

    path: str
    total_refs: int = 0
    trashed_refs: int = 0
    groups_count: int = 0
    group_sets_count: int = 0
    tags_count: int = 0
    pdf_count: int = 0
    doi_count: int = 0
    refs_with_abstract: int = 0
