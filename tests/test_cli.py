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
    # 强制走 Generic 路径：避免 Claude Code config dir 误命中真实 HOME
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path / "nohome"))  # 一个一定没有 .claude/projects 的目录
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
    from contextbridge.store import Store
    from contextbridge.schema import Snapshot, SourceInfo, ConversationMessage
    s = Snapshot(source=SourceInfo(ide="generic", cwd="/"),
                 conversation=[ConversationMessage(role="user", content="old")],
                 created_at="2020-01-01T00:00:00+00:00")
    Store().save(s)
    res = runner.invoke(app, ["clear", "30"])
    assert res.exit_code == 0
    assert "Deleted 1" in res.stdout
