"""Project configuration loading from koyo.config.py."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_MODULE_NAME = "__koyo_project_config__"


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