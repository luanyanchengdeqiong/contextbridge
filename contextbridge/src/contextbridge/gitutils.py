from __future__ import annotations
import os
import subprocess


def _windows_safe_kwargs() -> dict:
    """Prevent git subprocesses from inheriting the parent's pipe handles.

    On Windows, an MCP stdio server runs with its stdin/stdout/stderr wired to
    pipes. If a child process (git, and anything it spawns — e.g. a pager or
    credential helper) inherits those handles, communicate() blocks until every
    inherited write end closes, which looks like a 30s hang. Redirecting stdin
    to DEVNULL and passing STARTUPINFO keeps the child off our pipes.
    """
    kw: dict = {"stdin": subprocess.DEVNULL}
    if os.name == "nt":
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        kw["startupinfo"] = si
    return kw


def get_git_diff(cwd: str) -> str | None:
    """Return combined diff of tracked files vs HEAD (staged + unstaged). None if not a repo."""
    safe = _windows_safe_kwargs()
    try:
        rev = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=cwd, capture_output=True, text=True, timeout=5, **safe,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if rev.returncode != 0 or rev.stdout.strip() != "true":
        return None

    r = subprocess.run(
        ["git", "diff", "HEAD"],
        cwd=cwd, capture_output=True, text=True, timeout=10, **safe,
    )
    return r.stdout if r.stdout else ""
