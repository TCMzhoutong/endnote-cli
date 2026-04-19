"""Journal ranking data loader (CAS / New-Elite zones).

Fetches CSV dumps from github.com/hitfyd/ShowJCR on first use and caches them
under ~/.endnote-cli/jcr_cache/. Currently wires up the two tables the
`write journal-tags` command reads:

- XR2026 — 新锐期刊分区表 2026
- FQBJCR2025 — 中科院分区表升级版 2025

Data license: the ShowJCR project is GPL-3.0; the underlying zone data is
scraped from xr-scholar.com / fenqubiao.com and has no explicit redistribution
license. We fetch on demand rather than vendor the files.
"""
from __future__ import annotations

import csv
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

CACHE_DIR = Path.home() / ".endnote-cli" / "jcr_cache"

_REPO_BASE = (
    "https://raw.githubusercontent.com/hitfyd/ShowJCR/master/"
    "中科院分区表及JCR原始数据文件/"
)

DATASETS: dict[str, dict] = {
    "XR2026": {
        "url": _REPO_BASE + "XR2026-UTF8.csv",
        "filename": "XR2026-UTF8.csv",
        "journal_col": "Journal",
        "issn_cols": ["ISSN", "EISSN"],
        "zone_col": "大类新锐分区",
        "zone_pattern": re.compile(r"\s*([1-4])\s*区"),
    },
    "FQBJCR2025": {
        "url": _REPO_BASE + "FQBJCR2025-UTF8.csv",
        "filename": "FQBJCR2025-UTF8.csv",
        "journal_col": "Journal",
        "issn_cols": ["ISSN/EISSN"],  # slash-separated
        "zone_col": "大类分区",
        "zone_pattern": re.compile(r"\s*([1-4])\b"),
    },
}


@dataclass(frozen=True)
class JournalRanking:
    zone: int  # 1..4
    journal: str
    issns: tuple[str, ...]


def _encoded_url(url: str) -> str:
    parts = urllib.parse.urlsplit(url)
    path = urllib.parse.quote(parts.path)
    return urllib.parse.urlunsplit(
        (parts.scheme, parts.netloc, path, parts.query, parts.fragment)
    )


def _fetch_to_cache(url: str, filename: str, force: bool = False) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    out = CACHE_DIR / filename
    if out.exists() and not force:
        return out
    req = urllib.request.Request(_encoded_url(url), headers={"User-Agent": "endnote-cli"})
    with urllib.request.urlopen(req, timeout=60) as resp, out.open("wb") as f:
        f.write(resp.read())
    return out


def _normalize(name: str) -> str:
    s = (name or "").lower().strip()
    s = re.sub(r"[\s\-_.,:;&/()\[\]]+", " ", s)
    return s.strip()


def _extract_issns(row: dict, cols: list[str]) -> list[str]:
    out: list[str] = []
    for col in cols:
        raw = row.get(col, "") or ""
        for part in re.split(r"[/,;\s]+", raw):
            part = part.strip().upper()
            if re.fullmatch(r"\d{4}-\d{3}[\dX]", part):
                out.append(part)
    # dedup while preserving order
    seen: set[str] = set()
    uniq = []
    for p in out:
        if p not in seen:
            seen.add(p)
            uniq.append(p)
    return uniq


@dataclass
class RankingIndex:
    by_issn: dict[str, JournalRanking]
    by_name: dict[str, JournalRanking]

    def lookup(self, journal: str, issn: str) -> Optional[JournalRanking]:
        for p in _extract_issns({"_": issn}, ["_"]):
            hit = self.by_issn.get(p)
            if hit:
                return hit
        if journal:
            hit = self.by_name.get(_normalize(journal))
            if hit:
                return hit
        return None


def load(key: str, force_refresh: bool = False) -> RankingIndex:
    """Load (downloading if needed) a named dataset into an in-memory index."""
    meta = DATASETS[key]
    path = _fetch_to_cache(meta["url"], meta["filename"], force=force_refresh)
    pat: re.Pattern = meta["zone_pattern"]

    by_issn: dict[str, JournalRanking] = {}
    by_name: dict[str, JournalRanking] = {}

    with path.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            journal = (row.get(meta["journal_col"], "") or "").strip()
            zone_cell = row.get(meta["zone_col"], "") or ""
            m = pat.match(zone_cell)
            if not journal or not m:
                continue
            zone = int(m.group(1))
            issns = tuple(_extract_issns(row, meta["issn_cols"]))
            rec = JournalRanking(zone=zone, journal=journal, issns=issns)
            for issn in issns:
                by_issn.setdefault(issn, rec)
            norm = _normalize(journal)
            if norm:
                by_name.setdefault(norm, rec)

    return RankingIndex(by_issn=by_issn, by_name=by_name)
