from __future__ import annotations
from typing import Optional
from mcp.server.fastmcp import FastMCP
from mcp.types import CallToolResult, TextContent

from .cli import _build_snapshot   # 复用 CLI 的快照构造逻辑
from .render import render_handoff
from .store import Store

mcp = FastMCP("contextbridge")


def cb_export_impl(
    title: Optional[str] = None,
    conversation: Optional[list[dict]] = None,
    include_diff: bool = True,
) -> str:
    conv_json = None
    if conversation is not None:
        import json
        conv_json = json.dumps(conversation)
    snap = _build_snapshot(title, conv_json, include_diff=include_diff)
    Store().save(snap)
    return f"Snapshot saved — id={snap.id} title={snap.title!r} ide={snap.source.ide} turns={len(snap.conversation)}"


def cb_list_impl(limit: int = 20) -> str:
    snaps = Store().list(limit=limit)
    if not snaps:
        return "No snapshots yet. Run cb_export first."
    lines = [f"- {s.id[:8]} | {s.source.ide:<12} | {s.created_at} | {s.title}" for s in snaps]
    return "ContextBridge snapshots (newest first):\n" + "\n".join(lines)


def cb_import_impl(id: Optional[str] = None) -> str:
    s = Store().get(id) if id else Store().latest()
    if not s:
        return "No snapshot available."
    return render_handoff(s)


def cb_clear_impl(older_than_days: int = 30) -> str:
    n = Store().delete_older_than(days=older_than_days)
    return f"Deleted {n} snapshot(s) older than {older_than_days} days."


@mcp.tool()
def cb_export(
    title: Optional[str] = None,
    conversation: Optional[list[dict]] = None,
    include_diff: bool = True,
) -> CallToolResult:
    """Export current context as a snapshot.

    If running inside Claude Code / Codex CLI, the conversation is auto-collected
    from the local session file. Otherwise pass `conversation` as a list of
    {role, content} dicts (e.g. AI invoking this tool from Cursor).

    Returns CallToolResult directly so FastMCP does not synthesize a
    structuredContent field (suspected to confuse some MCP clients).
    """
    msg = cb_export_impl(title, conversation, include_diff)
    return CallToolResult(content=[TextContent(type="text", text=msg)], isError=False)


@mcp.tool()
def cb_list(limit: int = 20) -> str:
    """List saved snapshots."""
    return cb_list_impl(limit)


@mcp.tool()
def cb_import(id: Optional[str] = None) -> str:
    """Import a snapshot by id; omit id to use the latest. Returns a structured
    handoff block to insert into the next IDE's conversation."""
    return cb_import_impl(id)


@mcp.tool()
def cb_clear(older_than_days: int = 30) -> str:
    """Delete snapshots older than N days."""
    return cb_clear_impl(older_than_days)


if __name__ == "__main__":
    mcp.run(transport="stdio")
