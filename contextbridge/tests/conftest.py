import os
import pytest


@pytest.fixture
def fake_home(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("CONTEXTBRIDGE_HOME", str(home))
    return home
