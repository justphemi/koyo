"""Project scaffolding for koyoapp create."""

from __future__ import annotations

from pathlib import Path

from . import templates
from .config import PROJECT_ROOT_MARKERS
from ._placeholders import ICON_RGB, LOGO_RGB, make_favicon_ico, make_png
from .venv import create_venv

_KOYO_VERSION = None

_ASSET_DIR = Path(__file__).resolve().parent / "assets"


class ScaffoldError(Exception):
    """Raised when a project cannot be scaffolded."""


def _koyo_version() -> str:
    global _KOYO_VERSION
    if _KOYO_VERSION is None:
        from .__init__ import __version__

        _KOYO_VERSION = __version__
    return _KOYO_VERSION


def scaffold(target: str) -> Path:
    if target in ("", ".", "./"):
        root = Path.cwd().resolve()
        project_name = root.name
    else:
        root = (Path.cwd() / target).resolve()
        project_name = target.replace("/", "-")

    if any((root / marker).exists() for marker in PROJECT_ROOT_MARKERS):
        raise ScaffoldError(
            f"refusing to scaffold into {root}, a Koyo project already exists there"
        )

    root.mkdir(parents=True, exist_ok=True)

    for relpath, content in templates.FILES.items():
        path = root / relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            content.replace("__PROJECT_NAME__", project_name).replace(
                "__KOYO_VERSION__", _koyo_version()
            ),
            encoding="utf-8",
        )

    public_dir = root / "public"
    public_dir.mkdir(exist_ok=True)
    assets = sorted(_ASSET_DIR.glob("*")) if _ASSET_DIR.is_dir() else []
    if assets:
        for asset in assets:
            (public_dir / asset.name).write_bytes(asset.read_bytes())
    else:
        (public_dir / "favicon.ico").write_bytes(make_favicon_ico())
        (public_dir / "logo.png").write_bytes(make_png(512, 512, LOGO_RGB))
        (public_dir / "icon.png").write_bytes(make_png(1024, 1024, ICON_RGB))

    print(f"Creating a virtual environment in {root / '.venv'}...")
    if not create_venv(root):
        print("warning: could not create .venv, the project will still work from your current Python")

    print(f"\nScaffolded a new Koyo project in {root}")
    print("Next steps:")
    print(f"  cd {root}")
    print("  koyoapp dev")
    return root