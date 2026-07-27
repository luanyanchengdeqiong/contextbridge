from __future__ import annotations
import os
from pathlib import Path


def get_home() -> Path:
    if env := os.environ.get("CONTEXTBRIDGE_HOME"):
        return Path(env)
    return Path(os.environ.get("HOME", os.path.expanduser("~"))) / ".contextbridge"


def ensure_dirs() -> None:
    snapshots_dir().mkdir(parents=True, exist_ok=True)
    get_home().mkdir(parents=True, exist_ok=True)


def db_path() -> Path:
    return get_home() / "index.db"


def snapshots_dir() -> Path:
    return get_home() / "snapshots"


def config_path() -> Path:
    return get_home() / "config.toml"
