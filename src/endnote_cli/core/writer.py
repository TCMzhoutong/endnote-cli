"""Safe write operations for EndNote .enl databases.

Only writes to fields that do NOT trigger EN_MAKE_SORT_KEY:
- research_notes, notes, keywords, read_status, rating, label, caption
- custom_1 through custom_7
- tag_members (FTS5 table for color tags)
- file_res (attachment registry)
"""

from __future__ import annotations

import os
import shutil
import sqlite3
from pathlib import Path
from typing import Optional

from .models import SAFE_WRITE_FIELDS
from .reader import EndnoteLibrary


class EndnoteWriter:
    """Write operations on an EndNote .enl database. Requires read-write access.

    Endnote maintains TWO copies of the database:
    - .enl file (primary)
    - .Data/sdb/sdb.eni (display index, same schema)
    Endnote reads from sdb.eni at runtime. We must write to BOTH.
    """

    def __init__(self, enl_path: str | Path):
        self.path = Path(enl_path)
        if not self.path.exists():
            raise FileNotFoundError(f"Library not found: {self.path}")
        self._conn: Optional[sqlite3.Connection] = None
        self._sdb_conn: Optional[sqlite3.Connection] = None

    @property
    def sdb_path(self) -> Path:
        return self.path.with_suffix(".Data") / "sdb" / "sdb.eni"

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.path))
        return self._conn

    @property
    def sdb_conn(self) -> Optional[sqlite3.Connection]:
        if self._sdb_conn is None and self.sdb_path.exists():
            self._sdb_conn = sqlite3.connect(str(self.sdb_path))
        return self._sdb_conn

    @property
    def pdf_dir(self) -> Path:
        return self.path.with_suffix(".Data") / "PDF"

    def _exec_both(self, sql: str, params: tuple = ()) -> None:
        """Execute SQL on both .enl and sdb.eni."""
        self.conn.execute(sql, params)
        if self.sdb_conn:
            self.sdb_conn.execute(sql, params)

    def _commit_both(self) -> None:
        """Commit to both databases."""
        self.conn.commit()
        if self.sdb_conn:
            self.sdb_conn.commit()

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None
        if self._sdb_conn:
            self._sdb_conn.close()
            self._sdb_conn = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def _ref_exists(self, ref_id: int) -> bool:
        row = self.conn.execute("SELECT id FROM refs WHERE id = ?", (ref_id,)).fetchone()
        return row is not None

    # ── Field writes ────────────────────────────────────────────

    def write_field(self, ref_id: int, field: str, value: str) -> None:
        """Overwrite a safe field with a new value."""
        if field not in SAFE_WRITE_FIELDS:
            raise ValueError(
                f"Field '{field}' is not safe to write. "
                f"Safe fields: {', '.join(sorted(SAFE_WRITE_FIELDS))}"
            )
        if not self._ref_exists(ref_id):
            raise ValueError(f"Reference {ref_id} not found")
        self._exec_both(
            f"UPDATE refs SET {field} = ? WHERE id = ?", (value, ref_id)
        )
        self._commit_both()

    def clear_field(self, ref_id: int, field: str) -> None:
        """Clear (empty) a safe field."""
        self.write_field(ref_id, field, "")

    def append_field(self, ref_id: int, field: str, value: str, separator: str = "\r") -> None:
        """Append text to an existing field value.

        Default separator is \\r (CR) which is Endnote's native multi-value separator.
        """
        if field not in SAFE_WRITE_FIELDS:
            raise ValueError(f"Field '{field}' is not safe to write.")
        if not self._ref_exists(ref_id):
            raise ValueError(f"Reference {ref_id} not found")
        current = self.conn.execute(
            f"SELECT {field} FROM refs WHERE id = ?", (ref_id,)
        ).fetchone()[0] or ""
        new_value = f"{current}{separator}{value}" if current.strip() else value
        self._exec_both(
            f"UPDATE refs SET {field} = ? WHERE id = ?", (new_value, ref_id)
        )
        self._commit_both()

    def write_research_notes(self, ref_id: int, text: str) -> None:
        """Write to research_notes field."""
        self.write_field(ref_id, "research_notes", text)

    def append_research_notes(self, ref_id: int, text: str) -> None:
        """Append to research_notes field."""
        self.append_field(ref_id, "research_notes", text)

    def write_notes(self, ref_id: int, text: str) -> None:
        self.write_field(ref_id, "notes", text)

    def append_notes(self, ref_id: int, text: str) -> None:
        self.append_field(ref_id, "notes", text)

    def write_read_status(self, ref_id: int, status: str = "1") -> None:
        """Set read status. '1' = read, '0' = unread, '' = not set."""
        self.write_field(ref_id, "read_status", status)

    def write_rating(self, ref_id: int, rating: str) -> None:
        self.write_field(ref_id, "rating", rating)

    def write_label(self, ref_id: int, label: str) -> None:
        self.write_field(ref_id, "label", label)

    # ── Keywords ────────────────────────────────────────────────

    def _split_multivalue(self, text: str) -> list[str]:
        """Split a multi-value field by Endnote's \\r separator."""
        return [v.strip() for v in text.split("\r") if v.strip()]

    def append_keyword(self, ref_id: int, keyword: str) -> None:
        """Add a keyword if not already present."""
        if not self._ref_exists(ref_id):
            raise ValueError(f"Reference {ref_id} not found")
        current = self.conn.execute(
            "SELECT keywords FROM refs WHERE id = ?", (ref_id,)
        ).fetchone()[0] or ""
        existing = {k.lower() for k in self._split_multivalue(current)}
        if keyword.strip().lower() not in existing:
            new_val = f"{current}\r{keyword}" if current.strip() else keyword
            self._exec_both(
                "UPDATE refs SET keywords = ? WHERE id = ?", (new_val, ref_id)
            )
            self._commit_both()

    def remove_keyword(self, ref_id: int, keyword: str) -> None:
        """Remove a keyword."""
        if not self._ref_exists(ref_id):
            raise ValueError(f"Reference {ref_id} not found")
        current = self.conn.execute(
            "SELECT keywords FROM refs WHERE id = ?", (ref_id,)
        ).fetchone()[0] or ""
        keywords = [k for k in self._split_multivalue(current)
                     if k.lower() != keyword.strip().lower()]
        new_val = "\r".join(keywords)
        self._exec_both(
            "UPDATE refs SET keywords = ? WHERE id = ?", (new_val, ref_id)
        )
        self._commit_both()

    # ── Tags (color labels) ────────────────────────────────────

    # Endnote 21 only renders these 7 preset colors; custom hex shows as gray.
    PRESET_COLORS = {
        "red": "de3131",
        "orange": "f6a33a",
        "yellow": "f5d44a",
        "green": "53cf64",
        "blue": "4a90d9",
        "purple": "5231de",
        "gray": "b8b8b8",
    }

    def create_tag(self, name: str, color: str = "blue") -> int:
        """Create a new color tag. Returns the new tag's group_id.

        Args:
            name: Tag display name (e.g. "预印本")
            color: Preset name (red/orange/yellow/green/blue/purple/gray)
                   or hex value. NOTE: Endnote 21 only renders preset colors;
                   custom hex values display as gray.
        """
        import uuid
        import time

        color = color.lstrip("#")
        # Map preset name to hex
        color = self.PRESET_COLORS.get(color.lower(), color)
        tag_uuid = str(uuid.uuid4()).upper()
        now = int(time.time())
        spec_xml = (
            f'<?xml version="1.0" encoding="UTF-8"?>'
            f'<group version="1"><ids><id>{tag_uuid}</id>'
            f'<name>{name}</name></ids>'
            f'<times><created format="UTC">{now}</created>'
            f'<modified format="UTC">{now}</modified></times>'
            f'<rules><rule>TYPE;10</rule>'
            f'<rule>COLOR;{color}</rule></rules></group>'
        )
        spec_bytes = spec_xml.encode("utf-8")
        self.conn.execute(
            "INSERT INTO tag_groups (spec) VALUES (?)",
            (spec_bytes,),
        )
        self.conn.commit()
        # Get the auto-generated group_id from enl
        new_id = self.conn.execute(
            "SELECT group_id FROM tag_groups ORDER BY group_id DESC LIMIT 1"
        ).fetchone()[0]
        # Write to sdb.eni with the SAME group_id
        if self.sdb_conn:
            self.sdb_conn.execute(
                "INSERT INTO tag_groups (group_id, spec) VALUES (?, ?)",
                (new_id, spec_bytes),
            )
            self.sdb_conn.commit()
        return new_id

    def _update_tag_members(self, conn: sqlite3.Connection, ref_id: int, new_val: str) -> None:
        """Update tag_members FTS5 table on a single connection."""
        conn.execute("DELETE FROM tag_members WHERE rowid = ?", (ref_id,))
        conn.execute(
            "INSERT INTO tag_members (rowid, tag_ids) VALUES (?, ?)",
            (ref_id, new_val),
        )

    def write_tag(self, ref_id: int, tag_id: int) -> None:
        """Add a color tag to a reference."""
        if not self._ref_exists(ref_id):
            raise ValueError(f"Reference {ref_id} not found")
        row = self.conn.execute(
            "SELECT tag_ids FROM tag_members WHERE rowid = ?", (ref_id,)
        ).fetchone()
        if row:
            current_ids = set(row[0].split()) if row[0] else set()
            current_ids.add(str(tag_id))
            new_val = " " + " ".join(sorted(current_ids)) + " "
        else:
            new_val = f" {tag_id} "
        # FTS5 tables need DELETE + INSERT; do on both dbs
        self._update_tag_members(self.conn, ref_id, new_val)
        if self.sdb_conn:
            self._update_tag_members(self.sdb_conn, ref_id, new_val)
        self._commit_both()

    def remove_tag(self, ref_id: int, tag_id: int) -> None:
        """Remove a color tag from a reference."""
        row = self.conn.execute(
            "SELECT tag_ids FROM tag_members WHERE rowid = ?", (ref_id,)
        ).fetchone()
        if not row:
            return
        current_ids = set(row[0].split()) if row[0] else set()
        current_ids.discard(str(tag_id))
        new_val = " " + " ".join(sorted(current_ids)) + " " if current_ids else " "
        self._update_tag_members(self.conn, ref_id, new_val)
        if self.sdb_conn:
            self._update_tag_members(self.sdb_conn, ref_id, new_val)
        self._commit_both()

    # ── Attachments ─────────────────────────────────────────────

    def add_attachment(self, ref_id: int, source_file: str | Path) -> str:
        """Copy a file into the .Data/PDF/ directory and register it.

        Returns the relative path stored in file_res.
        """
        source = Path(source_file)
        if not source.exists():
            raise FileNotFoundError(f"Source file not found: {source}")
        if not self._ref_exists(ref_id):
            raise ValueError(f"Reference {ref_id} not found")

        # Create a hash-like subdirectory (mimic Endnote's pattern)
        hash_dir = str(abs(hash(str(source) + str(ref_id))) % (10**10)).zfill(10)
        target_dir = self.pdf_dir / hash_dir
        target_dir.mkdir(parents=True, exist_ok=True)

        target = target_dir / source.name
        shutil.copy2(str(source), str(target))

        # Find next file_pos
        max_pos = self.conn.execute(
            "SELECT MAX(file_pos) FROM file_res WHERE refs_id = ?", (ref_id,)
        ).fetchone()[0]
        next_pos = (max_pos + 1) if max_pos is not None else 0

        rel_path = f"{hash_dir}/{source.name}"
        self._exec_both(
            "INSERT INTO file_res (refs_id, file_path, file_type, file_pos) VALUES (?, ?, 1, ?)",
            (ref_id, rel_path, next_pos),
        )
        self._commit_both()
        return rel_path

    def rename_attachment(self, ref_id: int, file_pos: int, new_filename: str) -> str:
        """Rename an attachment file on disk and update both databases.

        Args:
            ref_id: Reference ID
            file_pos: Attachment position (0 = first/main file)
            new_filename: New filename (just the name, not path)

        Returns the new relative path.
        """
        row = self.conn.execute(
            "SELECT file_path FROM file_res WHERE refs_id = ? AND file_pos = ?",
            (ref_id, file_pos),
        ).fetchone()
        if not row:
            raise ValueError(f"No attachment at pos {file_pos} for ref {ref_id}")

        old_rel = row[0]
        hash_dir = old_rel.split("/")[0] if "/" in old_rel else ""
        old_full = self.pdf_dir / old_rel

        new_rel = f"{hash_dir}/{new_filename}" if hash_dir else new_filename
        new_full = self.pdf_dir / new_rel

        # Rename on disk
        if old_full.exists():
            old_full.rename(new_full)

        # Update both databases
        self._exec_both(
            "UPDATE file_res SET file_path = ? WHERE refs_id = ? AND file_pos = ?",
            (new_rel, ref_id, file_pos),
        )
        self._commit_both()
        return new_rel

    def rename_main_pdf(self, ref_id: int, new_filename: str) -> str:
        """Rename the main PDF (pos=0) of a reference.

        If new_filename has no extension, '.pdf' is appended.
        """
        if "." not in new_filename:
            new_filename += ".pdf"
        return self.rename_attachment(ref_id, 0, new_filename)
