"""Read-only access to EndNote .enl SQLite databases."""

from __future__ import annotations

import re
import sqlite3
import struct
from pathlib import Path
from typing import Optional

from .models import (
    Attachment,
    Group,
    GroupSet,
    LibraryInfo,
    Reference,
    REFS_SELECT_FIELDS,
    Tag,
)


class EndnoteLibrary:
    """Read-only accessor for an EndNote .enl SQLite database."""

    def __init__(self, enl_path: str | Path):
        self.path = Path(enl_path)
        if not self.path.exists():
            raise FileNotFoundError(f"Library not found: {self.path}")
        if not self.path.suffix == ".enl":
            raise ValueError(f"Not an .enl file: {self.path}")
        self._conn: Optional[sqlite3.Connection] = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            # Use str(path) directly — URI mode fails on Windows with
            # non-ASCII characters (Chinese) in the path.
            self._conn = sqlite3.connect(str(self.path))
            self._conn.execute("PRAGMA query_only = ON")  # enforce read-only
            self._conn.row_factory = sqlite3.Row
        return self._conn

    @property
    def data_dir(self) -> Path:
        """The .Data directory alongside the .enl file."""
        return self.path.with_suffix(".Data")

    @property
    def pdf_dir(self) -> Path:
        return self.data_dir / "PDF"

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    # ── References ──────────────────────────────────────────────

    def _row_to_ref(self, row: sqlite3.Row) -> Reference:
        """Convert a database row to a Reference object."""
        data = {}
        for col in REFS_SELECT_FIELDS:
            val = row[col]
            data[col] = val if val is not None else ""
        # Fix integer fields
        for int_field in ("id", "reference_type", "trash_state",
                          "added_to_library", "record_last_updated"):
            data[int_field] = int(data[int_field]) if data[int_field] else 0
        return Reference(**data)

    def get_ref(self, ref_id: int) -> Optional[Reference]:
        """Get a single reference by ID."""
        fields = ", ".join(REFS_SELECT_FIELDS)
        row = self.conn.execute(
            f"SELECT {fields} FROM refs WHERE id = ?", (ref_id,)
        ).fetchone()
        if row is None:
            return None
        ref = self._row_to_ref(row)
        ref.attachments = self.get_attachments(ref_id)
        ref.tag_ids = self._get_tag_ids(ref_id)
        return ref

    def list_refs(
        self,
        include_trashed: bool = False,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> list[Reference]:
        """List all references."""
        fields = ", ".join(REFS_SELECT_FIELDS)
        sql = f"SELECT {fields} FROM refs"
        if not include_trashed:
            sql += " WHERE trash_state = 0"
        sql += " ORDER BY id"
        if limit is not None:
            sql += f" LIMIT {limit} OFFSET {offset}"
        rows = self.conn.execute(sql).fetchall()
        return [self._row_to_ref(r) for r in rows]

    def count_refs(self, include_trashed: bool = False) -> int:
        sql = "SELECT COUNT(*) FROM refs"
        if not include_trashed:
            sql += " WHERE trash_state = 0"
        return self.conn.execute(sql).fetchone()[0]

    # ── Attachments ─────────────────────────────────────────────

    def get_attachments(self, ref_id: int) -> list[Attachment]:
        rows = self.conn.execute(
            "SELECT refs_id, file_path, file_type, file_pos "
            "FROM file_res WHERE refs_id = ? ORDER BY file_pos",
            (ref_id,),
        ).fetchall()
        return [Attachment(
            refs_id=r["refs_id"],
            file_path=r["file_path"],
            file_type=r["file_type"],
            file_pos=r["file_pos"],
        ) for r in rows]

    def get_main_pdf(self, ref_id: int) -> Optional[Attachment]:
        """Get the main PDF for a reference (pos=0, with supplement check)."""
        attachments = self.get_attachments(ref_id)
        pdfs = [a for a in attachments if a.is_pdf]
        if not pdfs:
            return None
        if len(pdfs) == 1:
            return pdfs[0]
        # Multiple PDFs: prefer pos=0 unless it looks like a supplement
        pos0 = pdfs[0]
        if not pos0.is_supplement:
            return pos0
        # pos=0 is supplement, try to find non-supplement
        for pdf in pdfs[1:]:
            if not pdf.is_supplement:
                return pdf
        return pos0  # fallback

    def resolve_attachment_path(self, attachment: Attachment) -> Optional[Path]:
        """Resolve an attachment's relative path to absolute path."""
        full = self.pdf_dir / attachment.file_path
        return full if full.exists() else None

    # ── Tags ────────────────────────────────────────────────────

    def list_tags(self) -> list[Tag]:
        rows = self.conn.execute("SELECT group_id, spec FROM tag_groups").fetchall()
        tags = []
        for r in rows:
            spec = r["spec"]
            xml = spec.decode("utf-8") if isinstance(spec, bytes) else spec
            name_m = re.search(r"<name>([^<]+)</name>", xml)
            color_m = re.search(r"COLOR;([a-f0-9]+)", xml)
            created_m = re.search(r"<created[^>]*>(\d+)</created>", xml)
            modified_m = re.search(r"<modified[^>]*>(\d+)</modified>", xml)
            tags.append(Tag(
                group_id=r["group_id"],
                name=name_m.group(1) if name_m else f"Tag {r['group_id']}",
                color=color_m.group(1) if color_m else "000000",
                created=int(created_m.group(1)) if created_m else None,
                modified=int(modified_m.group(1)) if modified_m else None,
            ))
        return tags

    def _get_tag_ids(self, ref_id: int) -> list[int]:
        """Get tag IDs assigned to a reference.

        `tag_members.tag_ids` stores ids as space-separated lowercase hex
        (EndNote convention): "1".."9", "a"..."f", "10" (=16), etc.
        """
        row = self.conn.execute(
            "SELECT tag_ids FROM tag_members WHERE rowid = ?", (ref_id,)
        ).fetchone()
        if not row or not row["tag_ids"] or row["tag_ids"].strip() == "":
            return []
        out = []
        for tok in row["tag_ids"].split():
            try:
                out.append(int(tok, 16))
            except ValueError:
                pass
        return out

    def get_refs_by_tag(self, tag_id: int) -> list[int]:
        """Get reference IDs that have a specific tag.

        Tokens in `tag_ids` are lowercase hex per EndNote convention.
        """
        rows = self.conn.execute(
            "SELECT rowid, tag_ids FROM tag_members"
        ).fetchall()
        tag_hex = format(tag_id, "x")
        result = []
        for r in rows:
            ids = r["tag_ids"].split() if r["tag_ids"] else []
            if tag_hex in ids:
                result.append(r["rowid"])
        return result

    # ── Groups ──────────────────────────────────────────────────

    def _parse_group_members(self, members_blob: bytes) -> list[int]:
        """Parse the binary members blob into a list of reference IDs."""
        if not members_blob or len(members_blob) < 8:
            return []
        ids = []
        for i in range(0, len(members_blob), 4):
            if i + 4 <= len(members_blob):
                val = struct.unpack("<i", members_blob[i : i + 4])[0]
                if 0 < val < 100000:  # Filter out header values like 33554432
                    ids.append(val)
        return ids

    def list_groups(self) -> list[Group]:
        """List all custom groups."""
        # Get group-to-set mapping
        group_to_set = self._get_group_set_mapping()

        rows = self.conn.execute("SELECT group_id, spec, members FROM groups").fetchall()
        groups = []
        for r in rows:
            spec = r["spec"]
            xml = spec.decode("utf-8") if isinstance(spec, bytes) else spec
            name_m = re.search(r"<name>([^<]+)</name>", xml)
            uuid_m = re.search(r"<id>([^<]+)</id>", xml)
            created_m = re.search(r"<created[^>]*>(\d+)</created>", xml)
            modified_m = re.search(r"<modified[^>]*>(\d+)</modified>", xml)
            member_ids = self._parse_group_members(r["members"])
            gid = r["group_id"]
            groups.append(Group(
                group_id=gid,
                name=name_m.group(1) if name_m else f"Group {gid}",
                uuid=uuid_m.group(1) if uuid_m else "",
                member_ids=member_ids,
                created=int(created_m.group(1)) if created_m else None,
                modified=int(modified_m.group(1)) if modified_m else None,
                group_set_id=group_to_set.get(gid),
            ))
        return groups

    def get_group_by_name(self, name: str) -> Optional[Group]:
        """Find a group by name (case-insensitive)."""
        for g in self.list_groups():
            if g.name.lower() == name.lower():
                return g
        return None

    # ── Group Sets ──────────────────────────────────────────────

    def list_group_sets(self) -> list[GroupSet]:
        """List all group sets (parent folders)."""
        rows = self.conn.execute(
            "SELECT subcode, value FROM misc WHERE code = 17"
        ).fetchall()
        sets = []
        for r in rows:
            val = r["value"]
            xml = val.decode("utf-8") if isinstance(val, bytes) else val
            name_m = re.search(r"<name>([^<]+)</name>", xml)
            uuid_m = re.search(r"<id>([^<]+)</id>", xml)
            sets.append(GroupSet(
                set_id=r["subcode"],
                name=name_m.group(1) if name_m else f"Set {r['subcode']}",
                uuid=uuid_m.group(1) if uuid_m else "",
            ))
        return sets

    def _get_group_set_mapping(self) -> dict[int, int]:
        """Get mapping of group_id → set_id from misc code=4."""
        row = self.conn.execute(
            "SELECT value FROM misc WHERE code = 4 AND subcode = 0"
        ).fetchone()
        if not row:
            return {}
        raw = row["value"]
        text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
        parts = text.strip().split()
        mapping = {}
        for i in range(0, len(parts) - 1, 2):
            try:
                gid = int(parts[i])
                sid = int(parts[i + 1])
                mapping[gid] = sid
            except ValueError:
                continue
        return mapping

    def get_group_tree(self) -> list[GroupSet]:
        """Build the full hierarchy: GroupSet → Groups."""
        sets = {s.set_id: s for s in self.list_group_sets()}
        groups = self.list_groups()

        for g in groups:
            if g.group_set_id is not None and g.group_set_id in sets:
                sets[g.group_set_id].groups.append(g)

        # Collect unassigned groups
        unassigned = [g for g in groups if g.group_set_id is None]
        if unassigned:
            orphan_set = GroupSet(set_id=-1, name="(未分类)", groups=unassigned)
            result = list(sets.values()) + [orphan_set]
        else:
            result = list(sets.values())

        return result

    # ── Library Info ────────────────────────────────────────────

    def get_info(self) -> LibraryInfo:
        info = LibraryInfo(path=str(self.path))
        info.total_refs = self.conn.execute(
            "SELECT COUNT(*) FROM refs WHERE trash_state = 0"
        ).fetchone()[0]
        info.trashed_refs = self.conn.execute(
            "SELECT COUNT(*) FROM refs WHERE trash_state != 0"
        ).fetchone()[0]
        info.groups_count = self.conn.execute(
            "SELECT COUNT(*) FROM groups"
        ).fetchone()[0]
        info.group_sets_count = self.conn.execute(
            "SELECT COUNT(*) FROM misc WHERE code = 17"
        ).fetchone()[0]
        info.tags_count = self.conn.execute(
            "SELECT COUNT(*) FROM tag_groups"
        ).fetchone()[0]
        info.pdf_count = self.conn.execute(
            "SELECT COUNT(DISTINCT refs_id) FROM file_res WHERE file_type = 1"
        ).fetchone()[0]
        info.doi_count = self.conn.execute(
            "SELECT COUNT(*) FROM refs WHERE trash_state = 0 "
            "AND electronic_resource_number != ''"
        ).fetchone()[0]
        info.refs_with_abstract = self.conn.execute(
            "SELECT COUNT(*) FROM refs WHERE trash_state = 0 AND abstract != ''"
        ).fetchone()[0]
        return info
