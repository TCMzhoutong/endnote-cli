# endnote-cli

[English](README.md) | **中文**

通过直接读取 SQLite 数据库，为 EndNote `.enl` 文献库提供命令行工具和 MCP 服务器。

## 核心功能

- **检索** -- 列出、查看、统计题录，支持 Rich 表格输出
- **搜索** -- 快速全文搜索 + 高级多字段布尔搜索（Contains / Is / 大于 / 小于 / 开头 / 结尾 / 词首匹配，AND / OR / NOT 组合）
- **写入** -- 安全更新笔记、关键词、标签、评分、自定义字段、附件（自动双写 `.enl` + `sdb.eni`）
- **导出** -- BibTeX、RIS、JSON、CSV、按分组层级导出 XML、PDF 复制、格式化引用（APA7 / Harvard / Vancouver / IEEE）
- **分组与标签** -- 浏览 Group Set → Group 层级结构、颜色标签管理
- **MCP 服务器** -- 20+ 工具暴露给 Claude Code / Claude Desktop，通过 Model Context Protocol 调用
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

# 含 MCP 服务器支持
pip install 'endnote-cli[mcp]'

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
| `item` | `list`, `get`, `count` | 列出题录、查看详情、统计数量 |
| `group` | `list`, `tree`, `show` | 浏览分组、显示层级树、查看分组内容 |
| `tag` | `list`, `show` | 查看颜色标签及标记的论文 |
| `search` | `quick`, `advanced` | 快速搜索、高级多字段布尔搜索 |
| `export` | `bibtex`, `ris`, `json`, `csv`, `xml`, `pdf`, `citation` | 多格式导出 |
| `write` | `note`, `keyword`, `status`, `rating`, `label`, `tag`, `field`, `attach`, `clear`, `rename-pdf` | 安全写入字段、管理附件、批量重命名 PDF |
| `library` | `list`, `info`, `set-default`, `set-dir` | 多库管理 |
| `mcp` | *(无)* | 启动 MCP 服务器 |

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

# 按分组导出 BibTeX
endnote-cli export bibtex --group "RAG" -o rag_papers.bib

# 批量重命名 PDF 为 作者_年份_标题.pdf 格式（先预览再执行）
endnote-cli write rename-pdf --all --dry-run
endnote-cli write rename-pdf --all

# 给论文打颜色标签
endnote-cli write tag 296 6

# 将精读笔记写回 EndNote 的 Research Notes 字段
endnote-cli write note 296 my_review.md

# 按分组集合导出为层级 XML 文件
endnote-cli export xml --group-set "医案类研究"
```

## MCP 服务器配置

在 `.mcp.json`（Claude Code）或 `claude_desktop_config.json` 中添加：

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

配置后，Claude 可直接通过 MCP 调用 endnote-cli 的全部功能：搜索论文、获取元数据、导出 BibTeX、打标签等。

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
| 分组集合（父级） | `misc` 表 `code=17`，`value` 列为 XML BLOB |
| 分组归属映射 | `misc` 表 `code=4`，空格分隔的 `group_id set_id` 配对 |
| 颜色标签定义 | `tag_groups` 表，XML BLOB（含颜色十六进制值） |
| 颜色标签关联 | `tag_members`，FTS5 虚拟表，空格分隔的 tag ID |
| 附件文件映射 | `file_res` 表，`{hash_dir}/{filename}` 格式 |
| 多值字段分隔符 | `\r`（回车符 CR），非 `\n` 或分号 |

### 可安全写入的字段

以下字段可以安全 UPDATE，不会触发 `EN_MAKE_SORT_KEY` 内部函数：

`research_notes`, `notes`, `keywords`, `read_status`, `rating`, `label`, `caption`, `custom_1` ~ `custom_7`

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
