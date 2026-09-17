"""Project configuration loading from koyo.config.py."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_MODULE_NAME = "__koyo_project_config__"

# The files that identify a directory as a Koyo project root. A directory is
# a Koyo project when it contains at least one of these. koyoapp create
# scaffolds both, so a real project always has one of them.
PROJECT_ROOT_MARKERS = ("app", "koyo.config.py")


def is_project_root(project_dir: str | Path) -> bool:
    """Return True when ``project_dir`` looks like a Koyo project.

    Commands that operate on a project (dev, build, install, ...) call this
    before doing any work so that running them in the wrong directory fails
    fast with a clear message instead of creating files or crashing later.
    """
    project_dir = Path(project_dir)
    return any((project_dir / marker).exists() for marker in PROJECT_ROOT_MARKERS)


def require_project_root(project_dir: str | Path) -> Path:
    """Resolve ``project_dir`` or raise ProjectError when it is not a project."""
    project_dir = Path(project_dir).resolve()
    if not is_project_root(project_dir):
        raise ProjectError(
            f"{project_dir} is not a Koyo project (no {PROJECT_ROOT_MARKERS[0]}/ "
            f"or {PROJECT_ROOT_MARKERS[1]}). Run this command from your project "
            f"directory, or scaffold one with: koyoapp create"
        )
    return project_dir


class ProjectError(Exception):
    """Raised when a command runs outside a Koyo project directory."""


def load(project_dir: str | Path) -> dict:
    project_dir = Path(project_dir)
    config_path = project_dir / "koyo.config.py"
    if not config_path.is_file():
        return {}
    spec = importlib.util.spec_from_file_location(_MODULE_NAME, config_path)
    if spec is None or spec.loader is None:
        return {}
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception:
        return {}
    result = {}
    for name in dir(module):
        if name.startswith("_"):
            continue
        value = getattr(module, name)
        if isinstance(value, (str, int, float, bool)):
            result[name] = value
    return result