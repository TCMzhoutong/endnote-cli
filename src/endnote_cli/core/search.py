"""Search engine with Endnote-compatible operators and boolean logic."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from .models import FIELD_ALIASES, Reference, REFS_SELECT_FIELDS
from .reader import EndnoteLibrary


class Operator(str, Enum):
    CONTAINS = "contains"
    IS = "is"
    LT = "lt"
    LTE = "lte"
    GT = "gt"
    GTE = "gte"
    BEGINS_WITH = "begins-with"
    ENDS_WITH = "ends-with"
    WORD_BEGINS = "word-begins"


class BooleanOp(str, Enum):
    AND = "and"
    OR = "or"
    NOT = "not"


@dataclass
class Condition:
    """A single search condition."""

    field: str
    operator: Operator
    value: str

    def resolve_field(self) -> str:
        """Resolve field aliases to actual column names."""
        return FIELD_ALIASES.get(self.field, self.field)

    def to_sql(self) -> tuple[str, list]:
        """Convert to SQL WHERE clause fragment and parameters."""
        col = self.resolve_field()
        if col not in REFS_SELECT_FIELDS:
            raise ValueError(f"Unknown field: {self.field} (resolved: {col})")

        match self.operator:
            case Operator.CONTAINS:
                return f"{col} LIKE ?", [f"%{self.value}%"]
            case Operator.IS:
                return f"{col} = ?", [self.value]
            case Operator.LT:
                return f"{col} < ?", [self.value]
            case Operator.LTE:
                return f"{col} <= ?", [self.value]
            case Operator.GT:
                return f"{col} > ?", [self.value]
            case Operator.GTE:
                return f"{col} >= ?", [self.value]
            case Operator.BEGINS_WITH:
                return f"{col} LIKE ?", [f"{self.value}%"]
            case Operator.ENDS_WITH:
                return f"{col} LIKE ?", [f"%{self.value}"]
            case Operator.WORD_BEGINS:
                # Match word boundary: start of field or after space
                return f"({col} LIKE ? OR {col} LIKE ?)", [
                    f"{self.value}%",
                    f"% {self.value}%",
                ]


@dataclass
class SearchQuery:
    """A compound search query with boolean logic."""

    conditions: list[tuple[Optional[BooleanOp], Condition]]

    def to_sql(self) -> tuple[str, list]:
        """Build the full WHERE clause."""
        if not self.conditions:
            return "1=1", []

        parts = []
        params = []

        for i, (bool_op, cond) in enumerate(self.conditions):
            frag, p = cond.to_sql()

            if i == 0:
                parts.append(frag)
            elif bool_op == BooleanOp.AND:
                parts.append(f"AND ({frag})")
            elif bool_op == BooleanOp.OR:
                parts.append(f"OR ({frag})")
            elif bool_op == BooleanOp.NOT:
                parts.append(f"AND NOT ({frag})")
            else:
                parts.append(f"AND ({frag})")

            params.extend(p)

        return " ".join(parts), params


def search(
    lib: EndnoteLibrary,
    query: SearchQuery,
    include_trashed: bool = False,
    limit: Optional[int] = None,
    offset: int = 0,
    group_name: Optional[str] = None,
) -> list[Reference]:
    """Execute a search query against the library."""
    where_clause, params = query.to_sql()

    # Base filter
    base = "trash_state = 0" if not include_trashed else "1=1"

    # Group filter
    if group_name:
        group = lib.get_group_by_name(group_name)
        if group and group.member_ids:
            placeholders = ",".join("?" * len(group.member_ids))
            base += f" AND id IN ({placeholders})"
            params = list(group.member_ids) + params
        else:
            return []  # Group not found or empty

    fields = ", ".join(REFS_SELECT_FIELDS)
    sql = f"SELECT {fields} FROM refs WHERE {base} AND ({where_clause})"
    sql += " ORDER BY id"
    if limit is not None:
        sql += f" LIMIT {limit} OFFSET {offset}"

    rows = lib.conn.execute(sql, params).fetchall()
    return [lib._row_to_ref(r) for r in rows]


def quick_search(
    lib: EndnoteLibrary,
    query_text: str,
    include_trashed: bool = False,
    limit: Optional[int] = None,
    group_name: Optional[str] = None,
) -> list[Reference]:
    """Simple keyword search across title, author, abstract, keywords."""
    conditions = []
    for field in ("title", "author", "abstract", "keywords"):
        bool_op = None if not conditions else BooleanOp.OR
        conditions.append((bool_op, Condition(field, Operator.CONTAINS, query_text)))

    sq = SearchQuery(conditions=conditions)
    return search(lib, sq, include_trashed=include_trashed, limit=limit, group_name=group_name)
