import json
from contextbridge.adapters.codex import CodexAdapter


def _write_rollout(path, events):
    with path.open("w", encoding="utf-8") as f:
        for ev in events:
            f.write(json.dumps(ev) + "\n")


def test_parse_response_items(tmp_path, monkeypatch):
    """逐行解析 response_item,保留 user/assistant,developer->system,跳过 function_call。"""
    monkeypatch.setenv("CODEX_HOME", str(tmp_path))
    day = tmp_path / "sessions" / "2026" / "07" / "29"
    day.mkdir(parents=True)
    rollout = day / "rollout-2026-07-29T10-00-00-abc.jsonl"

    events = [
        {"type": "session_meta", "payload": {}},               # 噪音,跳过
        {"type": "response_item", "payload": {
            "type": "message", "role": "developer",
            "content": [{"type": "input_text", "text": "you are codex"}],
        }},
        {"type": "response_item", "payload": {
            "type": "message", "role": "user",
            "content": [{"type": "input_text", "text": "fix the bug"}],
        }},
        {"type": "response_item", "payload": {
            "type": "message", "role": "assistant",
            "content": [{"type": "text", "text": "done"}],
        }},
        {"type": "response_item", "payload": {                  # function_call,无 role,跳过
            "type": "function_call", "name": "shell", "arguments": "{}",
        }},
        {"type": "response_item", "payload": {                  # 纯字符串 content
            "type": "message", "role": "assistant", "content": "plain string",
        }},
    ]
    _write_rollout(rollout, events)

    a = CodexAdapter()
    assert a.detect() is True
    msgs = a.parse_session()
    assert [m.role for m in msgs] == ["system", "user", "assistant", "assistant"]
    assert msgs[0].content == "you are codex"   # developer -> system
    assert msgs[1].content == "fix the bug"
    assert msgs[3].content == "plain string"


def test_detect_when_absent(monkeypatch, tmp_path):
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "nope"))
    a = CodexAdapter()
    assert a.detect() is False
    assert a.parse_session() == []


def test_picks_most_recent_rollout(tmp_path, monkeypatch):
    import time
    monkeypatch.setenv("CODEX_HOME", str(tmp_path))
    day = tmp_path / "sessions" / "2026" / "07" / "29"
    day.mkdir(parents=True)
    _write_rollout(day / "rollout-old.jsonl", [
        {"type": "response_item", "payload": {"type": "message", "role": "user", "content": "OLD"}},
    ])
    time.sleep(0.05)
    _write_rollout(day / "rollout-new.jsonl", [
        {"type": "response_item", "payload": {"type": "message", "role": "user", "content": "NEW"}},
    ])
    a = CodexAdapter()
    msgs = a.parse_session()
    assert msgs[0].content == "NEW"
