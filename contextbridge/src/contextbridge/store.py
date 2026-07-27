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
        self._conn.commit()
        return len(rows)
