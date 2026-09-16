import subprocess

import pytest

from koyoapp import deps

PYPROJECT = '''\
[project]
name = "demo"
version = "0.1.0"
dependencies = [
    "koyoapp>=0.1.0",
]
'''


def make_project(root, pyproject=PYPROJECT):
    (root / "koyo.config.py").write_text("PORT = 2309\n", encoding="utf-8")
    (root / "pyproject.toml").write_text(pyproject, encoding="utf-8")
    return root


def ok_result(*args, **kwargs):
    return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")


def fail_result(*args, **kwargs):
    return subprocess.CompletedProcess(args=args, returncode=1, stdout="", stderr="error")


def test_upgrade_latest_passes_correct_args(tmp_path, monkeypatch):
    make_project(tmp_path)
    calls = []
    monkeypatch.setattr(
        deps, "run_pip", lambda project_dir, args, **kw: (calls.append(args), ok_result(*args))[1]
    )
    monkeypatch.setattr(deps, "installed_version", lambda _project, _pkg: "0.3.0")

    installed = deps.upgrade(tmp_path)

    assert calls == [["install", "--disable-pip-version-check", "--upgrade", "koyoapp"]]
    assert installed == "0.3.0"
    text = (tmp_path / "pyproject.toml").read_text(encoding="utf-8")
    assert '"koyoapp==0.3.0"' in text


def test_upgrade_pinned_version_passes_correct_args(tmp_path, monkeypatch):
    make_project(tmp_path)
    calls = []
    monkeypatch.setattr(
        deps, "run_pip", lambda project_dir, args, **kw: (calls.append(args), ok_result(*args))[1]
    )
    monkeypatch.setattr(deps, "installed_version", lambda _project, _pkg: "0.2.1")

    installed = deps.upgrade(tmp_path, version="0.2.1")

    assert calls == [["install", "--disable-pip-version-check", "--upgrade", "koyoapp==0.2.1"]]
    assert installed == "0.2.1"
    text = (tmp_path / "pyproject.toml").read_text(encoding="utf-8")
    assert '"koyoapp==0.2.1"' in text


def test_upgrade_pip_failure_raises_and_keeps_toml(tmp_path, monkeypatch):
    make_project(tmp_path)
    monkeypatch.setattr(deps, "run_pip", lambda project_dir, args, **kw: fail_result(*args))
    monkeypatch.setattr(deps, "installed_version", lambda _project, _pkg: "0.1.0")

    with pytest.raises(deps.DepsError, match="pip upgrade failed"):
        deps.upgrade(tmp_path)

    text = (tmp_path / "pyproject.toml").read_text(encoding="utf-8")
    assert '"koyoapp>=0.1.0"' in text


def test_upgrade_requires_project_dir(tmp_path):
    (tmp_path / "pyproject.toml").write_text(PYPROJECT, encoding="utf-8")
    with pytest.raises(deps.DepsError, match="not inside a Koyo project"):
        deps.upgrade(tmp_path)


def test_upgrade_unknown_version_raises(tmp_path, monkeypatch):
    make_project(tmp_path)
    monkeypatch.setattr(deps, "run_pip", lambda project_dir, args, **kw: ok_result(*args))
    monkeypatch.setattr(deps, "installed_version", lambda _project, _pkg: None)

    with pytest.raises(deps.DepsError, match="version could not be read"):
        deps.upgrade(tmp_path)


def test_upgrade_writes_toml_even_when_koyoapp_missing(tmp_path, monkeypatch):
    text = '''\
[project]
name = "demo"
version = "0.1.0"
dependencies = [
    "requests==2.31.0",
]
'''
    make_project(tmp_path, text)
    monkeypatch.setattr(deps, "run_pip", lambda project_dir, args, **kw: ok_result(*args))
    monkeypatch.setattr(deps, "installed_version", lambda _project, _pkg: "0.2.1")

    deps.upgrade(tmp_path)

    toml = (tmp_path / "pyproject.toml").read_text(encoding="utf-8")
    assert '"koyoapp==0.2.1"' in toml
    assert '"requests==2.31.0"' in toml
