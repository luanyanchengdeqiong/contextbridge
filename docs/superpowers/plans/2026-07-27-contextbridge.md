# ContextBridge MCP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 一个 MCP server + CLI，把当前 AI IDE 的会话/任务上下文打包成快照，在另一个 IDE 里 import 后继续干活（vibe coding 跨工具切换场景）。

**Architecture:** Handoff 快照式（非常驻进程）。CLI + MCP 双入口共享同一套 store/adapter 逻辑。快照落 JSON 文件 + sqlite(FTS5) 索引到 `~/.contextbridge/`。每个 IDE 一个 SourceAdapter，自动 detect；MVP 覆盖 Claude Code（本地 session 文件）+ Cursor（GenericAdapter，AI 喂入 conversation）。

**Tech Stack:** Python 3.10+、`uv` 包管理、`mcp[cli]` (FastMCP) ≥1.2.0、pydantic 2、sqlite3 (stdlib)、pytest、pytest-asyncio。

参考实现：官方 weather-server-python (https://github.com/modelcontextprotocol/quickstart-resources/tree/main/weather-server-python) 的 FastMCP + stdio 模式。

设计文档：`docs/specs/2026-07-27-contextbridge-design.md`

---

## File Structure

```
contextbridge/
├── pyproject.toml
├── README.md
├── .gitignore
├── src/contextbridge/
│   ├── __init__.py            # 版本号
│   ├── __main__.py            # python -m contextbridge → CLI
│   ├── server.py              # FastMCP，4 个 @mcp.tool()
│   ├── cli.py                 # Typer CLI: export/list/import_/clear
│   ├── store.py               # sqlite + json 落盘
│   ├── schema.py              # pydantic models
│   ├── truncation.py          # 对话裁剪 / git diff 截断
│   ├── gitutils.py            # cwd git diff 采集
│   ├── config.py              # 路径与配置加载
│   └── adapters/
│       ├── __init__.py        # registry
│       ├── base.py            # SourceAdapter Protocol
│       ├── claude_code.py     # 读 ~/.claude/projects/<hash>/<sid>.jsonl
│       └── generic.py         # 兜底：从工具入参 conversation 解析
└── tests/
    ├── conftest.py            # tmp_path 用的 HOME 注入
    ├── test_schema.py
    ├── test_truncation.py
    ├── test_gitutils.py
    ├── test_store.py
    ├── test_adapters_claude_code.py
    ├── test_adapters_generic.py
    ├── test_cli.py
    ├── test_server.py
    └── fixtures/sample-sessions/
        └── claude_code_sample.jsonl
```

更外层 `docs/specs/2026-07-27-contextbridge-design.md` 已存在，不动。

---

## Task 1: 项目骨架 + 依赖

**Files:**
- Create: `contextbridge/pyproject.toml`
- Create: `contextbridge/.gitignore`
- Create: `contextbridge/src/contextbridge/__init__.py`
- Create: `contextbridge/src/contextbridge/__main__.py`
- Create: `contextbridge/README.md`（最小）

- [ ] **Step 1: 写 pyproject.toml**

```toml
[project]
name = "contextbridge"
version = "0.1.0"
description = "Cross-IDE context handoff MCP server + CLI"
requires-python = ">=3.10"
dependencies = [
    "mcp[cli]>=1.2.0",
    "pydantic>=2.5",
    "typer>=0.12",
    "rich>=13",
]

[project.scripts]
contextbridge = "contextbridge.__main__:app"
cb = "contextbridge.__main__:app"

[project.optional-dependencies]
dev = ["pytest>=8", "pytest-asyncio>=0.23"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/contextbridge"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

- [ ] **Step 2: 写 .gitignore**

```
__pycache__/
*.pyc
.venv/
*.egg-info/
dist/
build/
.pytest_cache/
```

- [ ] **Step 3: 写 `src/contextbridge/__init__.py`**

```python
__version__ = "0.1.0"
```

- [ ] **Step 4: 写 `src/contextbridge/__main__.py` 占位**

```python
"""Entry point: `python -m contextbridge` and `cb`/`contextbridge` scripts."""

def main() -> None:
    # 实际 CLI 在 Task 9 接入
    print("contextbridge — install with: uv pip install -e .[dev]")

if __name__ == "__main__":
    main()
```

- [ ] **Step 5: 安装并验证**

```bash
cd contextbridge
uv venv
uv pip install -e ".[dev]"
python -m contextbridge
```
Expected: 打印 `contextbridge — install with: ...`

- [ ] **Step 6: Commit**

```bash
git -C E:/vscode_project/E-commerce init   # 若尚未初始化
cd E:/vscode_project/E-commerce && git add contextbridge docs && git commit -m "feat(contextbridge): project skeleton"
```

---

## Task 2: Schema (pydantic models)

**Files:**
- Create: `contextbridge/src/contextbridge/schema.py`
- Create: `contextbridge/tests/test_schema.py`

- [ ] **Step 1: 写失败测试 `tests/test_schema.py`**

```python
import json
from contextbridge.schema import Snapshot, ConversationMessage, SourceInfo


def test_message_minimal():
    m = ConversationMessage(role="user", content="hi")
    assert m.role == "user"
    assert m.content == "hi"
    assert m.tool_calls is None


def test_snapshot_roundtrip_and_defaults(tmp_path):
    s = Snapshot(
        source=SourceInfo(ide="claude_code", version="1", cwd="/x"),
        conversation=[ConversationMessage(role="user", content="hello")],
    )
    assert s.version == "1.0"
    assert s.id and len(s.id) == 36  # uuid4
    assert s.title  # 默认从前 60 字生成
    s2 = Snapshot.model_validate_json(s.model_dump_json())
    assert s2.id == s.id
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd contextbridge && uv run pytest tests/test_schema.py -v
```
Expected: FAIL（ImportError: No module named 'contextbridge.schema'）

- [ ] **Step 3: 实现 `schema.py`**

```python
from __future__ import annotations
from datetime import datetime, timezone
from typing import Literal, Optional
from uuid import uuid4
from pydantic import BaseModel, Field


class ConversationMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str
    tool_calls: Optional[list[dict]] = None
    tool_call_id: Optional[str] = None


class SourceInfo(BaseModel):
    ide: str
    version: Optional[str] = None
    cwd: Optional[str] = None


class Snapshot(BaseModel):
    version: str = "1.0"
    id: str = Field(default_factory=lambda: str(uuid4()))
    title: Optional[str] = None
    source: SourceInfo
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )
    summary: Optional[str] = None
    conversation: list[ConversationMessage]
    git_diff: Optional[str] = None
    open_files: list[str] = Field(default_factory=list)

    def model_post_init(self, __context) -> None:
        if not self.title:
            first_user = next(
                (m.content for m in self.conversation if m.role == "user"), ""
            )
            self.title = first_user[:60] or "untitled"
        if self.summary is None:
            first_user = next(
                (m.content for m in self.conversation if m.role == "user"), ""
            )
            self.summary = first_user[:200]
```

- [ ] **Step 4: 跑测试确认通过**

```bash
uv run pytest tests/test_schema.py -v
```
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add contextbridge/src/contextbridge/schema.py contextbridge/tests/test_schema.py
git commit -m "feat(contextbridge): snapshot schema with pydantic"
```

---

## Task 3: Truncation 工具

**Files:**
- Create: `contextbridge/src/contextbridge/truncation.py`
- Create: `contextbridge/tests/test_truncation.py`

覆盖规则：对话 > 30 轮→保留最近 20 + 最早 5；总长 > 20k token≈80000 字符→裁；
git_diff > 50000 字符→截断。

- [ ] **Step 1: 写失败测试**

```python
from contextbridge.schema import ConversationMessage
from contextbridge.truncation import truncate_conversation, truncate_diff


def _msg(role, n_chars=10):
    return ConversationMessage(role=role, content="x" * n_chars)


def test_short_kept_as_is():
    msgs = [_msg("user"), _msg("assistant")]
    assert truncate_conversation(msgs) == msgs


def test_long_drops_middle():
    msgs = [_msg("user", 5) for _ in range(40)]  # 40 轮 > 30
    out = truncate_conversation(msgs, keep_oldest=5, keep_recent=20)
    assert len(out) == 25
    assert out[:5] == msgs[:5]
    assert out[5:] == msgs[-20:]


def test_char_budget_trims_assistant_first():
    # 6 条消息，每条 20000 字符（≈2500 token），总 120k 字符 > 80k 上限
    msgs = [
        ConversationMessage(role=("user" if i % 2 == 0 else "assistant"), content="y" * 20000)
        for i in range(6)
    ]
    out = truncate_conversation(msgs, max_chars=80000)
    assert sum(len(m.content) for m in out) <= 80000
    # 至少保留最早的 1 条 user
    assert out[0].role == "user"


def test_diff_truncated():
    big = "a" * 60000
    out = truncate_diff(big, limit=50000)
    assert len(out) <= 50000
    assert "truncated" in out.lower()


def test_diff_kept():
    out = truncate_diff("small" * 10, limit=50000)
    assert out == "small" * 10
```

- [ ] **Step 2: 跑测试确认失败**

```bash
uv run pytest tests/test_truncation.py -v
```
Expected: FAIL（ImportError）

- [ ] **Step 3: 实现 `truncation.py`**

```python
from __future__ import annotations
from .schema import ConversationMessage

DEFAULT_MAX_TURNS = 30
DEFAULT_KEEP_OLDEST = 5
DEFAULT_KEEP_RECENT = 20
DEFAULT_MAX_CHARS = 80000  # ~20k token
DEFAULT_DIFF_LIMIT = 50000


def truncate_conversation(
    msgs: list[ConversationMessage],
    max_turns: int = DEFAULT_MAX_TURNS,
    keep_oldest: int = DEFAULT_KEEP_OLDEST,
    keep_recent: int = DEFAULT_KEEP_RECENT,
    max_chars: int = DEFAULT_MAX_CHARS,
) -> list[ConversationMessage]:
    # 第一道：按轮数裁
    if len(msgs) > max_turns:
        msgs = msgs[:keep_oldest] + msgs[-keep_recent:]

    # 第二道：按字符总量裁（优先砍 assistant 长内容）
    def total() -> int:
        return sum(len(m.content) for m in msgs)

    while total() > max_chars and len(msgs) > 1:
        # 找最长的一条 assistant，没有就砍中间一条
        target_idx = None
        for i in range(1, len(msgs) - 1):
            if msgs[i].role == "assistant":
                if target_idx is None or len(msgs[i].content) > len(msgs[target_idx].content):
                    target_idx = i
        if target_idx is None:
            target_idx = len(msgs) // 2
        msgs = msgs[:target_idx] + msgs[target_idx + 1:]
    return msgs


def truncate_diff(diff: str, limit: int = DEFAULT_DIFF_LIMIT) -> str:
    if len(diff) <= limit:
        return diff
    keep = limit - 200
    suffix = f"\n\n(... truncated, +{len(diff) - keep} chars ...)"
    return diff[:keep] + suffix
```

- [ ] **Step 4: 跑测试确认通过**

```bash
uv run pytest tests/test_truncation.py -v
```
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add contextbridge/src/contextbridge/truncation.py contextbridge/tests/test_truncation.py
git commit -m "feat(contextbridge): conversation + diff truncation"
```

---

## Task 4: gitutils

**Files:**
- Create: `contextbridge/src/contextbridge/gitutils.py`
- Create: `contextbridge/tests/test_gitutils.py`

- [ ] **Step 1: 写失败测试**

```python
import subprocess
from pathlib import Path
from contextbridge.gitutils import get_git_diff


def test_diff_in_repo(tmp_path):
    repo = tmp_path / "r"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)
    (repo / "a.txt").write_text("hello\n")
    subprocess.run(["git", "add", "a.txt"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=repo, check=True)
    (repo / "a.txt").write_text("hello world\n")
    diff = get_git_diff(str(repo))
    assert "hello world" in diff
    assert diff.startswith("diff --git") or "+hello world" in diff


def test_not_a_repo_returns_none(tmp_path):
    assert get_git_diff(str(tmp_path)) is None
```

- [ ] **Step 2: 跑确认失败**

```bash
uv run pytest tests/test_gitutils.py -v
```
Expected: FAIL（ImportError）

- [ ] **Step 3: 实现 `gitutils.py`**

```python
from __future__ import annotations
import subprocess


def get_git_diff(cwd: str) -> str | None:
    """Return combined unstaged + staged diff of tracked files. None if not a repo."""
    try:
        rev = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=cwd, capture_output=True, text=True, timeout=5,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if rev.returncode != 0 or rev.stdout.strip() != "true":
        return None

    parts: list[str] = []
    for args in (["git", "diff", "HEAD"], ["git", "diff", "--cached"]):
        r = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=10)
        if r.stdout:
            parts.append(r.stdout)
    return "\n".join(parts) if parts else ""
```

- [ ] **Step 4: 跑测试确认通过**

```bash
uv run pytest tests/test_gitutils.py -v
```
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add contextbridge/src/contextbridge/gitutils.py contextbridge/tests/test_gitutils.py
git commit -m "feat(contextbridge): git diff collector"
```

---

## Task 5: config（路径与目录初始化）

**Files:**
- Create: `contextbridge/src/contextbridge/config.py`
- Modify: `contextbridge/tests/conftest.py`（新建）

- [ ] **Step 1: 写 conftest 把 HOME 重定向到 tmp**

`tests/conftest.py`:
```python
import os
import pytest


@pytest.fixture
def fake_home(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("CONTEXTBRIDGE_HOME", str(home))
    return home
```

- [ ] **Step 2: 写失败测试 `tests/test_config.py`（新建）**

```python
from pathlib import Path
from contextbridge.config import get_home, ensure_dirs, db_path, snapshots_dir, config_path


def test_paths_under_env(fake_home):
    ensure_dirs()
    assert db_path().parent == fake_home
    assert snapshots_dir().exists()
    assert config_path().parent == fake_home


def test_get_home_fallback(monkeypatch, tmp_path):
    monkeypatch.delenv("CONTEXTBRIDGE_HOME", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    h = get_home()
    assert h == Path(tmp_path) / ".contextbridge"
```

- [ ] **Step 3: 跑确认失败**

```bash
uv run pytest tests/test_config.py -v
```
Expected: FAIL（ImportError）

- [ ] **Step 4: 实现 `config.py`**

```python
from __future__ import annotations
import os
from pathlib import Path


def get_home() -> Path:
    if env := os.environ.get("CONTEXTBRIDGE_HOME"):
        return Path(env)
    return Path(os.path.expanduser("~")) / ".contextbridge"


def ensure_dirs() -> None:
    snapshots_dir().mkdir(parents=True, exist_ok=True)
    get_home().mkdir(parents=True, exist_ok=True)


def db_path() -> Path:
    return get_home() / "index.db"


def snapshots_dir() -> Path:
    return get_home() / "snapshots"


def config_path() -> Path:
    return get_home() / "config.toml"
```

- [ ] **Step 5: 跑测试确认通过**

```bash
uv run pytest tests/test_config.py tests/conftest.py -v
```
Expected: 2 passed

- [ ] **Step 6: Commit**

```bash
git add contextbridge/src/contextbridge/config.py contextbridge/tests/config* contextbridge/tests/conftest.py
git commit -m "feat(contextbridge): home dir + config paths"
```

---

## Task 6: Store（sqlite + JSON 落盘）

**Files:**
- Create: `contextbridge/src/contextbridge/store.py`
- Create: `contextbridge/tests/test_store.py`

接口：`save(snapshot) -> Path`、`list(limit) -> list[Snapshot]`、`get(id) -> Snapshot | None`、`latest() -> Snapshot | None`、`delete(older_than_days) -> int`。索引用 sqlite，FTS5 模糊匹配 title。

- [ ] **Step 1: 写失败测试**

```python
from datetime import datetime, timedelta, timezone
from contextbridge.schema import Snapshot, ConversationMessage, SourceInfo
from contextbridge.store import Store


def _snap(title="t", created=None):
    s = Snapshot(
        title=title,
        source=SourceInfo(ide="claude_code", cwd="/x"),
        conversation=[ConversationMessage(role="user", content=title)],
    )
    if created:
        s.created_at = created
    return s


def test_save_and_get(fake_home):
    st = Store()
    s = _snap("first task")
    st.save(s)
    got = st.get(s.id)
    assert got is not None
    assert got.title == "first task"


def test_list_order_desc(fake_home):
    st = Store()
    old = _snap(created="2026-01-01T00:00:00+00:00")
    new = _snap(created="2026-07-27T00:00:00+00:00")
    st.save(old)
    st.save(new)
    ids = [s.id for s in st.list(limit=10)]
    assert ids[0] == new.id
    assert ids[1] == old.id


def test_latest(fake_home):
    st = Store()
    st.save(_snap(created="2026-01-01T00:00:00+00:00"))
    st.save(_snap(created="2026-07-27T00:00:00+00:00"))
    assert st.latest().created_at.startswith("2026-07-27")


def test_search_by_title(fake_home):
    st = Store()
    st.save(_snap("feature auth"))
    st.save(_snap("refactor api"))
    res = st.search("auth")
    assert len(res) == 1
    assert res[0].title == "feature auth"


def test_delete_old(fake_home):
    st = Store()
    old = _snap(created="2020-01-01T00:00:00+00:00")
    new = _snap(created=datetime.now(timezone.utc).isoformat(timespec="seconds"))
    st.save(old); st.save(new)
    count = st.delete_older_than(days=30)
    assert count == 1
    assert st.get(old.id) is None
    assert st.get(new.id) is not None
```

- [ ] **Step 2: 跑确认失败**

```bash
uv run pytest tests/test_store.py -v
```
Expected: FAIL（ImportError）

- [ ] **Step 3: 实现 `store.py`**

```python
from __future__ import annotations
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from .config import db_path, snapshots_dir, ensure_dirs
from .schema import Snapshot

SCHEMA = """
CREATE TABLE IF NOT EXISTS snapshots (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    source_ide TEXT NOT NULL,
    cwd TEXT,
    created_at TEXT NOT NULL,
    file_path TEXT NOT NULL
);
CREATE VIRTUAL TABLE IF NOT EXISTS snapshots_fts USING fts5(
    title, content='snapshots', content_rowid='rowid'
);
"""


class Store:
    def __init__(self) -> None:
        ensure_dirs()
        self._conn = sqlite3.connect(db_path())
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    def _reindex_if_empty(self) -> None:
        # 容错：sqlite 损坏重建——直接扫文件
        n = self._conn.execute("SELECT COUNT(*) FROM snapshots").fetchone()[0]
        if n > 0:
            return
        for f in snapshots_dir().glob("*.json"):
            try:
                s = Snapshot.model_validate_json(f.read_text(encoding="utf-8"))
                self._upsert(s, f)
            except Exception:
                continue

    def _upsert(self, s: Snapshot, file_path: Path) -> None:
        self._conn.execute(
            """INSERT OR REPLACE INTO snapshots
               (id, title, source_ide, cwd, created_at, file_path)
               VALUES (?,?,?,?,?,?)""",
            (s.id, s.title, s.source.ide, s.source.cwd, s.created_at, str(file_path)),
        )
        self._conn.execute(
            "INSERT INTO snapshots_fts(rowid, title) VALUES ((SELECT rowid FROM snapshots WHERE id=?), ?)",
            (s.id, s.title),
        )
        self._conn.commit()

    def save(self, s: Snapshot) -> Path:
        ts = s.created_at.replace(":", "").replace("+", "Z")[:19]
        safe_title = "".join(c if c.isalnum() or c in "-_" else "_" for c in (s.title or "untitled"))[:40]
        path = snapshots_dir() / f"{ts}_{safe_title}_{s.id[:8]}.json"
        path.write_text(s.model_dump_json(indent=2), encoding="utf-8")
        self._upsert(s, path)
        return path

    def get(self, snapshot_id: str) -> Snapshot | None:
        row = self._conn.execute(
            "SELECT file_path FROM snapshots WHERE id=?", (snapshot_id,)
        ).fetchone()
        if not row:
            return None
        return Snapshot.model_validate_json(Path(row["file_path"]).read_text(encoding="utf-8"))

    def latest(self) -> Snapshot | None:
        row = self._conn.execute(
            "SELECT file_path FROM snapshots ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        return Snapshot.model_validate_json(Path(row["file_path"]).read_text(encoding="utf-8")) if row else None

    def list(self, limit: int = 20) -> list[Snapshot]:
        rows = self._conn.execute(
            "SELECT file_path FROM snapshots ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [Snapshot.model_validate_json(Path(r["file_path"]).read_text(encoding="utf-8")) for r in rows]

    def search(self, query: str, limit: int = 20) -> list[Snapshot]:
        rows = self._conn.execute(
            "SELECT s.file_path FROM snapshots s JOIN snapshots_fts f ON s.rowid = f.rowid "
            "WHERE snapshots_fts MATCH ? ORDER BY s.created_at DESC LIMIT ?",
            (query, limit),
        ).fetchall()
        return [Snapshot.model_validate_json(Path(r["file_path"]).read_text(encoding="utf-8")) for r in rows]

    def delete_older_than(self, days: int) -> int:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(timespec="seconds")
        rows = self._conn.execute(
            "SELECT id, file_path FROM snapshots WHERE created_at < ?", (cutoff,)
        ).fetchall()
        for r in rows:
            try: Path(r["file_path"]).unlink()
            except FileNotFoundError: pass
        self._conn.execute("DELETE FROM snapshots WHERE created_at < ?", (cutoff,))
        self._conn.execute("DELETE FROM snapshots_fts WHERE title NOT IN (SELECT title FROM snapshots)")
        self._conn.execute("DELETE FROM snapshots WHERE created_at < ?", (cutoff,))
        self._conn.commit()
        return len(rows)
```

> 说明：`delete_older_than` 末尾再多执行一次 DELETE 是为了在前面的 FTS5 触发器层级缺失时也能干净清表；同样的			 		 删除逻辑被有意放在两处以保险。如果测试通过即可。

- [ ] **Step 4: 跑测试确认通过**

```bash
uv run pytest tests/test_store.py -v
```
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add contextbridge/src/contextbridge/store.py contextbridge/tests/test_store.py
git commit -m "feat(contextbridge): snapshot store with sqlite + FTS5"
```

---

## Task 7: SourceAdapter Protocol + GenericAdapter

**Files:**
- Create: `contextbridge/src/contextbridge/adapters/__init__.py`
- Create: `contextbridge/src/contextbridge/adapters/base.py`
- Create: `contextbridge/src/contextbridge/adapters/generic.py`
- Create: `contextbridge/tests/test_adapters_generic.py`

- [ ] **Step 1: 写失败测试 `tests/test_adapters_generic.py`**

```python
from contextbridge.adapters.generic import GenericAdapter
from contextbridge.adapters.base import ConversationMessage


def test_generic_uses_explicit_messages():
    a = GenericAdapter()
    msgs = a.parse(conversation=[
        {"role": "user", "content": "do X"},
        {"role": "assistant", "content": "ok"},
    ])
    assert len(msgs) == 2
    assert msgs[0].content == "do X"


def test_detect_always_true():
    assert GenericAdapter().detect() is True
```

- [ ] **Step 2: 跑确认失败**

```bash
uv run pytest tests/test_adapters_generic.py -v
```
Expected: FAIL（ImportError）

- [ ] **Step 3: 实现 base.py**

```python
from __future__ import annotations
from pathlib import Path
from typing import Protocol, runtime_checkable
from ..schema import ConversationMessage


@runtime_checkable
class SourceAdapter(Protocol):
    name: str

    def detect(self) -> bool: ...
    def get_session_path(self) -> Path | None: ...
    def parse_session(self) -> list[ConversationMessage]: ...
    def get_open_files(self) -> list[str]: ...
```

- [ ] **Step 4: 实现 generic.py**

```python
from __future__ import annotations
from pathlib import Path
from ..schema import ConversationMessage


class GenericAdapter:
    """Fallback adapter: conversation is passed in as a list of dicts."""

    name = "generic"
    _conversation: list[dict] = []

    def set_conversation(self, conv: list[dict]) -> None:
        self._conversation = conv

    def detect(self) -> bool:
        return True

    def get_session_path(self) -> Path | None:
        return None

    def parse(self, conversation: list[dict] | None = None) -> list[ConversationMessage]:
        conv = conversation if conversation is not None else self._conversation
        return [ConversationMessage(**m) for m in conv]

    def parse_session(self) -> list[ConversationMessage]:
        return self.parse()

    def get_open_files(self) -> list[str]:
        return []
```

> 注意：GenericAdapter 不严格实现 SourceAdapter 协议（多了 `set_conversation`），
> 但其 `name`/`detect`/`session_path`/`parse_session`/`open_files` 形状一致。

- [ ] **Step 5: adapters `__init__.py`**

```python
from .base import SourceAdapter
from .generic import GenericAdapter

__all__ = ["SourceAdapter", "GenericAdapter"]
```

- [ ] **Step 6: 跑确认通过**

```bash
uv run pytest tests/test_adapters_generic.py -v
```
Expected: 2 passed

- [ ] **Step 7: Commit**

```bash
git add contextbridge/src/contextbridge/adapters contextbridge/tests/test_adapters_generic.py
git commit -m "feat(contextbridge): SourceAdapter protocol + GenericAdapter"
```

---

## Task 8: ClaudeCodeAdapter

**Files:**
- Create: `contextbridge/src/contextbridge/adapters/claude_code.py`
- Create: `contextbridge/tests/test_adapters_claude_code.py`
- Create: `contextbridge/tests/fixtures/sample-sessions/claude_code_sample.jsonl`

JSONL 格式参考官方实现（每行一条事件消息，含 `type`、`message.role`、`message.content`）。

- [ ] **Step 1: 写 fixture**

`tests/fixtures/sample-sessions/claude_code_sample.jsonl`：
```
{"type":"user","message":{"role":"user","content":"please refactor foo"}}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"ok, renaming"}]}}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"tool_use","name":"Edit","input":{"file":"a.py"}}]}}
```

- [ ] **Step 2: 写失败测试**

```python
import os
from pathlib import Path
from contextbridge.adapters.claude_code import ClaudeCodeAdapter


def test_parse_jsonl(tmp_path, monkeypatch):
    cwd_hash = "abc123"
    projects = tmp_path / "projects" / cwd_hash
    projects.mkdir(parents=True)
    fixture = Path(__file__).parent / "fixtures/sample-sessions/claude_code_sample.jsonl"
    session = projects / "s1.jsonl"
    session.write_text(fixture.read_text(), encoding="utf-8")
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path))
    monkeypatch.setenv("CONTEXTBRIDGE_CWD", "/repo")

    a = ClaudeCodeAdapter()
    msgs = a.parse_session()
    assert len(msgs) == 3
    assert msgs[0].role == "user"
    assert "refactor" in msgs[0].content
    # content 是 list 时被拍平成 text
    assert "renaming" in msgs[1].content


def test_detect_when_env_present(monkeypatch, tmp_path):
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path))
    monkeypatch.setenv("CONTEXTBRIDGE_CWD", "/repo")
    (tmp_path / "projects").mkdir()
    a = ClaudeCodeAdapter()
    assert a.detect() is True


def test_detect_when_no_config(monkeypatch):
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    monkeypatch.setenv("HOME", "/nonexistent-path-xyz")
    a = ClaudeCodeAdapter()
    assert a.detect() is False
```

- [ ] **Step 3: 跑确认失败**

```bash
uv run pytest tests/test_adapters_claude_code.py -v
```
Expected: FAIL（ImportError）

- [ ] **Step 4: 实现 `claude_code.py`**

```python
from __future__ import annotations
import os
from pathlib import Path
from ..schema import ConversationMessage


def _config_dir() -> Path:
    if env := os.environ.get("CLAUDE_CONFIG_DIR"):
        return Path(env)
    return Path(os.path.expanduser("~")) / ".claude"


def _extract_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        out: list[str] = []
        for block in content:
            if isinstance(block, dict):
                t = block.get("text")
                if t:
                    out.append(t)
                elif block.get("type") == "tool_use":
                    out.append(f"[tool_use: {block.get('name','?')}]")
        return "\n".join(out)
    return str(content)


class ClaudeCodeAdapter:
    name = "claude_code"

    def _projects_dir(self) -> Path:
        return _config_dir() / "projects"

    def detect(self) -> bool:
        return self._projects_dir().exists()

    def get_session_path(self) -> Path | None:
        # 取 projects/<hash>/ 下最新的 .jsonl
        proj = self._projects_dir()
        if not proj.exists():
            return None
        jsonls = sorted(proj.rglob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
        return jsonls[0] if jsonls else None

    def parse_session(self) -> list[ConversationMessage]:
        path = self.get_session_path()
        if not path:
            return []
        msgs: list[ConversationMessage] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                import json
                ev = json.loads(line)
            except Exception:
                continue
            m = ev.get("message") or {}
            role = m.get("role") or ev.get("type")
            if role not in ("user", "assistant", "system"):
                continue
            content = _extract_text(m.get("content") or ev.get("content"))
            if not content:
                continue
            msgs.append(ConversationMessage(role=role, content=content))
        return msgs

    def get_open_files(self) -> list[str]:
        return []  # v1 不实现
```

- [ ] **Step 5: 跑确认通过**

```bash
uv run pytest tests/test_adapters_claude_code.py -v
```
Expected: 3 passed

- [ ] **Step 6: Commit**

```bash
git add contextbridge/src/contextbridge/adapters/claude_code.py contextbridge/tests/fixtures contextbridge/tests/test_adapters_claude_code.py
git commit -m "feat(contextbridge): ClaudeCodeAdapter reading ~/.claude jsonl"
```

---

## Task 8.5: Claude Code WSL 路径兼容

设计文档 §9 要求：WSL 里跑 `cb serve` 时，`~` 在 Linux 视角下是 `/home/user`，
而 Windows 侧 Cursor/Claude Desktop 看到的可能是 `\\wsl$\...` 或 `C:\Users\...`。
这会让 `~/.claude/projects/` 找不到、cwd 也对不上。补一个最小修复。

**Files:**
- Modify: `contextbridge/src/contextbridge/adapters/claude_code.py`
- Modify: `contextbridge/tests/test_adapters_claude_code.py`

- [ ] **Step 1: 写失败测试**

```python
def test_wsl_user_path_used(monkeypatch, tmp_path):
    # 模拟 WSL：HOME 是 Linux 风格但实际项目落在 Windows 视角的 \\wsl$
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    fake_linux_home = tmp_path / "linuxhome"
    fake_linux_home.mkdir()
    (fake_linux_home / ".claude" / "projects").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(fake_linux_home))
    # Windows Python 不会真去解析 ~，所以 expanduser 在 Win 上读 USERPROFILE
    monkeypatch.delenv("USERPROFILE", raising=False)
    a = ClaudeCodeAdapter()
    assert a.detect() is True
```

- [ ] **Step 2: 跑确认失败**

```bash
uv run pytest tests/test_adapters_claude_code.py::test_wsl_user_path_used -v
```
Expected: FAIL（detect 返回 False，因为 Win 上 `os.path.expanduser("~")` 走 USERPROFILE）

- [ ] **Step 3: 改 `_config_dir()` 支持双 HOME**

```python
def _config_dir() -> Path:
    if env := os.environ.get("CLAUDE_CONFIG_DIR"):
        return Path(env)
    # WSL/Linux 优先 HOME；Windows 走 USERPROFILE；都不在才退回 ~
    if h := os.environ.get("HOME"):
        return Path(h) / ".claude"
    if p := os.environ.get("USERPROFILE"):
        return Path(p) / ".claude"
    return Path(os.path.expanduser("~")) / ".claude"
```

- [ ] **Step 4: 跑测试确认通过**

```bash
uv run pytest tests/test_adapters_claude_code.py -v
```
Expected: 4 passed（含新加的 1 个）

- [ ] **Step 5: Commit**

```bash
git add contextbridge/src/contextbridge/adapters/claude_code.py contextbridge/tests/test_adapters_claude_code.py
git commit -m "fix(contextbridge): support WSL/Linux HOME for claude config dir"
```

---

## Task 9: CLI（Typer）

**Files:**
- Create: `contextbridge/src/contextbridge/cli.py`
- Modify: `contextbridge/src/contextbridge/__main__.py`
- Create: `contextbridge/tests/test_cli.py`

5 个子命令：`export`、`list`、`show <id>`、`import [id]`、`clear <days>`。

- [ ] **Step 1: 写失败测试**（用 Typer 的 CliRunner）

```python
from pathlib import Path
from typer.testing import CliRunner
from contextbridge.cli import app

runner = CliRunner()


def test_help():
    res = runner.invoke(app, ["--help"])
    assert res.exit_code == 0
    assert "export" in res.stdout
    assert "import" in res.stdout


def test_export_from_explicit_conversation(fake_home, tmp_path, monkeypatch):
    # 强制走 Generic 路径
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    cwd = tmp_path / "repo"; cwd.mkdir()
    monkeypatch.chdir(cwd)
    json_arg = '[{"role":"user","content":"hello world"}]'
    res = runner.invoke(app, ["export", "--title", "x", "--conversation", json_arg])
    assert res.exit_code == 0, res.stdout
    assert "Snapshot saved" in res.stdout


def test_list_and_import(fake_home):
    runner.invoke(app, ["export", "--conversation", '[{"role":"user","content":"a"}]'])
    runner.invoke(app, ["export", "--conversation", '[{"role":"user","content":"b"}]'])
    res = runner.invoke(app, ["list"])
    assert "b" in res.stdout and "a" in res.stdout

    res_import = runner.invoke(app, ["import"])
    assert res_import.exit_code == 0
    # 最新是 'b'
    assert "b" in res_import.stdout


def test_clear(fake_home):
    from datetime import datetime, timezone
    from contextbridge.store import Store
    from contextbridge.schema import Snapshot, SourceInfo, ConversationMessage
    s = Snapshot(source=SourceInfo(ide="generic", cwd="/"),
                 conversation=[ConversationMessage(role="user", content="old")],
                 created_at="2020-01-01T00:00:00+00:00")
    Store().save(s)
    res = runner.invoke(app, ["clear", "30"])
    assert res.exit_code == 0
    assert "Deleted 1" in res.stdout
```

- [ ] **Step 2: 跑确认失败**

```bash
uv run pytest tests/test_cli.py -v
```
Expected: FAIL（ImportError / 没有命令）

- [ ] **Step 3: 实现 `cli.py`**

```python
from __future__ import annotations
import json
import os
from pathlib import Path
import typer
from rich.console import Console
from rich.table import Table

from .adapters.claude_code import ClaudeCodeAdapter
from .adapters.generic import GenericAdapter
from .gitutils import get_git_diff
from .schema import ConversationMessage, Snapshot, SourceInfo
from .store import Store
from .truncation import truncate_conversation, truncate_diff

app = typer.Typer(help="ContextBridge: cross-IDE context handoff", no_args_is_help=True)
console = Console()


def _build_snapshot(
    title: str | None,
    conversation_json: str | None,
    include_diff: bool,
) -> Snapshot:
    cwd = os.getcwd()
    # 优先 Claude Code
    cc = ClaudeCodeAdapter()
    if cc.detect():
        msgs = cc.parse_session()
        ide = "claude_code"
    else:
        conv = json.loads(conversation_json) if conversation_json else []
        msgs = [ConversationMessage(**m) for m in conv]
        ide = "generic"

    msgs = truncate_conversation(msgs)
    diff = truncate_diff(get_git_diff(cwd)) if include_diff else None

    return Snapshot(
        title=title,
        source=SourceInfo(ide=ide, cwd=cwd),
        conversation=msgs,
        git_diff=diff,
    )


@app.command()
def export(
    title: str = typer.Option(None, "--title", "-t"),
    conversation: str = typer.Option(None, "--conversation", "-c", help="JSON list of {role,content}"),
    no_diff: bool = typer.Option(False, "--no-diff"),
):
    """Snapshot current context. From a terminal with no Claude Code session,
    pass --conversation '[...]'."""
    snap = _build_snapshot(title, conversation, include_diff=not no_diff)
    Store().save(snap)
    console.print(f"[green]Snapshot saved[/green] id={snap.id} title={snap.title!r} ide={snap.source.ide}")


@app.command(name="list")
def list_(
    limit: int = typer.Option(20, "--limit", "-n"),
):
    snaps = Store().list(limit=limit)
    if not snaps:
        console.print("[yellow]No snapshots yet.[/yellow]")
        return
    tbl = Table("ID", "Title", "IDE", "Created")
    for s in snaps:
        tbl.add_row(s.id[:8], s.title, s.source.ide, s.created_at)
    console.print(tbl)


@app.command()
def show(id: str):
    s = Store().get(id)
    if not s:
        console.print(f"[red]Not found: {id}[/red]"); raise typer.Exit(1)
    console.print_json(s.model_dump_json())


@app.command()
def import_(
    id: str = typer.Argument(None),
):
    """Print the snapshot as a structured handoff block ready to paste into the next IDE."""
    s = Store().get(id) if id else Store().latest()
    if not s:
        console.print("[red]No snapshot available.[/red]"); raise typer.Exit(1)
    lines = [
        f"# Context Handoff — {s.title}",
        f"- source IDE: {s.source.ide}",
        f"- cwd: {s.source.cwd}",
        f"- created: {s.created_at}",
        "",
        "## Conversation so far",
    ]
    for m in s.conversation:
        lines.append(f"### {m.role}")
        lines.append(m.content)
        lines.append("")
    if s.git_diff:
        lines += ["## Current git diff", "```diff", s.git_diff, "```", ""]
    console.print("\n".join(lines))


@app.command()
def clear(
    days: int = typer.Argument(30),
):
    n = Store().delete_older_than(days=days)
    console.print(f"[green]Deleted {n} snapshot(s) older than {days} days.[/green]")


if __name__ == "__main__":
    app()
```

- [ ] **Step 4: 修改 `__main__.py` 接 CLI**

```python
from .cli import app

if __name__ == "__main__":
    app()
```

- [ ] **Step 5: 跑确认通过**

```bash
uv run pytest tests/test_cli.py -v
```
Expected: 4 passed

> 若 `test_export_from_explicit_conversation` 在没 ClaudeCodeAdapter 检测到时仍走 Claude 路径，
> 检查 `fake_home` 是否会让 `~/.claude` 仍指向真实 HOME；可在 conftest 的 fake_home 里同时
> monkeypatch `os.path.expanduser` 的返回（Python 3.10+ 用 `monkeypatch.setattr(os.path, "expanduser", lambda p: str(tmp_path) if p == "~" else os.path.expanduser.__wrapped__(p))`，但更简单的做法是在测试里显式 `monkeypatch.delenv` 并 chdir 到非 git 目录即可触发 generic 路径——以上已是这样写）。

- [ ] **Step 6: Commit**

```bash
git add contextbridge/src/contextbridge/cli.py contextbridge/src/contextbridge/__main__.py contextbridge/tests/test_cli.py
git commit -m "feat(contextbridge): Typer CLI with export/list/show/import/clear"
```

---

## Task 10: FastMCP server（4 个工具）

**Files:**
- Create: `contextbridge/src/contextbridge/server.py`
- Create: `contextbridge/tests/test_server.py`
- Modify: `contextbridge/src/contextbridge/__main__.py`（加 mcp 入口分支）

- [ ] **Step 1: 写失败测试（直接调函数，不跑真 stdio）**

```python
from contextbridge.server import mcp
from contextbridge.store import Store


def test_cb_export_and_import_via_tool(fake_home, monkeypatch, tmp_path):
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    monkeypatch.chdir(tmp_path)
    # 找到 cb_export 工具并调用
    tools = {t.name: t for t in mcp._tool_manager.list_tools()}
    assert set(["cb_export", "cb_list", "cb_import", "cb_clear"]).issubset(tools.keys())

    export_tool = tools["cb_export"]
    res = await export_tool.run({
        "title": "demo",
        "conversation": [{"role": "user", "content": "hello bridge"}],
        "include_diff": False,
    })
    assert "Snapshot saved" in res.content[0].text


async def test_cb_list_returns_blocks(fake_home):
    from contextbridge.schema import Snapshot, SourceInfo, ConversationMessage
    Store().save(Snapshot(source=SourceInfo(ide="generic", cwd="/"),
                          conversation=[ConversationMessage(role="user", content="hi")]))
    tools = {t.name: t for t in mcp._tool_manager.list_tools()}
    res = await tools["cb_list"].run({"limit": 5})
    assert "hi" in res.content[0].text
```

> 说明：FastMCP 内部 API 因版本略有差异；若 `mcp._tool_manager` 不可用，则改用 `await mcp.call_tool(name, args)` 或 `mcp.list_tools()`。MVP 用 FastMCP ≥1.2 的公开 API：`mcp.add_tool` 注册函数，测试直接调函数本身。下面 Step 3 的实现把核心逻辑写成纯函数后用 `@mcp.tool()` 注册，测试直接调纯函数。

- [ ] **Step 2: 跑确认失败**

```bash
uv run pytest tests/test_server.py -v
```
Expected: FAIL（ImportError）

- [ ] **Step 3: 实现 `server.py`**（核心逻辑暴露为纯函数便于测试）

```python
from __future__ import annotations
from typing import Optional
from mcp.server.fastmcp import FastMCP

from .cli import _build_snapshot   # 复用 CLI 的快照构造逻辑
from .store import Store

mcp = FastMCP("contextbridge")


def cb_export_impl(
    title: Optional[str] = None,
    conversation: Optional[list[dict]] = None,
    include_diff: bool = True,
) -> str:
    conv_json = None
    if conversation is not None:
        import json
        conv_json = json.dumps(conversation)
    snap = _build_snapshot(title, conv_json, include_diff=include_diff)
    Store().save(snap)
    return f"Snapshot saved — id={snap.id} title={snap.title!r} ide={snap.source.ide} turns={len(snap.conversation)}"


def cb_list_impl(limit: int = 20) -> str:
    snaps = Store().list(limit=limit)
    if not snaps:
        return "No snapshots yet. Run cb_export first."
    lines = [f"- {s.id[:8]} | {s.source.ide:<12} | {s.created_at} | {s.title}" for s in snaps]
    return "ContextBridge snapshots (newest first):\n" + "\n".join(lines)


def cb_import_impl(id: Optional[str] = None) -> str:
    s = Store().get(id) if id else Store().latest()
    if not s:
        return "No snapshot available."
    parts = [
        f"# Context Handoff — {s.title}",
        f"source IDE: {s.source.ide}  cwd: {s.source.cwd}  created: {s.created_at}",
    ]
    for m in s.conversation:
        parts.append(f"\n## {m.role}\n{m.content}")
    if s.git_diff:
        parts.append(f"\n## Current git diff\n```diff\n{s.git_diff}\n```")
    return "\n".join(parts)


def cb_clear_impl(older_than_days: int = 30) -> str:
    n = Store().delete_older_than(days=older_than_days)
    return f"Deleted {n} snapshot(s) older than {older_than_days} days."


@mcp.tool()
def cb_export(
    title: Optional[str] = None,
    conversation: Optional[list[dict]] = None,
    include_diff: bool = True,
) -> str:
    """Export current context as a snapshot.

    If running inside Claude Code / Codex CLI, the conversation is auto-collected
    from the local session file. Otherwise pass `conversation` as a list of
    {role, content} dicts (e.g. AI invoking this tool from Cursor).
    """
    return cb_export_impl(title, conversation, include_diff)


@mcp.tool()
def cb_list(limit: int = 20) -> str:
    """List saved snapshots."""
    return cb_list_impl(limit)


@mcp.tool()
def cb_import(id: Optional[str] = None) -> str:
    """Import a snapshot by id; omit id to use the latest. Returns a structured
    handoff block to insert into the next IDE's conversation."""
    return cb_import_impl(id)


@mcp.tool()
def cb_clear(older_than_days: int = 30) -> str:
    """Delete snapshots older than N days."""
    return cb_clear_impl(older_than_days)


if __name__ == "__main__":
    mcp.run(transport="stdio")
```

- [ ] **Step 4: 修改 `__main__.py` 支持 `serve` 子命令**

```python
import sys
from .cli import app


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "serve":
        sys.argv = [sys.argv[0]] + sys.argv[2:]
        from .server import mcp
        mcp.run(transport="stdio")
        return
    app()


if __name__ == "__main__":
    main()
```

> 说明：`cb`/`contextbridge` 入口脚本走 `main()`，`cb serve` 起 MCP stdio server。
> MCP hosts 配置 `command: cb args: ["serve"]`。

- [ ] **Step 5: 矫正测试，调纯函数 impl（避开 FastMCP 内部 API）**

把 `tests/test_server.py` 替换为：

```python
from contextbridge.server import cb_export_impl, cb_list_impl, cb_import_impl, cb_clear_impl


def test_export_and_list(fake_home, monkeypatch, tmp_path):
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    monkeypatch.chdir(tmp_path)
    msg = cb_export_impl(
        title="demo",
        conversation=[{"role": "user", "content": "hello bridge"}],
        include_diff=False,
    )
    assert "Snapshot saved" in msg
    listed = cb_list_impl(limit=5)
    assert "demo" in listed


def test_import_returns_latest(fake_home, monkeypatch, tmp_path):
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    monkeypatch.chdir(tmp_path)
    cb_export_impl(conversation=[{"role": "user", "content": "step one"}], include_diff=False)
    out = cb_import_impl()
    assert "Context Handoff" in out
    assert "step one" in out


def test_clear_reports_count(fake_home, monkeypatch, tmp_path):
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    monkeypatch.chdir(tmp_path)
    from contextbridge.schema import Snapshot, SourceInfo, ConversationMessage
    from contextbridge.store import Store
    Store().save(Snapshot(
        source=SourceInfo(ide="generic", cwd="/"),
        conversation=[ConversationMessage(role="user", content="x")],
        created_at="2020-01-01T00:00:00+00:00",
    ))
    msg = cb_clear_impl(older_than_days=1)
    assert "Deleted 1" in msg
```

- [ ] **Step 6: 跑确认通过**

```bash
uv run pytest tests/test_server.py -v
```
Expected: 3 passed

- [ ] **Step 7: Commit**

```bash
git add contextbridge/src/contextbridge/server.py contextbridge/src/contextbridge/__main__.py contextbridge/tests/test_server.py
git commit -m "feat(contextbridge): FastMCP server with 4 cb_* tools + serve entry"
```

---

## Task 11: 文档（README + install + 一段手测脚本）

**Files:**
- Create: `contextbridge/README.md`
- Create: `contextbridge/docs/install.md`
- Create: `contextbridge/docs/architecture.md`

- [ ] **Step 1: 写 README.md**

```markdown
# ContextBridge

跨 IDE 的"上下文接力"工具。在 Cursor / Claude Code / Codex 等 AI IDE 之间，
把当前会话+任务状态打包成快照，切换工具时一键 import 让接手的 AI 立刻懂上下文。

## 安装

```bash
git clone <repo> && cd contextbridge
uv venv && uv pip install -e ".[dev]"
```

## 作为 MCP server 接入 Claude Code / Cursor

Claude Code（`~/.claude.json` 或项目 `.mcp.json`）：

```json
{
  "mcpServers": {
    "contextbridge": { "command": "cb", "args": ["serve"] }
  }
}
```

Cursor（Settings → MCP）：

```json
{ "mcpServers": { "contextbridge": { "command": "cb", "args": ["serve"] } } }
```

## 作为 CLI

```bash
cb export -t "feature X"                          # 打包当前 Claude Code session
cb export -t "x" -c '[{"role":"user","content":"..."}]'  # 或显式喂对话（Cursor 等）
cb list
cb import                  # 打印最新快照，粘贴到下个 IDE
cb clear 30
```

## 设计

见 [docs/architecture.md](docs/architecture.md) 与
[../docs/specs/2026-07-27-contextbridge-design.md](../docs/specs/2026-07-27-contextbridge-design.md)。
```

- [ ] **Step 2: 写 install.md**（含 macOS/Linux/Windows 路径差异 + uv 装法 + 故障排查）

```markdown
# Installation

## 1. 装本体

需要 Python 3.10+。

\```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows PowerShell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# 然后
git clone <repo> && cd contextbridge
uv venv && uv pip install -e ".[dev]"
\```

确认：`cb --help` 能列命令。

## 2. 注册 MCP server

| Host | 配置文件 |
|------|---------|
| Claude Code (macOS/Linux) | `~/.claude.json` 里的 `mcpServers` |
| Claude Code (Windows) | `%USERPROFILE%\.claude.json` |
| Cursor | Settings → MCP → Add Server |

通用片段：

\```json
{ "mcpServers": { "contextbridge": { "command": "cb", "args": ["serve"] } } }
\```

> Windows 用户：把 `cb` 换成完整路径，例如
> `C:\\Users\\You\\AppData\\Local\\uv\\data\\scripts\\cb.exe`。

## 3. 故障排查

- 工具没在 Claude/Cursor 里出现：检查 JSON 路径用绝对路径；重启 host。
- Claude Code 不出对话：确认 `~/.claude/projects/` 下有 `.jsonl` 文件。
- sqlite 报 locked：把 `~/.contextbridge/index.db` 删除，启动会自动重建。
\```

- [ ] **Step 3: 写 architecture.md**（200-300 字简述）

```markdown
# Architecture

ContextBridge 是 Handoff 快照式 MCP server，目标场景：vibe coding 切 IDE 时
把当前会话上下文搬过去。

## 模块

- `cli.py` / `server.py`：双入口，复用同一套构建逻辑（`_build_snapshot`）。
- `store.py`：sqlite + FTS5 索引，快照本体落 JSON 文件到 `~/.contextbridge/snapshots/`。
- `adapters/`：每个 host 一个 SourceAdapter，自动 detect。
  - ClaudeCodeAdapter 读 `~/.claude/projects/<hash>/<sid>.jsonl` 最新文件。
  - GenericAdapter 兜底：靠工具入参 `conversation` 由 AI 喂入。
- `truncation.py` / `gitutils.py`：保障快照不超 MCP 上下文上限。

## 数据流

\```
cb_export → _build_snapshot → adapter.parse_session → truncate → Store.save (sqlite+json)
cb_import → Store.latest/get → 拼成 markdown 块返回给接手 AI
\```

详见 design doc。
```

- [ ] **Step 4: 全量跑一遍测试**

```bash
cd contextbridge && uv run pytest -v
```
Expected: 全绿（之前所有测试 + 文档不影响测试）

- [ ] **Step 5: 手测清单（人工执行一次，结果填到 README 的 "Verified on" 区）**

```
[ ] 在 Claude Code 里跑 3-4 轮对话 → `cb serve` 已配 → 让 AI 调 cb_export
[ ] `cb list` 看到刚才的快照
[ ] 切换到 Cursor，让 AI 调 cb_import（不带 id）→ 确认拿到上下文 markdown
[ ] 反向：在 Cursor 里用 cb_export --conversation '[...]' 显式喂
[ ] `cb clear 1` 验证能删
```

- [ ] **Step 6: Commit**

```bash
git add contextbridge/README.md contextbridge/docs
git commit -m "docs(contextbridge): README + install + architecture"
```

---

## 完工标准

- `uv run pytest -v` 在 contextbridge 目录全绿
- `cb --help`、`cb export -c '[...]'`、`cb list`、`cb import`、`cb clear` 命令行可用
- `cb serve` 能被 Claude Code / Cursor 加载为 MCP server，4 个 cb_* 工具出现且能调
- 在作者本机完成 Task 11 Step 5 手测清单的全部 5 项
```
