# endnote-cli

[English](README.md) | **中文**

通过直接读取 SQLite 数据库，为 EndNote `.enl` 文献库提供命令行工具。

## 核心功能

- **检索** -- 列出、查看、统计题录，支持 Rich 表格输出
- **搜索** -- 快速全文搜索 + 高级多字段布尔搜索（Contains / Is / 大于 / 小于 / 开头 / 结尾 / 词首匹配，AND / OR / NOT 组合）
- **写入** -- 安全更新笔记、关键词、标签、评分、自定义字段、翻译标题/作者、附件（自动双写 `.enl` + `sdb.eni`）
- **导出** -- BibTeX、RIS、JSON、CSV、按分组层级导出 XML、PDF 复制、格式化引用（APA7 / Harvard / Vancouver / IEEE）
- **分组与标签** -- 浏览 Group Set → Group 层级结构、颜色标签管理
- **期刊分区自动打标签** -- 一条命令按 CAS + 新锐分区自动打颜色 tag，数据来自 [hitfyd/ShowJCR](https://github.com/hitfyd/ShowJCR)
- **多库管理** -- 在多个 `.enl` 文件之间切换
- **PDF 批量重命名** -- 按 `作者_年份_标题.pdf` 格式统一命名，含补充材料双重校验

## 环境要求

- **Python** 3.10+
- **EndNote** 20 或更高版本（在 EndNote 21 上完整测试）
- **操作系统**: Windows、macOS、Linux（只要能访问 `.enl` 文件即可）
- 写入操作时必须**关闭 EndNote**

## 安装

```bash
# 基础 CLI
pip install endnote-cli

# 含语义搜索（sentence-transformers）
pip install 'endnote-cli[semantic]'

# 全部安装
pip install 'endnote-cli[all]'
```

## 快速开始

```bash
# 指定 .enl 文件所在目录
endnote-cli library set-dir "C:/Users/你的用户名/Documents/EndNote"

# 设置默认库
endnote-cli library set-default MyLibrary.enl

# 验证连通性，查看库概览
endnote-cli app ping
endnote-cli app info
```

## 命令一览

| 命令 | 子命令 | 说明 |
|---|---|---|
| `app` | `ping`, `info` | 连通性检查、库概览统计 |
| `item` | `list`, `get`, `count`, `groups` | 列出题录、查看详情、统计数量、查看题录的分组归属 |
| `group` | `list`, `tree`, `show` | 浏览分组、显示层级树、查看分组内容 |
| `tag` | `list`, `show` | 查看颜色标签及标记的论文 |
| `search` | `quick`, `advanced` | 快速搜索、高级多字段布尔搜索 |
| `export` | `bibtex`, `ris`, `json`, `csv`, `xml`, `pdf`, `citation` | 多格式导出 |
| `write` | `note`, `keyword`, `status`, `rating`, `label`, `tag`, `journal-tags`, `field`, `attach`, `clear`, `rename-pdf` | 安全写入字段、管理附件、批量重命名 PDF、按期刊分区自动打标签 |
| `library` | `list`, `info`, `set-default`, `set-dir` | 多库管理 |

使用 `endnote-cli <命令> --help` 查看详细用法。

### 使用示例

```bash
# 搜索 "knowledge graph" 相关论文
endnote-cli search quick "knowledge graph"

# 高级搜索：标题含 "RAG" 且年份 >= 2025
endnote-cli search advanced \
  -f title -o contains -v "RAG" \
  -f year -o gte -v "2025" --bool and

# 显示分组层级树
endnote-cli group tree

# 查看某篇论文属于哪些分组（路径格式 GroupSet/Group；孤儿 group 用 bare 名）
endnote-cli item groups 6
endnote-cli item groups 6 --json   # 机器可读输出

# 按分组导出 BibTeX
endnote-cli export bibtex --group "RAG" -o rag_papers.bib

# 批量重命名 PDF 为 作者_年份_标题.pdf 格式（先预览再执行）
endnote-cli write rename-pdf --all --dry-run
endnote-cli write rename-pdf --all

# 给论文打颜色标签
endnote-cli write tag 296 6

# 按期刊分区自动给所有论文打标签（新锐N区 / N区25年 / 预印本）
endnote-cli write journal-tags --dry-run   # 先预览
endnote-cli write journal-tags             # 实际写入

# 填充 Translated Title 字段（学术中文标题）
endnote-cli write field 179 translated_title "肠道菌群与肺部疾病的文献计量分析"

# 将精读笔记写回 EndNote 的 Research Notes 字段
endnote-cli write note 296 my_review.md

# 按分组集合导出为层级 XML 文件
endnote-cli export xml --group-set "医案类研究"
```

## 按期刊分区自动打标签

`endnote-cli write journal-tags` 为库中每条论文按期刊所在分区打上带颜色的 tag：

| 标签 | 数据源 | 颜色 |
|---|---|---|
| `新锐N区` | 新锐期刊分区表 2026 (XR2026) | 红/橙/绿/灰 对应 N=1/2/3/4 |
| `N区25年` | 中科院分区表升级版 2025 (FQBJCR2025) | 同上配色 |
| `预印本` | 期刊名含 `arxiv` | 灰 |

匹配顺序：先用 ISSN（EndNote 的 `isbn` 字段），命中不了再用归一化的期刊名匹配。中文期刊和会议论文集会被跳过 —— CAS/新锐分区只覆盖 SCI 范围。

```bash
# 预览，不写入
endnote-cli write journal-tags --dry-run

# 实际写入
endnote-cli write journal-tags

# 只处理某个分组内的论文
endnote-cli write journal-tags --group "RAG"

# 重新下载最新的分区数据并清掉旧 tag 重新打
endnote-cli write journal-tags --refresh-data --refresh
```

分区数据首次使用时从 [hitfyd/ShowJCR](https://github.com/hitfyd/ShowJCR) 拉取，缓存在 `~/.endnote-cli/jcr_cache/`。

## 作为 Claude Code Skill 安装

本仓库在 `.claude/skills/endnote-cli/SKILL.md` 中提供了一份 [Claude Code skill](https://docs.claude.com/en/docs/claude-code/skills)。注册后，当你在 Claude Code 中提到 EndNote、`.enl`、导出 BibTeX 等关键词时会自动加载。

**注册 skill**（推荐软链接，随仓库更新自动同步）：

```bash
# Linux / macOS
ln -s "$(pwd)/.claude/skills/endnote-cli" ~/.claude/skills/endnote-cli

# Windows（以管理员身份打开 PowerShell）
New-Item -ItemType SymbolicLink `
  -Path  "$HOME\.claude\skills\endnote-cli" `
  -Target "$(Get-Location)\.claude\skills\endnote-cli"
```

不想用软链接也可以直接复制目录：

```bash
cp -r .claude/skills/endnote-cli ~/.claude/skills/
```

在 Claude Code 里执行 `/help` 验证 —— skills 列表中应出现 `endnote-cli`。

## 技术架构

### 双数据库发现

EndNote 的 `.enl` 文件实质上是 **SQLite 3.x 数据库**（Clarivate 未公开文档）。但 EndNote 维护了**两份**数据库：

1. **`MyLibrary.enl`** -- 用户看到的文件
2. **`MyLibrary.Data/sdb/sdb.eni`** -- 内部镜像，表结构完全相同

运行时 EndNote 从 `sdb.eni` 读取数据。**所有写入操作必须同时更新两个数据库**才能生效。`endnote-cli` 自动处理双写。

### 数据库结构要点

| 数据 | 存储方式 |
|---|---|
| 题录元数据 | `refs` 表，60+ 字段 |
| 分组 | `groups` 表，`spec` 列为 XML BLOB（含名称、UUID、时间戳） |
| 分组集合（父级） | `misc` 表 `code=17`，每行一个 GroupSet 的 XML BLOB（含名称、UUID、`<member>` 子 group UUID 列表） |
| 分组归属映射 | 真相藏在 `code=17` 各 GroupSet XML 的 `<member>` UUID 列表里。⚠️ `misc code=4` 只有残缺子集（疑似旧版本遗留），不可作为层级来源 |
| 颜色标签定义 | `tag_groups` 表，XML BLOB（含颜色十六进制值） |
| 颜色标签关联 | `tag_members`，FTS5 虚拟表，空格分隔的 tag ID |
| 附件文件映射 | `file_res` 表，`{hash_dir}/{filename}` 格式 |
| 多值字段分隔符 | `\r`（回车符 CR），非 `\n` 或分号 |

### 可安全写入的字段

以下字段可以安全 UPDATE，不会触发 `EN_MAKE_SORT_KEY` 内部函数：

`research_notes`, `notes`, `keywords`, `read_status`, `rating`, `label`, `caption`, `custom_1` ~ `custom_7`, `translated_title`, `translated_author`

## 限制

- **不能 INSERT 新题录** -- `refs` 表的触发器调用了 `EN_MAKE_SORT_KEY`（仅 EndNote 内部可用的 SQLite 自定义函数）。仅支持 UPDATE 安全字段。
- **写入时必须关闭 EndNote** -- 应用运行时会锁定数据库文件，且内存状态可能覆盖外部修改。
- **标签颜色仅支持 7 种预设** -- 红、橙、黄、绿、蓝、紫、灰。自定义十六进制值在 EndNote 界面中显示为灰色。

## 测试环境

| EndNote 版本 | 操作系统 | 状态 |
|---|---|---|
| EndNote 21 | Windows 11 | 完整测试通过 |
| EndNote 20 | Windows 10/11 | 应当兼容（相同 `.enl` 格式） |

其他使用 `.enl` SQLite 格式的版本也可能兼容。欢迎提交测试报告。

## 参与贡献

欢迎提交 Issue 和 Pull Request。

如果你发现了更多 `.enl` 数据库的结构细节（新的表、字段含义等），请分享——本项目基于逆向工程构建，社区贡献能让它更好地服务所有人。

## 许可证

[Apache License 2.0](LICENSE)
