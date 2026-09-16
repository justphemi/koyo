import koyoapp.build as build_module
from koyoapp.router import clear_module_cache

from test_router import make_project


def _no_tailwind(project_dir):
    return None


def test_build_prerenders_static_routes(tmp_path, monkeypatch):
    make_project(tmp_path)
    monkeypatch.setattr(build_module.tailwind, "ensure_tailwind_present", _no_tailwind)
    clear_module_cache()
    build_module.run_build(tmp_path)
    site = tmp_path / ".koyo" / "build" / "site"
    assert (site / "index.html").is_file()
    home = (site / "index.html").read_text(encoding="utf-8")
    assert "<!doctype html>" in home
    assert ">Home</h1>" in home
    assert (site / "about" / "index.html").is_file()
    assert (site / "blog" / "index.html").is_file()
    clear_module_cache()


def test_build_copies_public_next_to_pages(tmp_path, monkeypatch):
    make_project(tmp_path)
    monkeypatch.setattr(build_module.tailwind, "ensure_tailwind_present", _no_tailwind)
    clear_module_cache()
    build_module.run_build(tmp_path)
    site = tmp_path / ".koyo" / "build" / "site"
    assert (site / "favicon.ico").read_bytes() == b"fake-ico"
    clear_module_cache()


def test_build_skips_dynamic_routes_with_message(tmp_path, monkeypatch, capsys):
    make_project(tmp_path)
    monkeypatch.setattr(build_module.tailwind, "ensure_tailwind_present", _no_tailwind)
    clear_module_cache()
    build_module.run_build(tmp_path)
    output = capsys.readouterr().out
    assert "Skipped dynamic routes" in output
    assert "/blog/[slug]" in output
    site = tmp_path / ".koyo" / "build" / "site"
    assert not (site / "blog" / "[slug]").exists()
    assert not (site / "blog" / "index.html").parent.joinpath("[slug]").exists()
    clear_module_cache()