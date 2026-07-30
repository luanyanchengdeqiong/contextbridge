import os
import pytest

from contextbridge.store import Store


@pytest.fixture
def fake_home(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("CONTEXTBRIDGE_HOME", str(home))
    # 单例连接可能指向上一个测试的临时目录,这里重置让下一个 Store() 重新初始化
    Store.reset_connection()
    return home
