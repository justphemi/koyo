import os
import socket

import pytest
from starlette.testclient import TestClient
from typer.testing import CliRunner

from koyoapp import dev as dev_module
from koyoapp.app import build_app
from koyoapp.cli import app as cli_app
from koyoapp.router import clear_module_cache

from test_router import make_project

runner = CliRunner()


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


def test_is_project_root_detects_koyo_projects(tmp_path):
    from koyoapp.config import is_project_root

    assert not is_project_root(tmp_path)
    (tmp_path / "koyo.config.py").write_text("PORT = 2309\n", encoding="utf-8")
    assert is_project_root(tmp_path)

    other = tmp_path / "other"
    other.mkdir()
    (other / "app").mkdir()
    assert is_project_root(other)


def test_require_project_root_resolves_valid_directory(tmp_path):
    from koyoapp.config import require_project_root

    make_project(tmp_path)
    assert require_project_root(tmp_path) == tmp_path.resolve()


def test_require_project_root_raises_outside_project(tmp_path):
    from koyoapp.config import ProjectError, require_project_root

    with pytest.raises(ProjectError) as excinfo:
        require_project_root(tmp_path)
    message = str(excinfo.value)
    assert "not a Koyo project" in message
    assert "koyo.config.py" in message
    assert str(tmp_path.resolve()) in message


def test_run_dev_rejects_non_project_directory_without_side_effects(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(
        dev_module,
        "ensure_tailwind_present",
        lambda *args, **kwargs: calls.append("tailwind") or None,
    )
    monkeypatch.setattr(dev_module, "bump_token", lambda *args, **kwargs: calls.append("token"))

    with pytest.raises(dev_module.ProjectError):
        dev_module.run_dev(tmp_path)

    assert calls == []
    assert not (tmp_path / "app").exists()
    assert not (tmp_path / "public").exists()
    assert not (tmp_path / "styles").exists()
    assert not (tmp_path / ".koyo").exists()


def test_cli_dev_reports_error_outside_project(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(cli_app, ["dev"])

    assert result.exit_code == 1
    assert "error:" in result.output
    assert "not a Koyo project" in result.output
    assert "koyoapp create" in result.output


def test_existing_watch_paths_drops_missing_entries(tmp_path):
    keep_dir = tmp_path / "app"
    keep_dir.mkdir()
    keep_file = tmp_path / "koyo.config.py"
    keep_file.write_text("PORT = 2309\n", encoding="utf-8")
    watched = [
        keep_dir,
        tmp_path / "public",
        keep_file,
        tmp_path / "tailwind.config.js",
    ]

    assert dev_module._existing_watch_paths(watched) == [keep_dir, keep_file]


def test_run_dev_only_watches_paths_that_exist(tmp_path, monkeypatch):
    make_project(tmp_path)  # has no tailwind.config.js on purpose
    watched = {}
    monkeypatch.setattr(dev_module, "ensure_tailwind_present", lambda *args, **kwargs: None)
    monkeypatch.setattr(dev_module, "_spawn_server", lambda *args, **kwargs: None)
    monkeypatch.setattr(dev_module, "_wait_until_ready", lambda *args, **kwargs: 0.0)
    monkeypatch.setattr(dev_module.koyo_net, "detect_lan_ip", lambda: None)

    def fake_watch(*paths, **kwargs):
        watched["paths"] = paths
        raise KeyboardInterrupt

    monkeypatch.setattr(dev_module.watchfiles, "watch", fake_watch)

    dev_module.run_dev(tmp_path)

    assert watched["paths"]
    for path in watched["paths"]:
        assert path.exists()
    assert (tmp_path / "tailwind.config.js") not in watched["paths"]