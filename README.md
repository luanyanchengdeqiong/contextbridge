# ContextBridge

**跨 IDE 的"上下文接力"工具。** 在 Cursor / Claude Code / Codex / Gemini CLI 等 AI IDE 之间，
把当前会话 + 任务状态打包成快照，切换工具时一键 import，让接手的 AI 立刻懂"前因后果"。

适合 vibe coding 时反复切工具的人——不再每次"我刚改了哪几个文件"、"我刚才让你在做什么"重头讲一遍。

---

## 为什么

调研报告显示：Cursor→Claude Code、Claude Code→Web、Codex↔Gemini CLI 之间
**会话/选区/git diff 无法迁移**是 vibe coding 高频痛点，且当前**零成熟竞品**。

ContextBridge 的做法是 **Handoff 快照式**（非常驻 bridge）：

- 单 CLI + MCP server，零常驻进程、零外部依赖
- 全本地存储（sqlite + JSON 文件），隐私可控
- 任意 MCP host 都能用（Claude Code / Cursor / Claude Desktop）

代价：不是实时双向同步。但对 vibe coding 场景，"我决定切工具了，导出一次 →
在另一边 import 接着干"正是 99% 真实需求。

---

## 装机

需要 Python 3.10+。

```bash
# 装 uv（推荐）
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
# Windows PowerShell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# 然后
git clone <repo> && cd contextbridge
uv venv && uv pip install -e ".[dev]"
```

或者纯 pip:

```bash
python -m venv .venv
.venv\Scripts\activate       # Windows
# source .venv/bin/activate  # macOS/Linux
pip install -e ".[dev]"
```

验证：`cb --help` 应列出 5 个子命令。

详见 [docs/install.md](docs/install.md)。

---

## 接入 MCP

### Claude Code

编辑 `~/.claude.json`（或项目根的 `.mcp.json`），加入：

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

WSL 用户：把 `cb` 改成完整路径，例如 `/home/<user>/.venv/contextbridge/bin/cb`。

### Cursor

Settings → MCP → Add Server，填同样 JSON。

### Claude Desktop

编辑 `claude_desktop_config.json`：

- macOS：`~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows：`%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "contextbridge": {
      "command": "C:\\absolute\\path\\to\\cb.exe",
      "args": ["serve"]
    }
  }
}
```

---

## 作为 CLI

不依赖 MCP host，也可以纯命令行用：

```bash
# 打包当前 Claude Code session（自动读 ~/.claude/projects/）
cb export -t "feature X"

# 或者从 GUI host（Cursor 等）显式喂对话内容
cb export -t "x" -c '[{"role":"user","content":"需要把登录改成 OAuth"}]'

# 看所有快照
cb list

# 打印某个快照详情（json）
cb show <id>

# 打印结构化 handoff 块（粘贴到下一个 IDE 里）
cb import            # 默认最新
cb import <id>

# 清理 30 天以上的
cb clear 30
```

---

## 让 AI 在 MCP 里使用

接入后，新会话里跟 AI 说：

- "export 当前对话" → AI 调 `cb_export`
- "看一下之前 export 过哪些" → AI 调 `cb_list`
- "把上一个对话加载进来接着干" → AI 调 `cb_import`

---

## 数据放在哪

```
~/.contextbridge/
├── index.db               # sqlite + FTS5 索引
├── snapshots/             # JSON 快照文件，可直接看/分享
│   └── 2026-07-27T12-00-00Z_feature-x_<id8>.json
```

可用 `CONTEXTBRIDGE_HOME` env 覆盖目录。

---

## 设计 / 路线图

见 [docs/architecture.md](docs/architecture.md) 与
[../docs/specs/2026-07-27-contextbridge-design.md](../docs/specs/2026-07-27-contextbridge-design.md)。

**v1 已完成**：Claude Code 自动采集、Cursor/通用 host 显式喂入、sqlite+FTS5、4 工具 + CLI。

**后续**：Codex/Gemini CLI adapter、选中文本采集、团队共享库、Web UI。
