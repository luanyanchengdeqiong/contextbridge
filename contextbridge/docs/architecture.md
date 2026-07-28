# Architecture

ContextBridge 是 **Handoff 快照式** MCP server，专解 vibe coding 时跨 AI IDE 切换工具
带来的"上下文丢失"问题。不做实时同步、不做云备份——就是"打包我现在的活 → 在另一个 IDE
里 paste/load 接着干"。

## 模块

```
contextbridge/
└── src/contextbridge/
    ├── __main__.py    # 入口：serve → MCP server；其它 → Typer CLI
    ├── cli.py         # Typer CLI 5 命令 + _build_snapshot 共享逻辑
    ├── server.py      # FastMCP server，4 个 cb_* 工具，复用 _build_snapshot / _impl 纯函数
    ├── store.py       # sqlite + FTS5 索引，JSON 快照落盘
    ├── schema.py      # pydantic: Snapshot / ConversationMessage / SourceInfo
    ├── truncation.py  # 对话按轮数 / 字符数裁剪；diff 截断
    ├── gitutils.py    # 子进程收 git diff (HEAD + cached)
    ├── config.py      # 路径：CONTEXTBRIDGE_HOME 覆盖、HOME/USERPROFILE 兼容 WSL+Win
    └── adapters/
        ├── base.py        # SourceAdapter Protocol
        ├── generic.py     # GenericAdapter：从工具入参 conversation 喂入（Cursor / GUI 兜底）
        └── claude_code.py # ClaudeCodeAdapter：读 ~/.claude/projects/<hash>/<sid>.jsonl 最新一个
```

每个文件职责单一，能独立测试。

## 数据流

```
cb_export / `cb export`
  └─► _build_snapshot
        ├─► ClaudeCodeAdapter.detect/parse_session（或 Generic 路径）
        ├─► truncate_conversation（30 轮 + 80k 字符上限）
        ├─► get_git_diff（可选）
        └─► Store.save（写 JSON + sqlite + FTS5 rowid）

cb_list / `cb list`  ─► Store.list（sqlite ORDER BY created_at）
cb_import / `cb import [id]`
  └─► Store.get / Store.latest
        └─► 拼成 markdown 块返回给接手的 AI
cb_clear / `cb clear N`  ─► Store.delete_older_than（删 json + sql + fts）
```

## Adapter 模型

```
SourceAdapter (Protocol): name / detect / get_session_path / parse_session / get_open_files
   ├─ ClaudeCodeAdapter (auto-detect ~/.claude/projects/)
   ├─ GenericAdapter    (conversation 入参，AI 喂入)
   ├─ CodexAdapter      (TODO v2)
   └─ GeminiAdapter     (TODO v2)
```

新增 IDE 支持仅加一个 adapter，零侵入现有逻辑。

## 入口分发

```
[project.scripts] cb = contextbridge.__main__:main
$ cb serve      → main() 检测 argv[1]=='serve' → server.mcp.run(transport='stdio')
$ cb <其它>     → main() 把 argv 让给 Typer app
```

详见 design doc：[../../docs/specs/2026-07-27-contextbridge-design.md](../../docs/specs/2026-07-27-contextbridge-design.md)。
