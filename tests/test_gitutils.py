import subprocess
from pathlib import Path
from contextbridge.gitutils import get_git_diff


def test_diff_in_repo(tmp_path):
    repo = tmp_path / "r"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)
    (repo / "a.txt").write_text("hello\n")
    subprocess.run(["git", "add", "a.txt"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=repo, check=True)
    (repo / "a.txt").write_text("hello world\n")
    diff = get_git_diff(str(repo))
    assert "hello world" in diff
    assert diff.startswith("diff --git") or "+hello world" in diff


def test_not_a_repo_returns_none(tmp_path):
    assert get_git_diff(str(tmp_path)) is None


def test_staged_changes_not_duplicated(tmp_path):
    repo = tmp_path / "r"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)
    (repo / "a.txt").write_text("init\n")
    subprocess.run(["git", "add", "a.txt"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=repo, check=True)
    (repo / "a.txt").write_text("staged + unstaged\n")
    subprocess.run(["git", "add", "a.txt"], cwd=repo, check=True)
    (repo / "a.txt").write_text("staged + unstaged + more\n")
    diff = get_git_diff(str(repo))
    assert diff.count("staged + unstaged") == 1
