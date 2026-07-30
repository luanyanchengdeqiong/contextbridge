from datetime import datetime, timedelta, timezone
import pytest
from contextbridge.schema import Snapshot, ConversationMessage, SourceInfo
from contextbridge.store import Store, SnapshotTooLargeError, db_path


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


def test_delete_removes_orphan_fts_rows(fake_home):
    st = Store()
    old = _snap(created="2020-01-01T00:00:00+00:00", title="old-unique-search-term")
    new = _snap(created="2026-07-28T00:00:00+00:00", title="new-keep")
    st.save(old)
    st.save(new)
    assert len(st.search("unique")) == 1
    st.delete_older_than(days=30)
    n = st._conn.execute("SELECT COUNT(*) FROM snapshots_fts").fetchone()[0]
    assert n == 1, f"expected fts to only have 1 row after delete, got {n}"
    assert st.search("unique") == []


def test_save_rejects_oversized(fake_home):
    st = Store()
    huge_content = "x" * (2 * 1024 * 1024)
    big = Snapshot(
        source=SourceInfo(ide="generic", cwd="/"),
        conversation=[ConversationMessage(role="user", content=huge_content)],
    )
    with pytest.raises(SnapshotTooLargeError):
        st.save(big)


def test_rebuild_index_from_json_files(fake_home):
    st1 = Store()
    s = _snap(title="persisted")
    st1.save(s)
    Store.reset_connection()
    db_path().unlink()
    st2 = Store()
    rebuilt = st2.get(s.id)
    assert rebuilt is not None
    assert rebuilt.title == "persisted"
    assert any(x.id == s.id for x in st2.list(limit=10))
    assert any(x.id == s.id for x in st2.search("persisted"))


def test_get_accepts_short_prefix(fake_home):
    """Store.get 应接受 cb_list 显示的 8 位前缀。"""
    st = Store()
    s = _snap(title="prefixable")
    st.save(s)
    assert st.get(s.id) is not None               # 完整 UUID
    assert st.get(s.id[:8]) is not None           # 8 位前缀
    assert st.get(s.id[:8]).id == s.id


def test_get_prefers_exact_match(fake_home):
    """当存在两个共享前缀的快照时,精确 id 命中而非前缀误匹配。"""
    st = Store()
    a = _snap(title="aaa", created="2026-01-01T00:00:00+00:00")
    b = _snap(title="bbb", created="2026-02-01T00:00:00+00:00")
    st.save(a)
    st.save(b)
    # 即便 b 较新,精确 id 仍优先返回 a
    assert st.get(a.id).title == "aaa"


def test_get_handles_missing_snapshot_file(fake_home):
    """DB 记录在但快照文件被外部删除时,get/latest/list 不应抛 FileNotFoundError。"""
    from contextbridge.store import snapshots_dir
    st = Store()
    s = _snap(title="orphan")
    st.save(s)
    for f in snapshots_dir().glob("*.json"):
        f.unlink()
    assert st.get(s.id) is None                    # 文件缺失 -> None,不崩溃
    assert st.latest() is None
    assert st.list() == []

