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
    st1._conn.close()
    db_path().unlink()
    st2 = Store()
    rebuilt = st2.get(s.id)
    assert rebuilt is not None
    assert rebuilt.title == "persisted"
    assert any(x.id == s.id for x in st2.list(limit=10))
    assert any(x.id == s.id for x in st2.search("persisted"))
