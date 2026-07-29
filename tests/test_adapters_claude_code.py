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
    assert "renaming" in msgs[1].content


def test_detect_when_env_present(monkeypatch, tmp_path):
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path))
    (tmp_path / "projects").mkdir()
    a = ClaudeCodeAdapter()
    assert a.detect() is True


def test_detect_when_no_config(monkeypatch):
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    monkeypatch.setenv("HOME", "/nonexistent-path-xyz")
    a = ClaudeCodeAdapter()
    assert a.detect() is False
