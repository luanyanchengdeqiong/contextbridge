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
