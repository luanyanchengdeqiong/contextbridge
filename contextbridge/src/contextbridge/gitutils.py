from __future__ import annotations
import subprocess


def get_git_diff(cwd: str) -> str | None:
    """Return combined diff of tracked files vs HEAD (staged + unstaged). None if not a repo."""
    try:
        rev = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=cwd, capture_output=True, text=True, timeout=5,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if rev.returncode != 0 or rev.stdout.strip() != "true":
        return None

    r = subprocess.run(["git", "diff", "HEAD"], cwd=cwd, capture_output=True, text=True, timeout=10)
    return r.stdout if r.stdout else ""
