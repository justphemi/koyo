import subprocess

import pytest

from koyoapp import deps

PYPROJECT_SAMPLE = '''\
[project]
name = "demo"
version = "0.1.0"
dependencies = [
    "requests==2.31.0",
    "httpx>=0.27",
]

[project.optional-dependencies]
dev = [
    "pytest==9.1.1",
]
'''

PYPROJECT_NO_DEPS = '''\
[project]
name = "demo"
version = "0.1.0"
'''


def make_project(root, pyproject=PYPROJECT_SAMPLE):
    (root / "koyo.config.py").write_text("PORT = 2309\n", encoding="utf-8")
    (root / "pyproject.toml").write_text(pyproject, encoding="utf-8")
    return root


def ok_result(*args):
    return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")


def test_install_creates_missing_venv(tmp_path, monkeypatch, capsys):
    make_project(tmp_path)
    created = []

    def fake_create(project_dir):
        created.append(project_dir)
        return True

    calls = []

    def fake_run(project_dir, args):
        calls.append(args)
        return ok_result(*args)

    monkeypatch.setattr(deps, "create_venv", fake_create)
    monkeypatch.setattr(deps, "run_pip", fake_run)

    deps.install(tmp_path)

    assert created == [tmp_path]
    assert calls == [["install", "--disable-pip-version-check", "requests==2.31.0", "httpx>=0.27", "pytest==9.1.1"]]
    out = capsys.readouterr().out
    assert "Creating a virtual environment" in out
    assert "Installed 3 dependencies (2 main, 1 dev) into .venv" in out


def test_install_reuses_existing_venv(tmp_path, monkeypatch, capsys):
    make_project(tmp_path)
    (tmp_path / ".venv").mkdir()
    (tmp_path / ".venv" / "bin").mkdir()
    (tmp_path / ".venv" / "bin" / "python").write_text("#!/bin/sh\n", encoding="utf-8")

    created = []

    def fake_create(project_dir):
        created.append(project_dir)
        return True

    monkeypatch.setattr(deps, "create_venv", fake_create)
    monkeypatch.setattr(deps, "run_pip", lambda project_dir, args: ok_result(*args))

    deps.install(tmp_path)

    assert created == []
    out = capsys.readouterr().out
    assert "Creating a virtual environment" not in out
    assert "Installed 3 dependencies (2 main, 1 dev) into .venv" in out


def test_install_no_dev_skips_dev_section(tmp_path, monkeypatch, capsys):
    make_project(tmp_path)
    calls = []
    monkeypatch.setattr(deps, "create_venv", lambda project_dir: True)
    monkeypatch.setattr(
        deps, "run_pip", lambda project_dir, args: (calls.append(args), ok_result(*args))[1]
    )

    deps.install(tmp_path, no_dev=True)

    assert calls == [["install", "--disable-pip-version-check", "requests==2.31.0", "httpx>=0.27"]]
    out = capsys.readouterr().out
    assert "Installed 2 dependencies (2 main, 0 dev) into .venv" in out


def test_install_clean_deletes_existing_venv(tmp_path, monkeypatch, capsys):
    make_project(tmp_path)
    (tmp_path / ".venv").mkdir()
    (tmp_path / ".venv" / "sentinel").write_text("present", encoding="utf-8")

    created = []
    monkeypatch.setattr(deps, "create_venv", lambda project_dir: (created.append(project_dir), True)[1])
    monkeypatch.setattr(deps, "run_pip", lambda project_dir, args: ok_result(*args))

    deps.install(tmp_path, clean=True)

    assert not (tmp_path / ".venv" / "sentinel").exists()
    assert created == [tmp_path]
    out = capsys.readouterr().out
    assert "Deleting existing .venv..." in out


def test_install_no_dependencies_prints_info(tmp_path, monkeypatch, capsys):
    make_project(tmp_path, PYPROJECT_NO_DEPS)
    calls = []
    monkeypatch.setattr(deps, "create_venv", lambda project_dir: True)
    monkeypatch.setattr(
        deps, "run_pip", lambda project_dir, args: (calls.append(args), ok_result(*args))[1]
    )

    deps.install(tmp_path)

    assert calls == []
    out = capsys.readouterr().out
    assert "No dependencies listed in pyproject.toml, nothing to install" in out


def test_install_pip_failure_raises(tmp_path, monkeypatch):
    make_project(tmp_path)
    monkeypatch.setattr(deps, "create_venv", lambda project_dir: True)
    monkeypatch.setattr(
        deps,
        "run_pip",
        lambda project_dir, args: subprocess.CompletedProcess(args=args, returncode=1, stdout="", stderr="error"),
    )

    with pytest.raises(deps.DepsError):
        deps.install(tmp_path)


def test_install_requires_project_dir(tmp_path, monkeypatch):
    (tmp_path / "pyproject.toml").write_text(PYPROJECT_SAMPLE, encoding="utf-8")
    with pytest.raises(deps.DepsError):
        deps.install(tmp_path)