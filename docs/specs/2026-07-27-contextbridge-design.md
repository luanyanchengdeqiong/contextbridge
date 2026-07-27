# ContextBridge MCP — 设计文档

- 日期：2026-07-27
- 状态：已确认，待实现
- 主题：跨 IDE 上下文桥接 MCP server

## 1. 一句话定位

一个 **MCP server + CLI**，让你在 Cursor 里干了一半的活，按下快捷键 / 命令就能"打包"
丢给 Claude Code 接着干（或反向），让接手的 AI 立刻懂"前因后果"。

调研出处：独立开发者资源调研报告切入点 #11「跨 IDE 剪贴板桥接 MCP」——
vibe coding 时反复切 Cursor/Claude Code/Codex/Gemini 是常态，但会话、git diff、
当前任务上下文无法迁移，当前零成熟竞品。

## 2. 架构选型

| 维度 | Handoff 快照（已选） | Bridge 常驻 |
|------|------|------|
| 实现 | 单 CLI + 文件存储 | 本地 HTTP/socket |
| 依赖 | 零（uv/pip 即可） | 进程、端口管理 |
| 跨 IDE | 文件 + 命令，任意 IDE 都能用 | 每个客户端都要连服务 |
| MVP 工时 | ~7h | 3 天起 |
| 隐私 | 全本地 | 同 |

**选 Handoff 的理由**：vibe coding 场景下"切工具 → 导出一次 → 接着干"才是 99% 真实需求，
实时同步是伪需求；快照式实现简单、失败可见、零常驻进程依赖。

## 3. 核心工作流

```
IDE A 收尾           中转                     IDE B 接手

Cursor 里说：        ~/.contextbridge/        Claude Code 里说：
"用 contextbridge   snapshots/                "用 contextbridge
 export 把刚才的活   2026-07-27-...json        import 把上一个会话
 打包"                                         加进来接着干"

 export 工具 ──────► 写入文件
                    list 工具 ─► 列所有快照      import 工具 ◄─ 读文件
                    show 工具 ─► 看某个快照详情
                    clear 工具 ► 清理旧快照
```

## 4. MCP 工具表

| 工具 | 入参 | 作用 |
|------|------|------|
| `cb_export(title?, include_diff?, conversation?)` | 标题、是否含 git diff、外部传入对话 | 打包并落盘 |
| `cb_list(limit?)` | 条数 | 列出所有快照（id、标题、source、时间） |
| `cb_import(id?)` | 快照 id，缺省取最新 | 把快照转为结构化文本返回，供 AI 接力 |
| `cb_clear(older_than_days?)` | 保留天数 | 清理过期快照 |

每个工具同时通过 MCP（让 AI 调用）和 CLI（`cb export "feature X"`）暴露，
用户路径不绑死。

## 5. 快照 Schema (v1)

```json
{
  "version": "1.0",
  "id": "uuid-v4",
  "title": "用户起的名字 或 最新用户消息前 60 字",
  "source": { "ide": "cursor|claude_code|codex|gemini_cli|generic", "version": "0.42", "cwd": "/abs/path" },
  "created_at": "ISO-8601",
  "summary": "最新用户消息前 200 字自动生成的摘要",
  "conversation": [
    { "role": "user|assistant", "content": "..." }
  ],
  "git_diff": "include_diff=true 时收集；超过 50KB 截断",
  "open_files": ["..."]
}
```

### 截断策略

防止快照超过 MCP 上下文上限：

- 对话 > 30 轮 → 保留最近 20 轮 + 最早 5 轮
- 总长 > 20k token（约 80KB 文本）→ 按"工具调用结果 → 中段对话 → 最早对话"顺序裁
- git diff > 50KB → 截断并附 `(... truncated, +12KB)` 提示
- 快照总大小硬上限 1MB，超出拒绝写盘

## 6. 各 IDE 适配策略

定义 `SourceAdapter` 协议，每个 host 一个实现，自动 detect。

| IDE/Host | 会话获取 | Adapter | MVP? |
|---------|------|------|------|
| Claude Code | 读 `~/.claude/projects/<hash>/<sid>.jsonl` 最新 session 文件 | ClaudeCodeAdapter | ✅ |
| Cursor / 其他 GUI | 通过 MCP 工具入参 `conversation` 由 AI 喂入 | GenericAdapter | ✅ |
| Codex CLI | 本地 session 文件（路径在实现时确认） | CodexAdapter | post-MVP |
| Gemini CLI | 本地 session 文件 | GeminiAdapter | post-MVP |

新增 host 仅加一个 Adapter，零侵入。

### Adapter 协议

```python
class SourceAdapter(Protocol):
    name: str
    def detect(self, env: dict) -> bool: ...
    def get_session_path(self) -> Path | None: ...
    def parse_session(self, path: Path) -> list[ConversationMessage]: ...
    def get_open_files(self) -> list[str]: ...   # 尽力而为，可返回 []
```

## 7. 文件布局

```
~/.contextbridge/
├── config.toml              # max_keep_days / max_snapshot_size_kb
├── index.db                 # sqlite + FTS5，存 id/title/source/created_at/path
└── snapshots/
    └── 2026-07-27T12-00-00Z_feature-x.json
```

- 用 sqlite + FTS5：`list` 几毫秒返回、支持 title 模糊搜索
- 快照本体仍落 JSON 文件，便于用户直接查看/分享/审计

## 8. 项目结构

```
contextbridge/
├── pyproject.toml              # uv 管理
├── README.md
├── src/contextbridge/
│   ├── __init__.py
│   ├── __main__.py             # python -m contextbridge
│   ├── server.py               # FastMCP server, 4 个 @mcp.tool()
│   ├── cli.py                  # cb export/import/list/clear
│   ├── store.py                # sqlite + json 落盘
│   ├── schema.py               # pydantic: Snapshot, ConversationMessage
│   ├── adapters/
│   │   ├── base.py
│   │   ├── claude_code.py
│   │   ├── cursor.py           # GenericAdapter
│   │   └── __init__.py         # registry
│   ├── truncation.py
│   └── gitutils.py
├── tests/
│   ├── test_store.py
│   ├── test_truncation.py
│   ├── test_adapters.py
│   └── fixtures/sample-sessions/
└── docs/
    ├── install.md              # claude_desktop_config.json / Cursor mcp.json 片段
    └── architecture.md
```

## 9. 错误处理与边界

| 场景 | 处理 |
|------|------|
| 不在 git 仓库 | 跳过 diff，仅给 warning |
| session 文件读取失败 | fallback 到 GenericAdapter，要求 AI 传 conversation |
| 快照 > 1MB | 拒绝写入，提示用户精简 |
| 跨项目 import | 警告但放行，保留 cwd 让 AI 决定 |
| WSL 路径 | ClaudeCodeAdapter 处理 `\\wsl$\` ↔ `/home/` |
| sqlite 损坏 | 启动时重建索引（扫 snapshots/*.json） |

## 10. 测试策略

- **单测**：truncation 阈值、git diff 截断、adapter detect、store CRUD
- **集测**：假 session 文件 → export → list → import 全流程
- **手测清单**：装到作者自己的 Claude Code + Cursor，真跑一次"切工具"

## 11. MVP 范围

| 任务 | 工时 |
|------|------|
| 项目骨架 + pyproject + uv | 15min |
| schema + store(sqlite+json) | 60min |
| Claude Code Adapter | 45min |
| Generic Adapter（Cursor 兜底） | 30min |
| 4 个 MCP 工具 + CLI | 90min |
| truncation + gitutils | 60min |
| 单测 + 文档 | 90min |
| **合计** | **~7 小时** |

v1 不做：选中文本采集、团队共享、Web UI、收费版同步。
