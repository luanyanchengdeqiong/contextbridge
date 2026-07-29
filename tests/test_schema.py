import json
from contextbridge.schema import Snapshot, ConversationMessage, SourceInfo


def test_message_minimal():
    m = ConversationMessage(role="user", content="hi")
    assert m.role == "user"
    assert m.content == "hi"
    assert m.tool_calls is None


def test_snapshot_roundtrip_and_defaults(tmp_path):
    s = Snapshot(
        source=SourceInfo(ide="claude_code", version="1", cwd="/x"),
        conversation=[ConversationMessage(role="user", content="hello")],
    )
    assert s.version == "1.0"
    assert s.id and len(s.id) == 36  # uuid4
    assert s.title  # 默认从前 60 字生成
    s2 = Snapshot.model_validate_json(s.model_dump_json())
    assert s2.id == s.id
