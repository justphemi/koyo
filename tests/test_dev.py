import os

from starlette.testclient import TestClient

from koyoapp import dev as dev_module
from koyoapp.app import build_app
from koyoapp.router import clear_module_cache

from test_router import make_project


def test_default_host_is_ipv4_all_interfaces():
    assert dev_module.DEFAULT_HOST == "0.0.0.0"


class _FakeProc:
    def poll(self):
        return None


def test_dev_server_spawn_sets_pycache_prefix(tmp_path, monkeypatch):
    captured = {}
    monkeypatch.setattr(dev_module.time, "sleep", lambda _: None)

    def fake_popen(command, cwd=None, env=None, **kwargs):
        captured["command"] = command
        captured["cwd"] = cwd
        captured["env"] = env
        return _FakeProc()

    monkeypatch.setattr(dev_module.subprocess, "Popen", fake_popen)

    dev_module._spawn_server(tmp_path, 2399)

    prefix = str((tmp_path / ".koyo" / "pycache").resolve())
    assert captured["env"]["PYTHONPYCACHEPREFIX"] == prefix
    assert (tmp_path / ".koyo" / "pycache").is_dir()
    assert captured["cwd"] == str(tmp_path.resolve())
    assert "-m" in captured["command"]
    assert "uvicorn" in captured["command"]


def test_pycache_prefix_keeps_app_imports_clean(tmp_path):
    from koyoapp.reload import apply_pycache_prefix

    make_project(tmp_path)
    apply_pycache_prefix(tmp_path)
    clear_module_cache()
    app = build_app(tmp_path)
    with TestClient(app) as client:
        assert client.get("/").status_code == 200
        assert client.get("/about").status_code == 200
    assert not list((tmp_path / "app").rglob("__pycache__"))
    assert list((tmp_path / ".koyo" / "pycache").rglob("*.pyc"))
    clear_module_cache()


def test_with_pycache_env(tmp_path):
    from koyoapp.reload import with_pycache_env

    env = {"KOYO_DEV": "1"}
    out = with_pycache_env(env, tmp_path)
    assert out["PYTHONPYCACHEPREFIX"] == str((tmp_path / ".koyo" / "pycache").resolve())
    assert (tmp_path / ".koyo" / "pycache").is_dir()


def test_print_startup_shows_local_and_network(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(dev_module.koyo_net, "detect_lan_ip", lambda: "192.168.1.42")

    dev_module._print_startup(2309, 340)

    out = capsys.readouterr().out
    lines = [line.strip() for line in out.splitlines() if line.strip()]
    assert lines[0] == "Koyo dev server"
    assert "Local    http://localhost:2309" in out
    assert "Network  http://192.168.1.42:2309" in out
    assert "Ready in 340ms" in out


def test_print_startup_without_lan_shows_local_only(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(dev_module.koyo_net, "detect_lan_ip", lambda: None)

    dev_module._print_startup(2309, 12)

    out = capsys.readouterr().out
    assert "Local    http://localhost:2309" in out
    assert "Network" not in out