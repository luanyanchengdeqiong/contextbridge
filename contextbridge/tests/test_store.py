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
