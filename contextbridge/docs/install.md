# Installation

## 1. 装本体

需要 Python 3.10+。

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows PowerShell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# 然后
git clone <repo> && cd contextbridge
uv venv && uv pip install -e ".[dev]"
```

或纯 pip：

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -e ".[dev]"
```

确认：`cb --help` 能列 5 个命令（export / list / show / import / clear）。

## 2. 注册 MCP server

各 host 的配置文件位置：

| Host | 配置文件 |
|------|---------|
| Claude Code (CLI) | `~/.claude.json` 中的 `mcpServers` 字段，或项目根 `.mcp.json` |
| Claude Desktop (macOS) | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Claude Desktop (Windows) | `%APPDATA%\Claude\claude_desktop_config.json` |
| Cursor | Settings → MCP → Add Server（JSON 输入） |

通用 JSON 片段：

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

> **Windows 用户**：`cb` 可能要换成完整 exe 路径，例如
> `C:\\Users\\YOU\\path\\to\\contextbridge\\.venv\\Scripts\\cb.exe`。
> 用 `where cb`（cmd）或 `Get-Command cb`（PowerShell）拿到实际路径。
>
> **WSL 用户**：注意 host 看到的家目录路径与 Linux 端的 `~` 可能不同。
> 把 `cb` 写成绝对路径 `/home/<user>/.venv/contextbridge/bin/cb`，并确保 host 进程有权限访问。

## 2.1 Streamable HTTP 模式（远程 / 网络测试）

默认的 `cb serve` 走 stdio（本地 IDE 子进程），适合绝大多数场景。若需要远程访问或网络测试，可用 Streamable HTTP：

```bash
cb serve --http                 # 默认 127.0.0.1:8000
cb serve --http -H 0.0.0.0 -p 9000   # 监听所有网卡、指定端口
```

HTTP 模式启用**无状态核心**（`stateless_http=True`，符合 MCP 2026-07-28 规范）：每个请求独立处理，不依赖 session——这与 ContextBridge 的文件+sqlite 无状态存储天然契合。

对应的 host 配置（以 `url` 代替 `command`）：

```json
{
  "mcpServers": {
    "contextbridge": {
      "url": "http://127.0.0.1:8000/mcp"
    }
  }
}
```

> **安全提示**：`-H 0.0.0.0` 会暴露到局域网。生产环境请放在反向代理（Nginx/Caddy）后面并加鉴权；ContextBridge 本身不做 HTTP 层鉴权。

## 3. 故障排查

- **工具没在 Claude/Cursor 里出现**：检查 JSON 是用绝对路径；保存后**完全退出** host（系统托盘 Exit）再启动；查日志
  - Claude Desktop：`~/Library/Logs/Claude/mcp-server-contextbridge.log`
  - Cursor：`~/Library/Application Support/Cursor/logs/`
- **`cb export` 在 Claude Code 路径下没自动取到对话**：确认 `~/.claude/projects/` 下有 `.jsonl` 文件（如果还没用过 Claude Code，不会生成）；用 `--conversation '[...]'` 显式喂
- **sqlite 报 locked / 损坏**：删 `~/.contextbridge/index.db`，下次启动会自动重建
- **跨工具时 `cb import` 看到的 cwd 不对**：v0 不自动切换目录，需要自己 `cd` 到对应项目
