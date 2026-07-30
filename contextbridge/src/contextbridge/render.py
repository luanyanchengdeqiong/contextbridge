from __future__ import annotations
from .schema import Snapshot


def render_handoff(s: Snapshot) -> str:
    """Render a snapshot as a Markdown handoff block.

    Shared by the CLI `import` command and the MCP `cb_import` tool so both
    surfaces emit identical output.
    """
    lines = [
        f"# Context Handoff — {s.title}",
        f"source IDE: {s.source.ide}  cwd: {s.source.cwd}  created: {s.created_at}",
        "",
    ]
    if s.summary and s.summary != s.title:
        lines += [f"> {s.summary}", ""]
    for m in s.conversation:
        lines.append(f"## {m.role}")
        lines.append(m.content or "")
        lines.append("")
    if s.git_diff:
        lines += ["## Current git diff", "```diff", s.git_diff, "```", ""]
    return "\n".join(lines).rstrip() + "\n"
