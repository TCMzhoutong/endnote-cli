# endnote-cli

**English** | [中文](README_CN.md)

CLI and MCP server for reading, searching, writing, and exporting EndNote `.enl` libraries via direct SQLite access.

## Key Features

- **Read** -- list, get, and count references with rich table output
- **Search** -- quick full-text and advanced multi-field boolean search
- **Write** -- safely update notes, keywords, tags, ratings, labels, custom fields, translated title/author, and attachments
- **Export** -- BibTeX, RIS, JSON, CSV, XML, PDF copy-out, and formatted citations
- **Groups & Tags** -- browse group hierarchies and color-tag assignments
- **Journal zone auto-tagging** -- one command assigns CAS + New-Elite zone color tags using data from [hitfyd/ShowJCR](https://github.com/hitfyd/ShowJCR)
- **MCP Server** -- expose all capabilities to Claude Code / Claude Desktop via Model Context Protocol
- **Multi-library** -- manage and switch between multiple `.enl` files

## Requirements

- **Python** 3.10+
- **EndNote** 20 or later (tested on EndNote 21)
- **OS**: Windows, macOS, Linux (wherever EndNote stores `.enl` files)
- EndNote must be **closed** during write operations

## Installation

```bash
# Core CLI
pip install endnote-cli

# With MCP server support
pip install 'endnote-cli[mcp]'

# With semantic search (sentence-transformers)
pip install 'endnote-cli[semantic]'

# Everything
pip install 'endnote-cli[all]'
```

## Quick Start

```bash
# Point to the directory containing your .enl files
endnote-cli library set-dir "C:/Users/You/Documents/EndNote"

# Set the default library
endnote-cli library set-default MyLibrary.enl

# Verify connectivity and see library stats
endnote-cli app ping
endnote-cli app info
```

## Command Reference

| Command | Subcommands | Description |
|---|---|---|
| `app` | `ping`, `info` | Check connectivity and library summary |
| `item` | `list`, `get`, `count` | List, inspect, and count references |
| `group` | `list`, `tree`, `show` | Browse groups and group-set hierarchy |
| `tag` | `list`, `show` | Browse color tags and tagged references |
| `search` | `quick`, `advanced` | Full-text and multi-field boolean search |
| `export` | `bibtex`, `ris`, `json`, `csv`, `xml`, `pdf`, `citation` | Export in various formats |
| `write` | `note`, `keyword`, `status`, `rating`, `label`, `tag`, `journal-tags`, `field`, `attach`, `clear`, `rename-pdf` | Write to safe fields, manage attachments, auto-tag by journal zone |
| `library` | `list`, `info`, `set-default`, `set-dir` | Manage multiple libraries |
| `mcp` | *(none)* | Start MCP server |

Run `endnote-cli <command> --help` for detailed usage of any command.

### Usage Examples

```bash
# Search for papers about "knowledge graph"
endnote-cli search quick "knowledge graph"

# Advanced search: title contains "RAG" AND year >= 2025
endnote-cli search advanced \
  -f title -o contains -v "RAG" \
  -f year -o gte -v "2025" --bool and

# Show group hierarchy (GroupSet -> Groups)
endnote-cli group tree

# Export a group as BibTeX
endnote-cli export bibtex --group "RAG" -o rag_papers.bib

# Batch rename PDFs to Author_Year_Title.pdf format (dry run first)
endnote-cli write rename-pdf --all --dry-run
endnote-cli write rename-pdf --all

# Add a color tag to all arXiv papers
endnote-cli write tag 296 6

# Auto-tag every ref with its CAS zone (新锐N区 / N区25年 / 预印本)
endnote-cli write journal-tags --dry-run   # preview the plan
endnote-cli write journal-tags             # apply

# Fill the Translated Title field
endnote-cli write field 179 translated_title "肠道菌群与肺部疾病的文献计量分析"

# Write review notes back to EndNote
endnote-cli write note 296 my_review.md

# Export a group set as hierarchical XML files
endnote-cli export xml --group-set "Medical Cases"
```

## Journal Zone Auto-Tagging

`endnote-cli write journal-tags` tags every reference with color-coded
zone labels based on its journal. Tags applied per ref:

| Tag | Source | Color |
|---|---|---|
| `新锐N区` | 新锐期刊分区表 2026 (XR2026) | red/orange/green/gray for N=1/2/3/4 |
| `N区25年` | 中科院分区表升级版 2025 (FQBJCR2025) | same color scheme |
| `预印本` | journal name contains `arxiv` | gray |

Matching order: ISSN first (EndNote's `isbn` field), then normalized journal
name. Chinese-only journals and conference proceedings are skipped — they're
outside the CAS scope.

```bash
# Preview — no writes
endnote-cli write journal-tags --dry-run

# Apply
endnote-cli write journal-tags

# Scope to a group
endnote-cli write journal-tags --group "RAG"

# Re-download the source data and re-tag everything
endnote-cli write journal-tags --refresh-data --refresh
```

Ranking data is fetched from [hitfyd/ShowJCR](https://github.com/hitfyd/ShowJCR)
on first use and cached under `~/.endnote-cli/jcr_cache/`.

## MCP Server Setup

Add to your `.mcp.json` (Claude Code) or `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "endnote": {
      "command": "endnote-cli",
      "args": ["mcp"]
    }
  }
}
```

## Install as a Claude Code Skill

In addition to the MCP server, this repo ships a [Claude Code skill](https://docs.claude.com/en/docs/claude-code/skills) at `.claude/skills/endnote-cli/SKILL.md`. Once registered, Claude Code automatically loads it when you mention EndNote, `.enl`, BibTeX export, etc.

**Register the skill** (symlink keeps it in sync with repo updates):

```bash
# Linux / macOS
ln -s "$(pwd)/.claude/skills/endnote-cli" ~/.claude/skills/endnote-cli

# Windows (PowerShell, run as Administrator)
New-Item -ItemType SymbolicLink `
  -Path  "$HOME\.claude\skills\endnote-cli" `
  -Target "$(Get-Location)\.claude\skills\endnote-cli"
```

If you'd rather not symlink, just copy the folder:

```bash
cp -r .claude/skills/endnote-cli ~/.claude/skills/
```

Verify by running `/help` in Claude Code — `endnote-cli` should appear in the skills list.

## Architecture

### The Dual-Database Discovery

EndNote `.enl` files are **SQLite 3.x databases** (undocumented by Clarivate). However, EndNote maintains **two copies** of the database:

1. **`MyLibrary.enl`** -- the file users see
2. **`MyLibrary.Data/sdb/sdb.eni`** -- an internal mirror with the same schema

At runtime, EndNote reads from `sdb.eni`. **All write operations must update both databases** to keep them in sync. `endnote-cli` handles this transparently.

### Key Schema Details

- **Groups/GroupSets** are stored as XML blobs in the `groups` table and `misc` table (`code=17`)
- **Tags** use two tables: `tag_groups` (XML blob with color hex) and `tag_members` (FTS5 virtual table with space-separated IDs)
- **Multi-value fields** (keywords, authors) use `\r` (carriage return) as the separator
- The `refs` table has triggers that call `EN_MAKE_SORT_KEY`, a custom SQLite function only available inside the EndNote application -- this means direct `INSERT` into `refs` is not safe

### Safe Write Fields

The following fields can be safely updated without triggering internal triggers:

`research_notes`, `notes`, `keywords`, `read_status`, `rating`, `label`, `caption`, `custom_1` through `custom_7`, `translated_title`, `translated_author`

## Limitations

- **No INSERT into refs** -- the `refs` table uses triggers with a custom SQLite function (`EN_MAKE_SORT_KEY`) that only exists inside the EndNote runtime. Only `UPDATE` of safe fields is supported.
- **EndNote must be closed** during write operations. The application locks the database files at runtime.
- **Tag colors are limited to 7 presets** -- red, orange, yellow, green, blue, purple, and gray. Custom hex values render as gray in the EndNote UI.

## Tested On

| EndNote Version | OS | Status |
|---|---|---|
| EndNote 21 | Windows 11 | Fully tested |
| EndNote 20 | Windows 10/11 | Should work (same `.enl` format) |

Other versions using `.enl` SQLite format may also work. Contributions and test reports welcome.

## Contributing

Contributions are welcome! Please open an issue or pull request.

If you discover additional `.enl` schema details (new table structures, field meanings, etc.), please share -- this project is built on reverse-engineered knowledge and community contributions make it better for everyone.

## License

[Apache License 2.0](LICENSE)
