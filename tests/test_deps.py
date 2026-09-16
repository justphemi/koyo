import subprocess

import pytest

from koyoapp import deps, log as koyo_log

PYPROJECT = '''\
[project]
name = "demo"
version = "0.1.0"
dependencies = [
    "koyoapp>=0.1.0",
]
'''

PYPROJECT_WITH_MAIN = '''\
[project]
name = "demo"
version = "0.1.0"
dependencies = [
    "koyoapp>=0.1.0",
    "requests==1.0.0",
]
'''

PYPROJECT_WITH_DEV = '''\
[project]
name = "demo"
version = "0.1.0"
dependencies = [
    "koyoapp>=0.1.0",
]

[project.optional-dependencies]
dev = [
    "requests==1.0.0",
]
'''


def make_project(root, pyproject=PYPROJECT):
    (root / "koyo.config.py").write_text("PORT = 2309\n", encoding="utf-8")
    (root / "pyproject.toml").write_text(pyproject, encoding="utf-8")
    return root


def ok_result(*args):
    return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")


def test_add_writes_pinned_entry(tmp_path, monkeypatch, capsys):
    make_project(tmp_path)
    monkeypatch.setattr(deps, "run_pip", lambda _project, args: ok_result(*args))
    monkeypatch.setattr(deps, "installed_version", lambda _project, _name: "2.31.0")

    deps.add(tmp_path, ["requests"])

    text = (tmp_path / "pyproject.toml").read_text(encoding="utf-8")
    assert '"requests==2.31.0"' in text
    assert "    \"koyoapp>=0.1.0\"," in text
    assert text.count("requests") == 1
    assert "Added requests==2.31.0 to pyproject.toml" in capsys.readouterr().out


def test_add_with_specifier_keeps_it(tmp_path, monkeypatch, capsys):
    make_project(tmp_path)
    monkeypatch.setattr(deps, "run_pip", lambda _project, args: ok_result(*args))
    monkeypatch.setattr(deps, "installed_version", lambda _project, _name: "2.31.0")

    deps.add(tmp_path, ["requests>=2.28"])

    text = (tmp_path / "pyproject.toml").read_text(encoding="utf-8")
    assert '"requests>=2.28"' in text
    assert "Added requests>=2.28 to pyproject.toml" in capsys.readouterr().out


def test_add_updates_existing_entry(tmp_path, monkeypatch):
    make_project(tmp_path, PYPROJECT_WITH_MAIN)
    monkeypatch.setattr(deps, "run_pip", lambda _project, args: ok_result(*args))
    monkeypatch.setattr(deps, "installed_version", lambda _project, _name: "2.31.0")

    deps.add(tmp_path, ["requests"])

    text = (tmp_path / "pyproject.toml").read_text(encoding="utf-8")
    assert '"requests==2.31.0"' in text
    assert "requests==1.0.0" not in text
    assert text.count("requests") == 1


def test_add_dev_writes_optional_dependencies(tmp_path, monkeypatch, capsys):
    make_project(tmp_path)
    monkeypatch.setattr(deps, "run_pip", lambda _project, args: ok_result(*args))
    monkeypatch.setattr(deps, "installed_version", lambda _project, _name: "9.1.1")

    deps.add(tmp_path, ["pytest"], dev=True)

    text = (tmp_path / "pyproject.toml").read_text(encoding="utf-8")
    assert "[project.optional-dependencies]" in text
    assert '"pytest==9.1.1"' in text
    assert '"koyoapp>=0.1.0"' in text
    assert "Added pytest==9.1.1 to pyproject.toml" in capsys.readouterr().out


def test_add_dev_updates_existing_dev_entry(tmp_path, monkeypatch):
    make_project(tmp_path, PYPROJECT_WITH_DEV)
    monkeypatch.setattr(deps, "run_pip", lambda _project, args: ok_result(*args))
    monkeypatch.setattr(deps, "installed_version", lambda _project, _name: "3.0.0")

    deps.add(tmp_path, ["requests"], dev=True)

    text = (tmp_path / "pyproject.toml").read_text(encoding="utf-8")
    assert '"requests==3.0.0"' in text
    assert "requests==1.0.0" not in text
    assert text.count("requests") == 1


def test_add_multiple_packages(tmp_path, monkeypatch):
    make_project(tmp_path)
    versions = {"idna": "3.7", "six": "1.16.0"}
    monkeypatch.setattr(deps, "run_pip", lambda _project, args: ok_result(*args))
    monkeypatch.setattr(deps, "installed_version", lambda _project, name: versions[name])

    deps.add(tmp_path, ["idna", "six"])

    text = (tmp_path / "pyproject.toml").read_text(encoding="utf-8")
    assert '"idna==3.7"' in text
    assert '"six==1.16.0"' in text


def test_add_pip_failure_does_not_touch_pyproject(tmp_path, monkeypatch):
    make_project(tmp_path)
    monkeypatch.setattr(
        deps,
        "run_pip",
        lambda _project, args: subprocess.CompletedProcess(args=args, returncode=1, stdout="boom", stderr="error"),
    )

    with pytest.raises(deps.DepsError):
        deps.add(tmp_path, ["does-not-exist"])

    before = (tmp_path / "pyproject.toml").read_bytes()
    assert before == PYPROJECT.encode("utf-8")


def test_remove_deletes_from_both_sections(tmp_path, monkeypatch, capsys):
    make_project(tmp_path, PYPROJECT_WITH_DEV)
    calls = []

    def fake_run(_project, args):
        calls.append(args)
        return ok_result(*args)

    monkeypatch.setattr(deps, "run_pip", fake_run)

    deps.remove(tmp_path, ["requests"])

    text = (tmp_path / "pyproject.toml").read_text(encoding="utf-8")
    assert "requests" not in text
    assert "Removed requests from pyproject.toml" in capsys.readouterr().out
    assert calls == [["uninstall", "--disable-pip-version-check", "-y", "requests"]]


def test_remove_absent_package_is_informational(tmp_path, monkeypatch, capsys):
    make_project(tmp_path)
    monkeypatch.setattr(deps, "run_pip", lambda _project, args: ok_result(*args))

    deps.remove(tmp_path, ["requests"])

    assert "requests is not listed in pyproject.toml" in capsys.readouterr().out
    assert (tmp_path / "pyproject.toml").read_bytes() == PYPROJECT.encode("utf-8")


def test_require_project_dir(tmp_path, monkeypatch):
    (tmp_path / "pyproject.toml").write_text(PYPROJECT, encoding="utf-8")
    monkeypatch.setattr(deps, "run_pip", lambda _project, args: ok_result(*args))
    with pytest.raises(deps.DepsError):
        deps.add(tmp_path, ["requests"])
    with pytest.raises(deps.DepsError):
        deps.remove(tmp_path, ["requests"])


def test_split_requirement():
    cases = [
        ("requests", ("requests", "", "")),
        ("requests==2.31.0", ("requests", "", "==2.31.0")),
        ("requests>=2.28", ("requests", "", ">=2.28")),
        ("requests[socks]>=1.0", ("requests", "[socks]", ">=1.0")),
        ("pytest; python_version >= '3.8'", ("pytest", "", "; python_version >= '3.8'")),
        ("Foo_Bar==1.0", ("Foo_Bar", "", "==1.0")),
    ]
    for requirement, expected in cases:
        assert deps._split_requirement(requirement) == expected


def _stub_subprocess(monkeypatch, returncode, stdout, stderr):
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(
            args=command, returncode=returncode, stdout=stdout, stderr=stderr
        )

    monkeypatch.setattr(deps.subprocess, "run", fake_run)
    return captured


def test_run_pip_quiet_success_captures_output(tmp_path, monkeypatch, capsys):
    make_project(tmp_path)
    captured = _stub_subprocess(
        monkeypatch, 0, "Collecting requests\nSuccessfully installed requests", "ignored noise"
    )
    monkeypatch.setattr(koyo_log, "verbose_enabled", False)

    result = deps.run_pip(tmp_path, ["install", "requests"])

    assert result.returncode == 0
    assert captured["kwargs"]["capture_output"] is True
    out, err = capsys.readouterr()
    assert out == ""
    assert err == ""


def test_run_pip_verbose_streams_output(tmp_path, monkeypatch, capsys):
    make_project(tmp_path)
    _stub_subprocess(monkeypatch, 0, "Collecting six\n", "warning noise")
    monkeypatch.setattr(koyo_log, "verbose_enabled", True)

    deps.run_pip(tmp_path, ["install", "six"])

    out, err = capsys.readouterr()
    assert "Collecting six" in out
    assert "warning noise" in err


def test_run_pip_failure_prints_captured_output(tmp_path, monkeypatch, capsys):
    make_project(tmp_path)
    _stub_subprocess(
        monkeypatch, 1, "ERROR: No matching distribution\nfor does-not-exist", "resolved trace"
    )
    monkeypatch.setattr(koyo_log, "verbose_enabled", False)

    deps.run_pip(tmp_path, ["install", "does-not-exist"])

    out, err = capsys.readouterr()
    assert out == ""
    assert "ERROR: No matching distribution" in err
    assert "resolved trace" in err