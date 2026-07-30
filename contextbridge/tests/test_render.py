from contextbridge.schema import ConversationMessage, Snapshot, SourceInfo
from contextbridge.render import render_handoff


def _snap(title="t", role="user", content="hi", diff=None):
    return Snapshot(
        title=title,
        source=SourceInfo(ide="claude_code", cwd="/x"),
        conversation=[ConversationMessage(role=role, content=content)],
        git_diff=diff,
    )


def test_render_includes_header_and_messages():
    s = _snap(title="my snap", content="hello world")
    out = render_handoff(s)
    assert "# Context Handoff — my snap" in out
    assert "source IDE: claude_code" in out
    assert "cwd: /x" in out
    assert "## user" in out
    assert "hello world" in out


def test_render_appends_git_diff_block():
    s = _snap(diff="diff --git a/f b/f\n+new")
    out = render_handoff(s)
    assert "## Current git diff" in out
    assert "```diff" in out
    assert "+new" in out


def test_render_omits_diff_when_absent():
    s = _snap()
    assert "## Current git diff" not in render_handoff(s)


def test_render_includes_summary_when_distinct_from_title():
    s = Snapshot(
        title="short title",
        summary="a longer one-line description of the work",
        source=SourceInfo(ide="claude_code", cwd="/x"),
        conversation=[ConversationMessage(role="user", content="msg")],
    )
    out = render_handoff(s)
    assert "> a longer one-line description of the work" in out


def test_render_omits_summary_when_same_as_title():
    # 当 title 与 summary 同源(都取自首条 user 消息)时,不重复打印 summary 行
    s = _snap(title="hi", content="hi")
    out = render_handoff(s)
    # summary 自动生成 == "hi" == title,故不应出现引用行
    lines = [ln for ln in out.splitlines() if ln.startswith("> ")]
    assert lines == []
