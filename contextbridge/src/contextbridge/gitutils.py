from __future__ import annotations
import subprocess


def get_git_diff(cwd: str) -> str | None:
    """Return combined unstaged + staged diff of tracked files. None if not a repo."""
    try:
        rev = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=cwd, capture_output=True, text=True, timeout=5,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if rev.returncode != 0 or rev.stdout.strip() != "true":
        return None

    parts: list[str] = []
    for args in (["git", "diff", "HEAD"], ["git", "diff", "--cached"]):
        r = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=10)
        if r.stdout:
            parts.append(r.stdout)
    return "\n".join(parts) if parts else ""
