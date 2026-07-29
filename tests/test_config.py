from pathlib import Path
from contextbridge.config import get_home, ensure_dirs, db_path, snapshots_dir, config_path


def test_paths_under_env(fake_home):
    ensure_dirs()
    assert db_path().parent == fake_home
    assert snapshots_dir().exists()
    assert config_path().parent == fake_home


def test_get_home_fallback(monkeypatch, tmp_path):
    monkeypatch.delenv("CONTEXTBRIDGE_HOME", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    h = get_home()
    assert h == Path(tmp_path) / ".contextbridge"
