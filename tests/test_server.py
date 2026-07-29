from contextbridge.server import cb_export_impl, cb_list_impl, cb_import_impl, cb_clear_impl


def test_export_and_list(fake_home, monkeypatch, tmp_path):
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path / "nohome"))
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
    monkeypatch.setenv("HOME", str(tmp_path / "nohome"))
    monkeypatch.chdir(tmp_path)
    cb_export_impl(conversation=[{"role": "user", "content": "step one"}], include_diff=False)
    out = cb_import_impl()
    assert "Context Handoff" in out
    assert "step one" in out


def test_clear_reports_count(fake_home, monkeypatch, tmp_path):
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path / "nohome"))
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
