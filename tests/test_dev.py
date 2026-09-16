import os
import socket

import pytest

from starlette.testclient import TestClient

from koyoapp import dev as dev_module
from koyoapp.app import build_app
from koyoapp.router import clear_module_cache

from test_router import make_project


def test_default_host_is_ipv4_all_interfaces():
    assert dev_module.DEFAULT_HOST == "0.0.0.0"


def test_resolve_free_port_returns_same_when_free():
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    try:
        assert dev_module.resolve_free_port(port) == port
    finally:
        sock.close()


def test_resolve_free_port_steps_up_when_busy():
    with socket.socket() as busy:
        busy.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        busy.bind(("127.0.0.1", 0))
        busy.listen(1)
        base = busy.getsockname()[1]

        resolved = dev_module.resolve_free_port(base)
        assert resolved != base
        assert resolved > base
        assert not dev_module._port_in_use(resolved, "127.0.0.1", 0.3)


def test_live_reload_js_bundles_morphdom_and_poll_logic():
    from koyoapp.reload import live_reload_js

    js = live_reload_js()
    assert "morphdom" in js
    assert "__koyo-reload" in js
    assert "location.reload" not in js


def test_inject_dev_reload_references_live_script(tmp_path, monkeypatch):
    from koyoapp.reload import LIVE_RELOAD_URL, inject_dev_reload

    monkeypatch.setenv("KOYO_DEV", "1")
    out = inject_dev_reload("<html><body><h1>Hi</h1></body></html>")
    assert LIVE_RELOAD_URL in out
    assert out.index(LIVE_RELOAD_URL) < out.index("</body>")

    monkeypatch.delenv("KOYO_DEV", raising=False)
    out = inject_dev_reload("<html><body><h1>Hi</h1></body></html>")
    assert LIVE_RELOAD_URL not in out


def test_live_reload_route_serves_js_in_dev_only(tmp_path, monkeypatch):
    from koyoapp.reload import LIVE_RELOAD_URL
    from koyoapp.router import clear_module_cache

    make_project(tmp_path)
    clear_module_cache()
    monkeypatch.setenv("KOYO_DEV", "1")
    app = build_app(tmp_path)
    with TestClient(app) as client:
        response = client.get(LIVE_RELOAD_URL)
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/javascript")
        assert "morphdom" in response.text
    clear_module_cache()
    monkeypatch.delenv("KOYO_DEV", raising=False)
    app = build_app(tmp_path)
    with TestClient(app) as client:
        assert client.get(LIVE_RELOAD_URL).status_code == 404
    clear_module_cache()


def test_dev_mode_injects_live_reload_script_into_pages(tmp_path, monkeypatch):
    from koyoapp.reload import LIVE_RELOAD_URL
    from koyoapp.router import clear_module_cache

    make_project(tmp_path)
    clear_module_cache()
    monkeypatch.setenv("KOYO_DEV", "1")
    app = build_app(tmp_path)
    with TestClient(app) as client:
        response = client.get("/")
        assert response.status_code == 200
        assert f'src="{LIVE_RELOAD_URL}"' in response.text
    clear_module_cache()


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
    assert lines[0] == "*   *  *****  *   *  *****"
    assert "Koyo dev server" in out
    assert "Local    http://localhost:2309" in out
    assert "Network  http://192.168.1.42:2309" in out
    assert "Ready in 340ms" in out


def test_print_startup_without_lan_shows_local_only(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(dev_module.koyo_net, "detect_lan_ip", lambda: None)

    dev_module._print_startup(2309, 12)

    out = capsys.readouterr().out
    assert "Local    http://localhost:2309" in out
    assert "Network" not in out