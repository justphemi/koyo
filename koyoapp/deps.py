"""Dependency management for Koyo projects: koyoapp add, remove, and install.

Installs or removes packages through the project venv's own pip and keeps
pyproject.toml in sync, the way npm keeps package.json in sync.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import tomlkit
from tomlkit import items

from . import log as koyo_log
from .venv import create_venv

PROJECT_MARKER = "koyo.config.py"


class DepsError(Exception):
    """Raised when a dependency operation cannot be completed."""


def ensure_project_dir(path: str | Path) -> Path:
    path = Path(path)
    if not (path / PROJECT_MARKER).is_file():
        raise DepsError(
            f"not inside a Koyo project, no {PROJECT_MARKER} found in {path}"
        )
    return path


def project_python(path: str | Path) -> str:
    path = Path(path)
    for candidate in (
        path / ".venv" / "bin" / "python",
        path / ".venv" / "Scripts" / "python.exe",
    ):
        if candidate.is_file():
            return str(candidate)
    return sys.executable


def _pip_command(project_dir: Path, args: list[str]) -> list[str]:
    return [project_python(project_dir), "-m", "pip", *args]


def run_pip(
    project_dir: str | Path, args: list[str], verbose: bool | None = None
) -> subprocess.CompletedProcess:
    """Run pip, capturing its output unless verbose mode is on.

    A successful install is quiet, the caller prints its own confirmation
    line. On failure the captured pip output is written so the real error
    is never hidden. Verbose mode echoes the full pip output.
    """
    project_dir = Path(project_dir)
    if verbose is None:
        verbose = koyo_log.verbose_enabled
    result = subprocess.run(
        _pip_command(project_dir, args),
        cwd=str(project_dir),
        capture_output=True,
        text=True,
    )
    if verbose:
        if result.stdout:
            sys.stdout.write(result.stdout)
        if result.stderr:
            sys.stderr.write(result.stderr)
        sys.stdout.flush()
        sys.stderr.flush()
    elif result.returncode != 0:
        if result.stdout:
            sys.stderr.write(result.stdout)
        if result.stderr:
            sys.stderr.write(result.stderr)
        sys.stderr.flush()
    return result


def installed_version(project_dir: str | Path, package: str) -> str | None:
    project_dir = Path(project_dir)
    result = subprocess.run(
        _pip_command(project_dir, ["show", "--disable-pip-version-check", package]),
        cwd=str(project_dir),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    for line in result.stdout.splitlines():
        if line.lower().startswith("version:"):
            return line.split(":", 1)[1].strip()
    return None


_OPERATORS = ("===", "==", "!=", "<=", ">=", "~=", "<", ">", ";")


def _split_requirement(requirement: str) -> tuple[str, str, str]:
    """Split a requirement string into base name, extras, and version spec."""
    text = requirement.strip()
    cut = len(text)
    for operator in _OPERATORS:
        index = text.find(operator)
        if index != -1 and index < cut:
            cut = index
    name_part = text[:cut]
    rest = text[cut:].strip()
    base = name_part
    extras = ""
    if "[" in name_part:
        start = name_part.find("[")
        end = name_part.find("]", start)
        if end != -1:
            base = name_part[:start].strip()
            extras = name_part[start : end + 1]
    return base, extras, rest


def _dedup_key(name: str) -> str:
    return name.strip().replace("-", "_").casefold()


def read_toml(path: Path) -> tomlkit.TOMLDocument:
    if not path.is_file():
        return tomlkit.parse("")
    return tomlkit.parse(path.read_text(encoding="utf-8"))


def write_toml(path: Path, document: tomlkit.TOMLDocument) -> None:
    path.write_text(tomlkit.dumps(document), encoding="utf-8")


def _deps_array(document: tomlkit.TOMLDocument, dev: bool) -> items.Array:
    project = document.get("project")
    if not isinstance(project, items.Table):
        project = items.table()
        document["project"] = project
    if dev:
        optional = project.get("optional-dependencies")
        if not isinstance(optional, items.Table):
            optional = tomlkit.table()
            project["optional-dependencies"] = optional
        value = optional.get("dev")
        if not isinstance(value, items.Array):
            value = tomlkit.array()
            optional["dev"] = value
        return value
    value = project.get("dependencies")
    if not isinstance(value, items.Array):
        value = tomlkit.array()
        project["dependencies"] = value
    return value


def _find_array(document: tomlkit.TOMLDocument, dev: bool) -> items.Array | None:
    project = document.get("project")
    if not isinstance(project, items.Table):
        return None
    if dev:
        optional = project.get("optional-dependencies")
        if not isinstance(optional, items.Table):
            return None
        value = optional.get("dev")
        return value if isinstance(value, items.Array) else None
    value = project.get("dependencies")
    return value if isinstance(value, items.Array) else None


def _upsert(array: items.Array, entry: str) -> None:
    target = _dedup_key(_split_requirement(entry)[0])
    for index in range(len(array)):
        existing = array[index]
        if not isinstance(existing, str):
            continue
        base = _split_requirement(str(existing))[0]
        if _dedup_key(base) == target:
            array[index] = entry
            return
    array.append(entry)


def _remove_entry(array: items.Array, package: str) -> bool:
    target = _dedup_key(package)
    for index in range(len(array)):
        existing = array[index]
        if not isinstance(existing, str):
            continue
        base = _split_requirement(str(existing))[0]
        if _dedup_key(base) == target:
            del array[index]
            return True
    return False


def add(project_dir: str | Path, packages: list[str], dev: bool = False) -> None:
    project_dir = ensure_project_dir(project_dir)
    if not packages:
        raise DepsError("no packages given")
    parsed = [_split_requirement(package) for package in packages]
    for base, _, _ in parsed:
        if not base:
            raise DepsError(f"invalid package requirement: {packages!r}")

    result = run_pip(
        project_dir,
        ["install", "--disable-pip-version-check", *packages],
    )
    if result.returncode != 0:
        raise DepsError("pip install failed, pyproject.toml was not modified")

    entries = []
    for base, extras, spec in parsed:
        if not spec:
            version = installed_version(project_dir, base)
            if version:
                spec = f"=={version}"
        entries.append(f"{base}{extras}{spec}")

    path = Path(project_dir) / "pyproject.toml"
    document = read_toml(path)
    array = _deps_array(document, dev)
    for entry in entries:
        _upsert(array, entry)
    write_toml(path, document)

    for entry in entries:
        koyo_log.info(f"Added {entry} to pyproject.toml")


def remove(project_dir: str | Path, packages: list[str]) -> None:
    project_dir = ensure_project_dir(project_dir)
    if not packages:
        raise DepsError("no packages given")
    for package in packages:
        _remove_one(project_dir, package)


def _remove_one(project_dir: Path, package: str) -> None:
    base, extras, spec = _split_requirement(package)
    if not base:
        raise DepsError(f"invalid package requirement: {package!r}")

    path = project_dir / "pyproject.toml"
    document = read_toml(path)
    found = False
    for dev in (False, True):
        array = _find_array(document, dev)
        if array is not None and _remove_entry(array, base):
            found = True
    if found:
        write_toml(path, document)
        koyo_log.info(f"Removed {base} from pyproject.toml")
    else:
        koyo_log.info(f"{base} is not listed in pyproject.toml")

    run_pip(project_dir, ["uninstall", "--disable-pip-version-check", "-y", base])


def _collect_strings(array: items.Array | None) -> list[str]:
    if array is None:
        return []
    return [str(entry) for entry in array if isinstance(entry, str)]


def install(
    project_dir: str | Path,
    clean: bool = False,
    no_dev: bool = False,
) -> None:
    """Create the project venv if needed and install everything in pyproject.toml."""
    project_dir = ensure_project_dir(project_dir)
    venv_dir = Path(project_dir) / ".venv"

    if clean and venv_dir.exists():
        koyo_log.info("Deleting existing .venv...")
        shutil.rmtree(venv_dir)
    if not venv_dir.exists():
        koyo_log.info(f"Creating a virtual environment in {project_dir / '.venv'}...")
        if not create_venv(project_dir):
            raise DepsError("could not create .venv")

    path = Path(project_dir) / "pyproject.toml"
    document = read_toml(path)
    main_entries = _collect_strings(_find_array(document, dev=False))
    dev_entries = _collect_strings(_find_array(document, dev=True))

    requirements = list(main_entries)
    if not no_dev:
        requirements.extend(dev_entries)

    if not requirements:
        koyo_log.info("No dependencies listed in pyproject.toml, nothing to install")
        return

    result = run_pip(
        project_dir,
        ["install", "--disable-pip-version-check", *requirements],
    )
    if result.returncode != 0:
        raise DepsError("pip install failed")

    dev_count = len(dev_entries) if not no_dev else 0
    koyo_log.info(
        f"Installed {len(main_entries) + dev_count} dependencies "
        f"({len(main_entries)} main, {dev_count} dev) into .venv"
    )


def upgrade(
    project_dir: str | Path,
    version: str | None = None,
    verbose: bool | None = None,
) -> str:
    """Upgrade koyoapp in the project venv.

    Pass a *version* string like ``"0.3.0"`` to pin an exact release,
    or ``None`` for the latest. After a successful install the koyoapp
    entry in pyproject.toml is pinned to the installed version. Returns
    the installed version string.
    """
    project_dir = ensure_project_dir(project_dir)
    requirement = f"koyoapp=={version}" if version else "koyoapp"
    result = run_pip(
        project_dir,
        ["install", "--disable-pip-version-check", "--upgrade", requirement],
        verbose=verbose,
    )
    if result.returncode != 0:
        raise DepsError("pip upgrade failed, check pip output above for details")
    installed = installed_version(project_dir, "koyoapp")
    if not installed:
        raise DepsError("koyoapp upgraded but its version could not be read from the venv")

    path = project_dir / "pyproject.toml"
    document = read_toml(path)
    array = _find_array(document, dev=False)
    if array is not None:
        _upsert(array, f"koyoapp=={installed}")
        write_toml(path, document)
        koyo_log.info(f"Pinned koyoapp=={installed} in pyproject.toml")
    return installed