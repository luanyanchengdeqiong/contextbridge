from contextbridge.adapters.generic import GenericAdapter
from contextbridge.adapters.base import ConversationMessage


def test_generic_uses_explicit_messages():
    a = GenericAdapter()
    msgs = a.parse(conversation=[
        {"role": "user", "content": "do X"},
        {"role": "assistant", "content": "ok"},
    ])
    assert len(msgs) == 2
    assert msgs[0].content == "do X"


def test_detect_always_true():
    assert GenericAdapter().detect() is True
