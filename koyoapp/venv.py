"""Shared virtual environment helpers for Koyo."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def create_venv(project_dir: str | Path) -> bool:
    """Create the project .venv using the current interpreter, if possible."""
    project_dir = Path(project_dir)
    result = subprocess.run(
        [sys.executable, "-m", "venv", str(project_dir / ".venv")],
        check=False,
    )
    return result.returncode == 0