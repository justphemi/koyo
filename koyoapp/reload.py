"""Dev reload coordination between the CLI watcher and the running server."""

from __future__ import annotations

import functools
import os
import sys
import time
from pathlib import Path

TOKEN_DIR = ".koyo"
TOKEN_FILE = "reload-token"
RELOAD_URL = "/__koyo-reload"
LIVE_RELOAD_URL = "/__koyo-live-reload.js"
PYCACHE_SUBDIR = "pycache"

_VENDOR_DIR = Path(__file__).resolve().parent / "vendor"


def _read_vendor(name: str) -> str:
    return (_VENDOR_DIR / name).read_text(encoding="utf-8")


@functools.lru_cache(maxsize=1)
def live_reload_js() -> str:
    """The concatenated client script: morphdom + the live reload poll and morph."""
    return _read_vendor("morphdom.min.js") + "\n" + _read_vendor("koyo-live-reload.js")


def pycache_dir(project_dir: str | Path) -> Path:
    """The single bytecode cache location for a project's Python files."""
    return Path(project_dir) / TOKEN_DIR / PYCACHE_SUBDIR


def apply_pycache_prefix(project_dir: str | Path) -> str:
    """Redirect bytecode caching for this process into .koyo/pycache."""
    directory = pycache_dir(project_dir)
    directory.mkdir(parents=True, exist_ok=True)
    sys.pycache_prefix = str(directory)
    return str(directory)


def with_pycache_env(env: dict, project_dir: str | Path) -> dict:
    """Set PYTHONPYCACHEPREFIX in a child process environment."""
    directory = pycache_dir(project_dir)
    directory.mkdir(parents=True, exist_ok=True)
    env["PYTHONPYCACHEPREFIX"] = str(directory)
    return env


def dev_mode() -> bool:
    return os.environ.get("KOYO_DEV") == "1"


def token_path(project_dir: str | Path) -> Path:
    return Path(project_dir) / TOKEN_DIR / TOKEN_FILE


def current_token(project_dir: str | Path) -> str:
    path = token_path(project_dir)
    try:
        return str(path.stat().st_mtime_ns)
    except OSError:
        return "0"


def bump_token(project_dir: str | Path) -> None:
    path = token_path(project_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(time.time_ns()), encoding="utf-8")


_RELOAD_SCRIPT = (
    f'<script id="koyo-reload-script" src="{LIVE_RELOAD_URL}"></script>'
)


def _reload_script() -> str:
    return _RELOAD_SCRIPT


def inject_dev_reload(content: str) -> str:
    """Inject the auto reload probe into an HTML document in dev mode only."""
    if not dev_mode():
        return content
    if "koyo-reload-script" in content:
        return content
    body_marker = "</body>"
    if body_marker in content:
        return content.replace(body_marker, _reload_script() + body_marker, 1)
    return content + _reload_script()