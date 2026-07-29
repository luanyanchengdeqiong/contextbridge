from contextbridge.schema import ConversationMessage
from contextbridge.truncation import truncate_conversation, truncate_diff


def _msg(role, n_chars=10):
    return ConversationMessage(role=role, content="x" * n_chars)


def test_short_kept_as_is():
    msgs = [_msg("user"), _msg("assistant")]
    assert truncate_conversation(msgs) == msgs


def test_long_drops_middle():
    msgs = [_msg("user", 5) for _ in range(40)]  # 40 轮 > 30
    out = truncate_conversation(msgs, keep_oldest=5, keep_recent=20)
    assert len(out) == 25
    assert out[:5] == msgs[:5]
    assert out[5:] == msgs[-20:]


def test_char_budget_trims_assistant_first():
    msgs = [
        ConversationMessage(role=("user" if i % 2 == 0 else "assistant"), content="y" * 20000)
        for i in range(6)
    ]
    out = truncate_conversation(msgs, max_chars=80000)
    assert sum(len(m.content) for m in out) <= 80000
    assert out[0].role == "user"


def test_diff_truncated():
    big = "a" * 60000
    out = truncate_diff(big, limit=50000)
    assert len(out) <= 50000
    assert "truncated" in out.lower()


def test_diff_kept():
    out = truncate_diff("small" * 10, limit=50000)
    assert out == "small" * 10
