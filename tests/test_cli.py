from typer.testing import CliRunner

from koyoapp import __version__
from koyoapp.cli import app

runner = CliRunner()


def test_version_long_flag():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_version_short_flag():
    result = runner.invoke(app, ["-v"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_upgrade_help():
    result = runner.invoke(app, ["upgrade", "--help"])
    assert result.exit_code == 0
    assert "latest" in result.output.lower() or "specific" in result.output.lower()


def test_install_help():
    result = runner.invoke(app, ["install", "--help"])
    assert result.exit_code == 0
    assert "pyproject" in result.output.lower() or "dependencies" in result.output.lower()


def test_add_help():
    result = runner.invoke(app, ["add", "--help"])
    assert result.exit_code == 0
    assert "install" in result.output.lower() or "packages" in result.output.lower()


def test_remove_help():
    result = runner.invoke(app, ["remove", "--help"])
    assert result.exit_code == 0
    assert "uninstall" in result.output.lower() or "packages" in result.output.lower()


def test_build_help():
    result = runner.invoke(app, ["build", "--help"])
    assert result.exit_code == 0
    assert "prerender" in result.output.lower() or "static" in result.output.lower()


def test_no_args_exits_cleanly():
    result = runner.invoke(app, [])
    assert result.exit_code == 0
