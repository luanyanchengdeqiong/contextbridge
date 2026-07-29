# ContextBridge

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/tests-38%20passed-brightgreen)](#测试)
[![License](https://img.shields.io/badge/license-MIT-green)](#license)

> 在多个 AI 编程 IDE 之间传递会话上下文的轻量 MCP 工具。
> 把当前对话 + git diff 打包成快照,切换工具时一键 import,接手的 AI 立刻懂"前因后果"。

ContextBridge 解决一个非常具体的问题:你在 Cursor / Claude Code / Codex / Gemini CLI 之间切来切去时,每次都要跟新工具重新解释"我刚改了什么、现在在做什么"。它把当前会话导出成一份可移植的快照,在另一边 import 进来,接着干。

- **双入口**:既能作为 MCP server 被 AI IDE 直接调用,也能作为命令行工具独立使用
- **全本地**:sqlite + JSON 文件存储,不联网,不上传,隐私完全可控
- **零常驻**:CLI 用完即走,MCP server 仅在 host 进程内运行,没有后台服务
- **自动采集**:在 Claude Code 下自动读取 `~/.claude/projects/` 会话,无需手动粘贴

---

## 目录

- [安装](#安装)
- [快速开始](#快速开始)
- [接入 MCP host](#接入-mcp-host)
- [CLI 用法](#cli-用法)
- [MCP 工具](#mcp-工具)
- [数据存储](#数据存储)
- [项目结构](#项目结构)
- [测试](#测试)
- [设计文档](#设计文档)
- [License](#license)

---

## 安装

需要 Python 3.10+。

```bash
git clone https://github.com/luanyanchengdeqiong/contextbridge.git
cd contextbridge

# 推荐:用 uv
uv venv && uv pip install -e ".[dev]"

# 或者纯 pip
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

验证安装:

```bash
cb --help          # 应列出 export / list / show / import / clear
```

---

## 快速开始

**场景**:你在 Claude Code 里干了一阵,想切到 Cursor 接着做。

```bash
# 1. 在 Claude Code 侧,导出当前会话(自动读取本地 session)
cb export -t "把登录改成 OAuth"

# 2. 切到 Cursor 后,打印 handoff 块粘贴进新对话
cb import          # 默认取最新一条
```

粘贴进去的内容长这样(节选):

```markdown
# Context Handoff — 把登录改成 OAuth
source IDE: claude_code  cwd: /path/to/repo  created: 2026-07-29T...

## user
需要把登录改成 OAuth...

## assistant
我已经把 session.py 改好了,接下来要...

## Current git diff
```diff
diff --git a/src/session.py b/src/session.py
...
```
```

接手的 AI 一眼看到完整上下文 + 当前代码改动。

---

## 接入 MCP host

接入后,AI 能在自己会话里直接调用 `cb_export` / `cb_import`,无需切到终端。

### Claude Code

编辑 `~/.claude.json`(或项目根 `.mcp.json`):

```json
{
  "mcpServers": {
    "contextbridge": {
      "command": "cb",
      "args": ["serve"]
    }
  }
}
```

### Cursor / Claude Desktop / 其他 MCP host

Settings → MCP → Add Server,填入同样 JSON。Windows 上若 `cb` 不在 PATH,改用绝对路径:

```json
{
  "mcpServers": {
    "contextbridge": {
      "command": "C:\\path\\to\\contextbridge\\.venv\\Scripts\\cb.exe",
      "args": ["serve"]
    }
  }
}
```

> **Windows 注意**:`cb serve` 启动的 git 子进程已做 handle 隔离处理,不会因继承 stdio 管道而挂起。

---

## CLI 用法

```bash
cb export [-t TITLE] [-c CONVERSATION_JSON] [--no-diff]   # 导出快照
cb list   [-n LIMIT]                                       # 列出快照
cb show   <ID>                                             # 打印某条快照 JSON
cb import [<ID>]                                           # 打印 handoff 块(默认最新)
cb clear  [DAYS]                                           # 清理 N 天前的(默认 30)
```

**显式传入对话**(非 Claude Code 环境,如从 GUI host 拷贝):

```bash
cb export -t "修复登录 bug" -c '[{"role":"user","content":"登录总报 500"}]'
```

**ID 支持前缀**:`cb_list` 显示的是 8 位短 id,`import` / `show` 既接受完整 UUID 也接受短前缀。

---

## MCP 工具

| 工具 | 作用 |
|---|---|
| `cb_export` | 导出当前上下文为快照;在 Claude Code 下自动采集,其他 host 可传 `conversation` 参数 |
| `cb_list` | 列出快照(显示短 id、IDE、时间、标题) |
| `cb_import` | 按 id/前缀导入,返回 Markdown handoff 块;省略 id 取最新 |
| `cb_clear` | 按天数清理旧快照 |

---

## 数据存储

```
~/.contextbridge/
├── index.db               # sqlite 索引 + FTS5 全文检索(按标题)
└── snapshots/             # JSON 快照文件,可直接查看/分享/删除
    └── 2026-07-29T080000Z_feature-x_<id8>.json
```

- 用 `CONTEXTBRIDGE_HOME` 环境变量覆盖存储目录
- 快照单文件上限 1MB(超长对话会被截断)
- 存储采用进程级单例连接,长生命周期下不会泄漏 sqlite 连接

---

## 项目结构

```
contextbridge/
├── src/contextbridge/
│   ├── server.py            # FastMCP server + 4 个 cb_* 工具
│   ├── cli.py               # Typer CLI
│   ├── store.py             # sqlite 存储 + FTS5 + 前缀查找
│   ├── render.py            # 共享的 handoff 渲染(CLI/MCP 复用)
│   ├── gitutils.py          # Windows 安全的 git diff
│   ├── truncation.py        # 对话/diff 截断
│   ├── schema.py            # pydantic 模型
│   └── adapters/            # IDE 适配器(Claude Code / Generic)
├── tests/                   # 38 条测试
├── docs/
│   ├── install.md
│   └── architecture.md
└── pyproject.toml
```

---

## 测试

```bash
pytest
```

覆盖:存储 CRUD、前缀查找、孤儿行兜底、FTS 检索、CLI 各命令、MCP server 工具、Claude Code 适配器、渲染格式。

---

## 设计文档

- [docs/install.md](docs/install.md) — 详细安装说明
- [docs/architecture.md](docs/architecture.md) — 架构与设计决策

---

## License

MIT
