from starlette.testclient import TestClient

from koyoapp.app import build_app
from koyoapp.router import (
    RouteError,
    clear_module_cache,
    render_route,
    scan_app_dir,
)

META_ROOT_LAYOUT = '''\
from koyoapp.html import body, head, html, meta
from koyoapp.meta import metadata_tags

metadata = {"title": "Root Title", "description": "Root Description"}

def layout(children):
    return html(lang="en")[
        head()[meta(charset="utf-8"), *metadata_tags()],
        body(class_="layout")[children],
    ]
'''

META_BLOG_LAYOUT = '''\
from koyoapp.html import div

metadata = {
    "description": "Blog Description",
    "og_image": "/blog-og.png",
}

def layout(children):
    return div(class_="blog")[children]
'''

META_HOME_PAGE = '''\
from koyoapp.html import p

metadata = {"title": "Page Title"}

def page():
    return p()["home"]
'''

META_PLAIN_PAGE = '''\
from koyoapp.html import p

def page():
    return p()["plain"]
'''

BROKEN_PAGE = '''\
from koyoapp.html import p

def page():
    raise RuntimeError("boom from page")
'''

ROOT_LAYOUT = '''\
from koyoapp.html import body, head, html, meta, title

def layout(children):
    return html(lang="en")[
        head()[meta(charset="utf-8"), title()["Test App"]],
        body()[children],
    ]
'''

HOME = '''\
from koyoapp.html import h1

def page():
    return h1()["Home"]
'''

ABOUT = '''\
from koyoapp.html import h1

def page():
    return h1()["About"]
'''

BLOG_LAYOUT = '''\
from koyoapp.html import div, h1

def layout(children):
    return div(class_="blog")[h1()["Blog heading"], children]
'''

BLOG_INDEX = '''\
from koyoapp.html import p

def page():
    return p()["Blog index"]
'''

BLOG_POST = '''\
from koyoapp.html import p

def page(slug: str):
    return p()[f"post:{slug}"]
'''

MISSING_PAGE_FN = '''\
from koyoapp.html import p

def not_a_page():
    return p()["oops"]
'''


def write(path, content):
    path.write_text(content, encoding="utf-8")


def make_project(root):
    (root / "public").mkdir(parents=True)
    (root / "styles").mkdir(parents=True)
    (root / "public" / "favicon.ico").write_bytes(b"fake-ico")
    app = root / "app"
    (app / "about").mkdir(parents=True)
    (app / "blog" / "[slug]").mkdir(parents=True)
    write(app / "layout.py", ROOT_LAYOUT)
    write(app / "page.py", HOME)
    write(app / "about" / "page.py", ABOUT)
    write(app / "blog" / "layout.py", BLOG_LAYOUT)
    write(app / "blog" / "page.py", BLOG_INDEX)
    write(app / "blog" / "[slug]" / "page.py", BLOG_POST)
    write(root / "koyo.config.py", "PORT = 2399\n")


def test_scan_builds_wildcard_paths(tmp_path):
    make_project(tmp_path)
    clear_module_cache()
    entries = scan_app_dir(tmp_path / "app")
    paths = sorted(entry.path for entry in entries)
    assert paths == ["/", "/about", "/blog", "/blog/{slug}"]


def test_render_dynamic_route_with_nested_layouts(tmp_path):
    make_project(tmp_path)
    clear_module_cache()
    entries = scan_app_dir(tmp_path / "app")
    post = next(entry for entry in entries if entry.path == "/blog/{slug}")
    rendered = render_route(post, {"slug": "hello"})
    assert rendered.startswith("<!doctype html>")
    assert "<title>Test App</title>" in rendered
    assert "Blog heading" in rendered
    assert "post:hello" in rendered


def test_render_root_page(tmp_path):
    make_project(tmp_path)
    clear_module_cache()
    entries = scan_app_dir(tmp_path / "app")
    home = next(entry for entry in entries if entry.path == "/")
    rendered = render_route(home, {})
    assert ">Home</h1>" in rendered
    assert "Blog heading" not in rendered


def test_missing_page_function_raises_route_error(tmp_path):
    make_project(tmp_path)
    (tmp_path / "app" / "bad").mkdir(parents=True)
    write(tmp_path / "app" / "bad" / "page.py", MISSING_PAGE_FN)
    clear_module_cache()
    entries = scan_app_dir(tmp_path / "app")
    bad = next(entry for entry in entries if entry.path == "/bad")
    try:
        render_route(bad, {})
    except RouteError:
        pass
    else:
        raise AssertionError("expected RouteError")


def test_http_endpoints(tmp_path):
    make_project(tmp_path)
    clear_module_cache()
    app = build_app(tmp_path)
    with TestClient(app) as client:
        response = client.get("/")
        assert response.status_code == 200
        assert "<!doctype html>" in response.text
        assert ">Home</h1>" in response.text

        response = client.get("/about")
        assert response.status_code == 200
        assert "About" in response.text

        response = client.get("/blog/hello-world")
        assert response.status_code == 200
        assert "post:hello-world" in response.text

        response = client.get("/missing-page")
        assert response.status_code == 404
        assert "Not Found" in response.text
        assert "There is no route or public file" in response.text

        response = client.get("/favicon.ico")
        assert response.status_code == 200
        assert response.content == b"fake-ico"
    clear_module_cache()


def test_static_styles_are_served(tmp_path):
    make_project(tmp_path)
    (tmp_path / "styles" / "extra.css").write_text("body { color: red; }", encoding="utf-8")
    clear_module_cache()
    app = build_app(tmp_path)
    with TestClient(app) as client:
        response = client.get("/styles/extra.css")
        assert response.status_code == 200
        assert response.text == "body { color: red; }"
    clear_module_cache()


def test_pages_can_import_components_absolutely(tmp_path, monkeypatch):
    (tmp_path / "app").mkdir(parents=True)
    (tmp_path / "components").mkdir()
    (tmp_path / "public").mkdir()
    (tmp_path / "styles").mkdir()
    write(tmp_path / "app" / "layout.py", ROOT_LAYOUT)
    write(
        tmp_path / "components" / "site.py",
        "from koyoapp.html import p\n\n"
        "def site_footer():\n"
        '    return p()["COMPONENT_RENDERED"]\n',
    )
    write(
        tmp_path / "app" / "page.py",
        "from koyoapp.html import div\n"
        "from components.site import site_footer\n\n"
        "def page():\n"
        '    return div()["card", site_footer()]\n',
    )
    monkeypatch.chdir("/")
    clear_module_cache()
    app = build_app(tmp_path)
    with TestClient(app) as client:
        assert "COMPONENT_RENDERED" in client.get("/").text
    clear_module_cache()


def test_page_metadata_wins_over_root(tmp_path):
    (tmp_path / "app").mkdir(parents=True)
    write(tmp_path / "app" / "layout.py", META_ROOT_LAYOUT)
    write(tmp_path / "app" / "page.py", META_HOME_PAGE)
    clear_module_cache()
    entries = scan_app_dir(tmp_path / "app")
    rendered = render_route(entries[0], {})
    assert "<title>Page Title</title>" in rendered
    assert "Root Title" not in rendered
    assert '<meta name="description" content="Root Description">' in rendered
    clear_module_cache()


def test_page_without_metadata_uses_root_defaults(tmp_path):
    (tmp_path / "app").mkdir(parents=True)
    write(tmp_path / "app" / "layout.py", META_ROOT_LAYOUT)
    write(tmp_path / "app" / "page.py", META_PLAIN_PAGE)
    clear_module_cache()
    entries = scan_app_dir(tmp_path / "app")
    rendered = render_route(entries[0], {})
    assert "<title>Root Title</title>" in rendered
    assert '<meta name="description" content="Root Description">' in rendered
    clear_module_cache()


def test_nested_layouts_merge_metadata_key_by_key(tmp_path):
    app = tmp_path / "app"
    (app / "blog").mkdir(parents=True)
    write(app / "layout.py", META_ROOT_LAYOUT)
    write(app / "blog" / "layout.py", META_BLOG_LAYOUT)
    write(app / "blog" / "page.py", META_PLAIN_PAGE)
    clear_module_cache()
    entries = scan_app_dir(app)
    rendered = render_route(next(e for e in entries if e.path == "/blog"), {})
    assert "<title>Root Title</title>" in rendered
    assert '<meta name="description" content="Blog Description">' in rendered
    assert '<meta property="og:image" content="/blog-og.png">' in rendered
    clear_module_cache()


def test_root_defaults_apply_when_nothing_specific_is_set(tmp_path):
    (tmp_path / "app").mkdir(parents=True)
    write(tmp_path / "app" / "layout.py", META_ROOT_LAYOUT)
    write(tmp_path / "app" / "page.py", META_PLAIN_PAGE)
    clear_module_cache()
    app = build_app(tmp_path)
    with TestClient(app) as client:
        body_text = client.get("/").text
        assert "<title>Root Title</title>" in body_text
        assert "Root Description" in body_text
    clear_module_cache()


def test_fragment_endpoint_returns_fragment_only(tmp_path):
    (tmp_path / "app").mkdir(parents=True)
    write(tmp_path / "app" / "layout.py", ROOT_LAYOUT)
    write(
        tmp_path / "app" / "page.py",
        "from koyoapp.html import div, p\n\n"
        "def page():\n"
        '    return div()["PAGE"]\n\n'
        'def fragment():\n'
        '    return p()["FRAG"]\n',
    )
    clear_module_cache()
    app = build_app(tmp_path)
    with TestClient(app) as client:
        full = client.get("/")
        assert full.status_code == 200
        assert "PAGE" in full.text
        assert "<html" in full.text
        frag = client.get("/", headers={"HX-Request": "true"})
        assert frag.status_code == 200
        assert "FRAG" in frag.text
        assert "PAGE" not in frag.text
        assert "<html" not in frag.text
        assert "Test App" not in frag.text
    clear_module_cache()


def test_fragment_only_route_always_returns_fragment(tmp_path):
    (tmp_path / "app").mkdir(parents=True)
    write(tmp_path / "app" / "layout.py", ROOT_LAYOUT)
    write(
        tmp_path / "app" / "page.py",
        "from koyoapp.html import p\n\n"
        'def fragment():\n'
        '    return p()["only-fragment"]\n',
    )
    clear_module_cache()
    app = build_app(tmp_path)
    with TestClient(app) as client:
        response = client.get("/")
        assert response.status_code == 200
        assert "only-fragment" in response.text
        assert "<html" not in response.text
        assert "Test App" not in response.text
    clear_module_cache()


def test_dev_mode_error_page_shows_exception(tmp_path, monkeypatch):
    (tmp_path / "app").mkdir(parents=True)
    write(tmp_path / "app" / "layout.py", ROOT_LAYOUT)
    write(tmp_path / "app" / "page.py", BROKEN_PAGE)
    monkeypatch.setenv("KOYO_DEV", "1")
    clear_module_cache()
    app = build_app(tmp_path)
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/")
        assert response.status_code == 500
        assert "boom from page" in response.text
        assert "RuntimeError" in response.text
        assert "pre" in response.text
    clear_module_cache()


def test_non_dev_mode_error_hides_traceback(tmp_path, monkeypatch):
    (tmp_path / "app").mkdir(parents=True)
    write(tmp_path / "app" / "layout.py", ROOT_LAYOUT)
    write(tmp_path / "app" / "page.py", BROKEN_PAGE)
    monkeypatch.delenv("KOYO_DEV", raising=False)
    clear_module_cache()
    app = build_app(tmp_path)
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/")
        assert response.status_code == 500
        assert "boom from page" not in response.text
        assert "RuntimeError" not in response.text
        assert "Internal Server Error" in response.text
    clear_module_cache()