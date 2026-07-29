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

MAX_SNAPSHOT_SIZE_BYTES = 1_000_000


class SnapshotTooLargeError(Exception):
    """Raised when a serialized snapshot exceeds the configured size limit."""


class Store:
    # 进程级单例:MCP server 长期运行,每次 tool 调用若新建 sqlite 连接会泄漏。
    # CLI 进程短命,单例也无害。测试用 reset_connection() 隔离。
    _conn: sqlite3.Connection | None = None

    @classmethod
    def reset_connection(cls) -> None:
        """Drop the cached connection. Used by tests to switch CONTEXTBRIDGE_HOME."""
        if cls._conn is not None:
            cls._conn.close()
            cls._conn = None

    @classmethod
    def _connection(cls) -> sqlite3.Connection:
        if cls._conn is None:
            ensure_dirs()
            conn = sqlite3.connect(db_path())
            conn.row_factory = sqlite3.Row
            conn.executescript(SCHEMA)
            conn.commit()
            cls._conn = conn
            Store._reindex_if_empty(conn)
        return cls._conn

    def __init__(self) -> None:
        # 触发单例初始化(兼容旧用法 Store().get(...))
        self._conn = self._connection()

    @staticmethod
    def _reindex_if_empty(conn: sqlite3.Connection) -> None:
        n = conn.execute("SELECT COUNT(*) FROM snapshots").fetchone()[0]
        if n > 0:
            return
        for f in snapshots_dir().glob("*.json"):
            try:
                s = Snapshot.model_validate_json(f.read_text(encoding="utf-8"))
            except Exception:
                continue
            conn.execute(
                """INSERT OR REPLACE INTO snapshots
                   (id, title, source_ide, cwd, created_at, file_path)
                   VALUES (?,?,?,?,?,?)""",
                (s.id, s.title, s.source.ide, s.source.cwd, s.created_at, str(f)),
            )
            conn.execute(
                "INSERT INTO snapshots_fts(rowid, title) VALUES ((SELECT rowid FROM snapshots WHERE id=?), ?)",
                (s.id, s.title),
            )
        conn.commit()

    def _read_or_none(self, row: sqlite3.Row | None) -> Snapshot | None:
        """读取快照文件;文件缺失(DB 有孤儿行)时返回 None 而非抛异常。"""
        if row is None:
            return None
        try:
            return Snapshot.model_validate_json(Path(row["file_path"]).read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError):
            return None

    def _upsert(self, s: Snapshot, file_path: Path) -> None:
        self._conn.execute("DELETE FROM snapshots_fts WHERE rowid = (SELECT rowid FROM snapshots WHERE id=?)", (s.id,))
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
        payload = s.model_dump_json(indent=2)
        if len(payload.encode("utf-8")) > MAX_SNAPSHOT_SIZE_BYTES:
            raise SnapshotTooLargeError(
                f"Snapshot is {len(payload)} bytes, exceeds limit of {MAX_SNAPSHOT_SIZE_BYTES}. "
                "Reduce conversation length or git diff size."
            )
        path.write_text(payload, encoding="utf-8")
        self._upsert(s, path)
        return path

    def get(self, snapshot_id: str) -> Snapshot | None:
        # 接受完整 UUID 或 cb_list 显示的 8 位前缀。优先精确匹配,再做前缀 LIKE。
        row = self._conn.execute(
            "SELECT file_path FROM snapshots WHERE id = ?", (snapshot_id,)
        ).fetchone()
        if row is None:
            row = self._conn.execute(
                "SELECT file_path FROM snapshots WHERE id LIKE ? || '%' ORDER BY created_at DESC LIMIT 1",
                (snapshot_id,),
            ).fetchone()
        return self._read_or_none(row)

    def latest(self) -> Snapshot | None:
        row = self._conn.execute(
            "SELECT file_path FROM snapshots ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        return self._read_or_none(row)

    def list(self, limit: int = 20) -> list[Snapshot]:
        rows = self._conn.execute(
            "SELECT file_path FROM snapshots ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [s for s in (self._read_or_none(r) for r in rows) if s is not None]

    def search(self, query: str, limit: int = 20) -> list[Snapshot]:
        rows = self._conn.execute(
            "SELECT s.file_path FROM snapshots s JOIN snapshots_fts f ON s.rowid = f.rowid "
            "WHERE snapshots_fts MATCH ? ORDER BY s.created_at DESC LIMIT ?",
            (query, limit),
        ).fetchall()
        return [s for s in (self._read_or_none(r) for r in rows) if s is not None]

    def delete_older_than(self, days: int) -> int:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(timespec="seconds")
        rows = self._conn.execute(
            "SELECT id, file_path FROM snapshots WHERE created_at < ?", (cutoff,)
        ).fetchall()
        for r in rows:
            try: Path(r["file_path"]).unlink()
            except FileNotFoundError: pass
        self._conn.execute(
            "DELETE FROM snapshots_fts WHERE rowid IN (SELECT rowid FROM snapshots WHERE created_at < ?)",
            (cutoff,),
        )
        self._conn.execute("DELETE FROM snapshots WHERE created_at < ?", (cutoff,))
        self._conn.commit()
        return len(rows)
