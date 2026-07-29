import json
from contextbridge.adapters.zcode import ZCodeAdapter


def _write_transcript(path, events):
    with path.open("w", encoding="utf-8") as f:
        for ev in events:
            f.write(json.dumps(ev) + "\n")


def test_parse_picks_latest_model_request(tmp_path, monkeypatch):
    """应取最后一条 model_request 的 messages 快照,且只保留对话角色。"""
    monkeypatch.setenv("ZCODE_HOME", str(tmp_path))
    agents = tmp_path / "cli" / "agents" / "sess_1" / "agent_1"
    agents.mkdir(parents=True)
    transcript = agents / "transcript.jsonl"

    events = [
        # 第一条 model_request(较旧,应被覆盖)
        {"type": "model_request", "payload": {"messages": [
            {"role": "user", "content": "old question"},
        ]}},
        # 噪音事件,应被忽略
        {"type": "turn_started", "payload": {}},
        {"type": "tool_batch_complete", "payload": {}},
        # 最新 model_request —— 最终采用
        {"type": "model_request", "payload": {"messages": [
            {"role": "system", "content": "system prompt"},
            {"role": "user", "content": "new question"},
            {"role": "assistant", "content": [{"type": "text", "text": "answer"}]},
            {"role": "tool", "content": "tool output"},   # 非对话角色,应被跳过
        ]}},
    ]
    _write_transcript(transcript, events)

    a = ZCodeAdapter()
    assert a.detect() is True
    msgs = a.parse_session()
    # 只剩 system / user / assistant,tool 被过滤
    assert [m.role for m in msgs] == ["system", "user", "assistant"]
    assert msgs[1].content == "new question"
    assert msgs[2].content == "answer"   # 从 list 提取


def test_detect_when_absent(monkeypatch, tmp_path):
    monkeypatch.setenv("ZCODE_HOME", str(tmp_path / "nope"))
    a = ZCodeAdapter()
    assert a.detect() is False
    assert a.parse_session() == []


def test_picks_most_recent_session(tmp_path, monkeypatch):
    """多个 transcript 时,mtime 最新的胜出。"""
    import os, time
    monkeypatch.setenv("ZCODE_HOME", str(tmp_path))
    base = tmp_path / "cli" / "agents"
    old_dir = base / "sess_old" / "agent_1"; old_dir.mkdir(parents=True)
    new_dir = base / "sess_new" / "agent_1"; new_dir.mkdir(parents=True)
    _write_transcript(old_dir / "transcript.jsonl", [
        {"type": "model_request", "payload": {"messages": [{"role": "user", "content": "OLD"}]}},
    ])
    time.sleep(0.05)
    _write_transcript(new_dir / "transcript.jsonl", [
        {"type": "model_request", "payload": {"messages": [{"role": "user", "content": "NEW"}]}},
    ])
    a = ZCodeAdapter()
    msgs = a.parse_session()
    assert msgs[0].content == "NEW"
