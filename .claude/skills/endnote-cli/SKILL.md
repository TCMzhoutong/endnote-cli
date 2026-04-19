---
name: endnote-cli
description: Interact with EndNote `.enl` libraries using the endnote-cli tool to read, search, export, and safely update references, groups, color tags, and attachments via direct SQLite access. Also handles batch-filling the `translated_title` field with user-specified translations, and auto-tagging references with their journal's CAS zone. Use when the user asks to work with EndNote libraries, `.enl` files, export BibTeX/RIS/CSV/XML/JSON, search or list references, rename PDFs, manage groups or color tags, write notes/keywords/ratings back, translate paper titles, fill `translated_title` / `Translated Title`, tag by journal zone / 分区, or start the EndNote MCP server. Trigger signals include: "EndNote", ".enl", "文献库", "参考文献管理", "Clarivate", "sdb.eni", "翻译标题", "Translated Title", "translated_title", "分区标签", "期刊分区", "新锐分区", "CAS 分区", "预印本标签".
---

# EndNote CLI

Use the `endnote-cli` command to interact with EndNote `.enl` libraries via direct SQLite access. Works without EndNote running for reads; **EndNote must be closed for writes** (it locks the database files).

## Command reference

Run `endnote-cli --help` or `endnote-cli <command> --help` for up-to-date usage. Full docs: https://github.com/TCMzhoutong/endnote-cli

| Command | Subcommands | Purpose |
|---|---|---|
| `app` | `ping`, `info` | Check connectivity and library summary |
| `item` | `list`, `get`, `count` | List, inspect, and count references |
| `group` | `list`, `tree`, `show` | Browse GroupSet → Group hierarchy |
| `tag` | `list`, `show` | Browse color tags and tagged references |
| `search` | `quick`, `advanced` | Full-text and multi-field boolean search |
| `export` | `bibtex`, `ris`, `json`, `csv`, `xml`, `pdf`, `citation` | Export references |
| `write` | `note`, `keyword`, `status`, `rating`, `label`, `tag`, `field`, `attach`, `clear`, `rename-pdf` | Update safe fields, manage attachments |
| `library` | `list`, `info`, `set-default`, `set-dir` | Manage multiple `.enl` libraries |
| `mcp` | *(none)* | Start MCP server for Claude Code / Desktop |

## First-time setup

Before other commands work, point the CLI at a library directory and pick a default:

```bash
endnote-cli library set-dir "<path/to/your/EndNote/directory>"
endnote-cli library set-default MyLibrary.enl
endnote-cli app ping     # verify
endnote-cli app info     # library stats
```

## Common patterns

```bash
# Search
endnote-cli search quick "knowledge graph"
endnote-cli search advanced -f title -o contains -v "RAG" -f year -o gte -v "2025" --bool and

# Browse
endnote-cli group tree
endnote-cli tag list
endnote-cli item list --limit 20

# Export
endnote-cli export bibtex --group "RAG" -o rag_papers.bib
endnote-cli export xml --group-set "Medical Cases"
endnote-cli export citation 296 --style apa

# Write (EndNote must be CLOSED)
endnote-cli write note 296 my_review.md
endnote-cli write keyword 296 "RAG,LLM,survey"
endnote-cli write tag 296 6                  # color tag ID
endnote-cli write rename-pdf --all --dry-run # always dry-run first
endnote-cli write rename-pdf --all
```

## Safety rules

- **Always dry-run destructive writes first** (`--dry-run` on `rename-pdf`, bulk `write` ops).
- **Close EndNote before any `write` subcommand** — the app locks `.enl` and `sdb.eni`; writes while open corrupt state or silently fail.
- **Never `INSERT` into `refs`** — the table uses triggers calling `EN_MAKE_SORT_KEY`, a custom SQLite function only present inside the EndNote runtime. Only `UPDATE` of safe fields is supported; the CLI enforces this.
- **Safe write fields**: `research_notes`, `notes`, `keywords`, `read_status`, `rating`, `label`, `caption`, `custom_1`..`custom_7`, `translated_title`, `translated_author`. Other fields are not exposed by `write`.
- **Dual-database sync**: writes update both `MyLibrary.enl` and `MyLibrary.Data/sdb/sdb.eni`. The CLI handles this — do not hand-edit one side.
- **Tag colors**: only 7 presets render correctly (red, orange, yellow, green, blue, purple, gray). Custom hex renders as gray in the UI.

## Auto-tag by journal zone → `write journal-tags`

`endnote-cli write journal-tags` assigns color tags based on each ref's
journal zone. Tags applied per ref:

- `新锐N区` from XR2026 (New-Elite 2026) — red/orange/green/gray for N=1/2/3/4
- `N区25年` from FQBJCR2025 (CAS upgraded 2025) — same colors
- `预印本` (gray) if `secondary_title` contains "arxiv"

Tags are created on first use (color baked in). Existing tags with matching
names are reused, so subsequent runs are idempotent. `--group <name>` scopes
to a group. `--dry-run` previews. `--refresh` strips and recomputes all
zone/preprint tags (use when source data is refreshed via `--refresh-data`).
Chinese-only journals and conference proceedings won't match (data covers
SCI-scope only); that's expected.

Data source: github.com/hitfyd/ShowJCR, cached under `~/.endnote-cli/jcr_cache/`.

## Translate titles → `translated_title`

For refs whose `title` is in one language and `translated_title` is empty,
translate the title and write it via `EndnoteWriter.write_field(id,
"translated_title", value)`.

- Ask the user for target language and domain up front if not obvious.
- Detect "foreign" titles by character-set heuristic on `title`; the
  `language` column is unreliable (often blank).
- Dry-run a preview list before writing. At write time, re-check the row's
  `translated_title` is still empty.
- After the real run, confirm both `.enl` and `sdb.eni` counts match and
  have the user spot-check in EndNote.

## Multi-library

```bash
endnote-cli library list
endnote-cli library set-default OtherLibrary.enl
# or pass --library per-command if the CLI supports it (check --help)
```

## MCP server

To expose EndNote capabilities to Claude Desktop or Claude Code as MCP tools:

```json
{
  "mcpServers": {
    "endnote": { "command": "endnote-cli", "args": ["mcp"] }
  }
}
```
