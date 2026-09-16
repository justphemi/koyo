"""Production build for Koyo: prerender static routes into .koyo/build.

The build output lives under .koyo/build, because .koyo is already the
hidden tooling directory for the dev token and bytecode cache and is
gitignored. The static site itself, ready for any static file host, is
written to .koyo/build/site. Compiled CSS lands at
.koyo/build/site/styles/koyo.css so the prerendered pages link correctly.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

from . import tailwind
from .deps import ensure_project_dir
from .reload import apply_pycache_prefix
from .router import render_route, scan_app_dir

BUILD_DIR = ".koyo/build"
SITE_DIR = "site"
CSS_OUTPUT = "styles/koyo.css"


def _copy_dir(src: Path, dest: Path) -> None:
    if src.is_dir():
        shutil.copytree(src, dest, dirs_exist_ok=True)


def _route_output_path(site_root: Path, path: str) -> Path:
    if path == "/":
        return site_root / "index.html"
    return site_root / path.lstrip("/") / "index.html"


def _pretty_path(path: str) -> str:
    return path.replace("{", "[").replace("}", "]")


def run_build(project_dir: str | Path) -> None:
    project_dir = ensure_project_dir(project_dir)
    root = str(project_dir)
    if sys.path and sys.path[0] != root:
        sys.path.insert(0, root)
    apply_pycache_prefix(project_dir)

    site_root = project_dir / BUILD_DIR / SITE_DIR
    site_root.mkdir(parents=True, exist_ok=True)

    _copy_dir(project_dir / "public", site_root)
    _copy_dir(project_dir / "styles", site_root / "styles")

    css_dest = site_root / CSS_OUTPUT
    css_dest.parent.mkdir(parents=True, exist_ok=True)
    binary = tailwind.ensure_tailwind_present(project_dir)
    if binary is not None:
        if not tailwind.compile_tailwind_prod(project_dir, binary, str(css_dest)):
            print("warning: the production Tailwind build failed")
    else:
        print("warning: tailwindcss could not be found, styles have no compiled CSS")

    entries = scan_app_dir(project_dir / "app")
    static_entries = [entry for entry in entries if not entry.is_dynamic]
    dynamic_entries = [entry for entry in entries if entry.is_dynamic]

    for entry in static_entries:
        content = render_route(entry, {})
        output = _route_output_path(site_root, entry.path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(content, encoding="utf-8")

    if dynamic_entries:
        names = ", ".join(_pretty_path(entry.path) for entry in dynamic_entries)
        print(
            f"Skipped dynamic routes, they are not prerendered and must be served "
            f"by the running Koyo server: {names}"
        )

    print(
        f"Built {len(static_entries)} static routes into {project_dir / BUILD_DIR / SITE_DIR}"
    )