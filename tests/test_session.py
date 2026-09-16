import re
import time

from starlette.testclient import TestClient

from koyoapp import templates
from koyoapp.app import build_app
from koyoapp.router import clear_module_cache
from koyoapp.session import SessionStore


def make_scaffold(root):
    for relpath, content in templates.FILES.items():
        path = root / relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content.replace("__PROJECT_NAME__", "demo"), encoding="utf-8")
    return root


def action_url(html_text):
    match = re.search(r'hx-post="(/__koyo_state/[^"]+)"', html_text)
    assert match is not None, "no state action found"
    return match.group(1).replace("&amp;", "&")


def test_use_state_starts_at_initial(tmp_path):
    make_scaffold(tmp_path)
    clear_module_cache()
    app = build_app(tmp_path)
    with TestClient(app) as client:
        page = client.get("/")
        assert page.status_code == 200
        assert "Visits: 0" in page.text
        assert "__koyo_state" in page.text
    clear_module_cache()


def test_use_state_increment_persists_across_requests(tmp_path):
    make_scaffold(tmp_path)
    clear_module_cache()
    app = build_app(tmp_path)
    with TestClient(app) as client:
        url = action_url(client.get("/").text)
        assert url.startswith("/__koyo_state/")
        response = client.post(url)
        assert response.status_code == 200
        assert "Visits: 1" in response.text
        assert "Visits: 1" in client.get("/").text
    clear_module_cache()


def test_use_state_two_sessions_are_independent(tmp_path):
    make_scaffold(tmp_path)
    clear_module_cache()
    app = build_app(tmp_path)
    with TestClient(app) as client_a:
        first_home = client_a.get("/").text
        assert "Visits: 0" in first_home
        with TestClient(app) as client_b:
            assert "Visits: 0" in client_b.get("/").text
        client_a.post(action_url(first_home))
        with TestClient(app) as client_c:
            assert "Visits: 0" in client_c.get("/").text
        assert "Visits: 1" in client_a.get("/").text
    clear_module_cache()


def test_use_state_build_falls_back_to_initial(tmp_path, monkeypatch):
    from koyoapp import build as build_module

    make_scaffold(tmp_path)
    monkeypatch.setattr(build_module.tailwind, "ensure_tailwind_present", lambda project_dir: None)
    clear_module_cache()
    build_module.run_build(tmp_path)
    built = tmp_path / ".koyo" / "build" / "site" / "index.html"
    page = built.read_text(encoding="utf-8")
    assert "Visits: 0" in page
    assert "__koyo_state" not in page
    clear_module_cache()


def test_session_idle_timeout_resets_values(tmp_path):
    from koyoapp import session as session_module

    make_scaffold(tmp_path)
    clear_module_cache()
    session_module.store = SessionStore(timeout=0.05)
    app = build_app(tmp_path)
    with TestClient(app) as client:
        url = action_url(client.get("/").text)
        client.post(url)
        assert "Visits: 1" in client.get("/").text
        time.sleep(0.15)
        assert "Visits: 0" in client.get("/").text
    clear_module_cache()