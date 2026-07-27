from __future__ import annotations
from .schema import ConversationMessage

DEFAULT_MAX_TURNS = 30
DEFAULT_KEEP_OLDEST = 5
DEFAULT_KEEP_RECENT = 20
DEFAULT_MAX_CHARS = 80000  # ~20k token
DEFAULT_DIFF_LIMIT = 50000


def truncate_conversation(
    msgs: list[ConversationMessage],
    max_turns: int = DEFAULT_MAX_TURNS,
    keep_oldest: int = DEFAULT_KEEP_OLDEST,
    keep_recent: int = DEFAULT_KEEP_RECENT,
    max_chars: int = DEFAULT_MAX_CHARS,
) -> list[ConversationMessage]:
    # 第一道：按轮数裁
    if len(msgs) > max_turns:
        msgs = msgs[:keep_oldest] + msgs[-keep_recent:]

    # 第二道：按字符总量裁（优先砍 assistant 长内容）
    def total() -> int:
        return sum(len(m.content) for m in msgs)

    while total() > max_chars and len(msgs) > 1:
        target_idx = None
        for i in range(1, len(msgs) - 1):
            if msgs[i].role == "assistant":
                if target_idx is None or len(msgs[i].content) > len(msgs[target_idx].content):
                    target_idx = i
        if target_idx is None:
            target_idx = len(msgs) // 2
        msgs = msgs[:target_idx] + msgs[target_idx + 1:]
    return msgs


def truncate_diff(diff: str, limit: int = DEFAULT_DIFF_LIMIT) -> str:
    if len(diff) <= limit:
        return diff
    keep = limit - 200
    suffix = f"\n\n(... truncated, +{len(diff) - keep} chars ...)"
    return diff[:keep] + suffix
