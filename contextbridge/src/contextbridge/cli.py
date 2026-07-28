from __future__ import annotations
import json
import os
from pathlib import Path
import typer
from rich.console import Console
from rich.table import Table

from .adapters.claude_code import ClaudeCodeAdapter
from .gitutils import get_git_diff
from .schema import ConversationMessage, Snapshot, SourceInfo
from .store import Store
from .truncation import truncate_conversation, truncate_diff

app = typer.Typer(help="ContextBridge: cross-IDE context handoff", no_args_is_help=True)
console = Console()


def _build_snapshot(
    title: str | None,
    conversation_json: str | None,
    include_diff: bool,
) -> Snapshot:
    cwd = os.getcwd()
    # 显式传 --conversation 时优先用之（测试/脚本场景）；否则探测 Claude Code
    cc = ClaudeCodeAdapter()
    if conversation_json is None and cc.detect():
        msgs = cc.parse_session()
        ide = "claude_code"
    else:
        conv = json.loads(conversation_json) if conversation_json else []
        msgs = [ConversationMessage(**m) for m in conv]
        ide = "claude_code" if (conversation_json is None and cc.detect()) else "generic"

    msgs = truncate_conversation(msgs)
    raw_diff = get_git_diff(cwd) if include_diff else None
    diff = truncate_diff(raw_diff) if raw_diff else None

    return Snapshot(
        title=title,
        source=SourceInfo(ide=ide, cwd=cwd),
        conversation=msgs,
        git_diff=diff,
    )


@app.command()
def export(
    title: str = typer.Option(None, "--title", "-t"),
    conversation: str = typer.Option(None, "--conversation", "-c", help="JSON list of {role,content}"),
    no_diff: bool = typer.Option(False, "--no-diff"),
):
    """Snapshot current context. From a terminal with no Claude Code session,
    pass --conversation '[...]'."""
    snap = _build_snapshot(title, conversation, include_diff=not no_diff)
    Store().save(snap)
    console.print(f"[green]Snapshot saved[/green] id={snap.id} title={snap.title!r} ide={snap.source.ide}")


@app.command(name="list")
def list_(
    limit: int = typer.Option(20, "--limit", "-n"),
):
    snaps = Store().list(limit=limit)
    if not snaps:
        console.print("[yellow]No snapshots yet.[/yellow]")
        return
    tbl = Table("ID", "Title", "IDE", "Created")
    for s in snaps:
        tbl.add_row(s.id[:8], s.title, s.source.ide, s.created_at)
    console.print(tbl)


@app.command()
def show(id: str):
    s = Store().get(id)
    if not s:
        console.print(f"[red]Not found: {id}[/red]"); raise typer.Exit(1)
    console.print_json(s.model_dump_json())


@app.command(name="import")
def import_(
    id: str = typer.Argument(None),
):
    """Print the snapshot as a structured handoff block ready to paste into the next IDE."""
    s = Store().get(id) if id else Store().latest()
    if not s:
        console.print("[red]No snapshot available.[/red]"); raise typer.Exit(1)
    lines = [
        f"# Context Handoff — {s.title}",
        f"- source IDE: {s.source.ide}",
        f"- cwd: {s.source.cwd}",
        f"- created: {s.created_at}",
        "",
        "## Conversation so far",
    ]
    for m in s.conversation:
        lines.append(f"### {m.role}")
        lines.append(m.content)
        lines.append("")
    if s.git_diff:
        lines += ["## Current git diff", "```diff", s.git_diff, "```", ""]
    console.print("\n".join(lines))


@app.command()
def clear(
    days: int = typer.Argument(30),
):
    n = Store().delete_older_than(days=days)
    console.print(f"[green]Deleted {n} snapshot(s) older than {days} days.[/green]")


if __name__ == "__main__":
    app()
