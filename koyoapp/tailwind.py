"""Tailwind CSS integration for the Koyo dev server."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from . import log as koyo_log

INPUT_CSS = "styles/globals.css"
OUTPUT_CSS = "styles/koyo.css"
CONFIG_FILE = "tailwind.config.js"


def _local_bin(project_dir: Path) -> Path | None:
    candidate = project_dir / "node_modules" / ".bin" / "tailwindcss"
    return candidate if candidate.exists() else None


def ensure_tailwind_present(project_dir: Path, verbose: bool = False) -> str | None:
    project_dir = Path(project_dir)
    local = _local_bin(project_dir)
    if local is not None:
        return str(local)

    npm = shutil.which("npm")
    if npm is not None:
        koyo_log.info("Installing frontend tooling (tailwindcss) with npm...")
        try:
            result = koyo_log.run(
                [npm, "install", "--no-fund", "--no-audit"], cwd=str(project_dir)
            )
            if result.returncode != 0:
                koyo_log.error("npm install failed")
        except OSError as exc:
            koyo_log.warn(f"could not run npm install: {exc}")

    local = _local_bin(project_dir)
    if local is not None:
        return str(local)

    standalone = shutil.which("tailwindcss")
    if standalone is not None:
        return standalone
    return None


def _tailwind_cmd(
    binary: str,
    project_dir: Path,
    watch: bool,
    output: str | None = None,
    minify: bool = False,
) -> list[str]:
    cmd = [binary, "-i", INPUT_CSS, "-o", output or OUTPUT_CSS, "-c", CONFIG_FILE]
    if watch:
        cmd.append("--watch")
    if minify:
        cmd.append("--minify")
    return cmd


def compile_tailwind(project_dir: Path, binary: str, verbose: bool = False) -> bool:
    result = koyo_log.run(_tailwind_cmd(binary, project_dir, watch=False), cwd=str(project_dir))
    return result.returncode == 0


def compile_tailwind_prod(project_dir: Path, binary: str, output: str, verbose: bool = False) -> bool:
    result = koyo_log.run(
        _tailwind_cmd(binary, project_dir, watch=False, output=output, minify=True),
        cwd=str(project_dir),
    )
    return result.returncode == 0


def start_tailwind_watch(
    project_dir: Path, binary: str, verbose: bool = False
) -> subprocess.Popen:
    command = _tailwind_cmd(binary, project_dir, watch=True)
    if verbose:
        return subprocess.Popen(command, cwd=str(project_dir))
    log_file = koyo_log.open_log(project_dir / ".koyo", "tailwind.log")
    return subprocess.Popen(
        command, cwd=str(project_dir), stdout=log_file, stderr=subprocess.STDOUT
    )