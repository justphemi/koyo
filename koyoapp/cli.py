"""The koyoapp command line interface."""

from __future__ import annotations

from pathlib import Path

import typer

from . import deps as koyo_deps
from . import log as koyo_log
from .build import run_build
from .dev import DEFAULT_HOST, run_dev
from .scaffold import ScaffoldError, scaffold

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Koyo, a Python web framework with file based routing.",
)


@app.command()
def create(
    target: str = typer.Argument(
        ..., help="Directory to scaffold into, or '.' for the current directory."
    ),
) -> None:
    """Scaffold a new Koyo project."""
    try:
        scaffold(target)
    except ScaffoldError as exc:
        typer.echo(f"error: {exc}")
        raise typer.Exit(code=1)


@app.command()
def dev(
    port: int = typer.Option(
        None, "--port", help="Port to listen on. Defaults to the project PORT setting, then 2309."
    ),
    host: str = typer.Option(
        None,
        "--host",
        help=f"Address to bind. Defaults to {DEFAULT_HOST}, reachable from other devices on the LAN.",
    ),
    verbose: bool = typer.Option(
        False, "--verbose", help="Stream raw subprocess output from uvicorn, npm, and Tailwind."
    ),
) -> None:
    """Run the Koyo dev server with hot reload."""
    koyo_log.set_verbose(verbose)
    run_dev(Path.cwd(), port, host=host, verbose=verbose)


@app.command()
def add(
    packages: list[str] = typer.Argument(
        ..., help="Package names or requirement specifiers to install, for example requests or requests==2.31.0."
    ),
    dev: bool = typer.Option(
        False, "--dev", help="Add the packages to the dev optional dependencies section instead."
    ),
    verbose: bool = typer.Option(
        False, "--verbose", help="Stream the full pip output instead of a quiet summary."
    ),
) -> None:
    """Install packages into the project venv and record them in pyproject.toml."""
    koyo_log.set_verbose(verbose)
    try:
        koyo_deps.add(Path.cwd(), packages, dev=dev)
    except koyo_deps.DepsError as exc:
        typer.echo(f"error: {exc}")
        raise typer.Exit(code=1)


@app.command()
def remove(
    packages: list[str] = typer.Argument(
        ..., help="Package names to uninstall and remove from pyproject.toml."
    ),
    verbose: bool = typer.Option(
        False, "--verbose", help="Stream the full pip output instead of a quiet summary."
    ),
) -> None:
    """Uninstall packages from the project venv and remove them from pyproject.toml."""
    koyo_log.set_verbose(verbose)
    try:
        koyo_deps.remove(Path.cwd(), packages)
    except koyo_deps.DepsError as exc:
        typer.echo(f"error: {exc}")
        raise typer.Exit(code=1)


@app.command()
def install(
    clean: bool = typer.Option(
        False, "--clean", help="Delete and recreate .venv before installing."
    ),
    no_dev: bool = typer.Option(
        False, "--no-dev", help="Install only the main dependencies, skipping the dev section."
    ),
    verbose: bool = typer.Option(
        False, "--verbose", help="Stream the full pip output instead of a quiet summary."
    ),
) -> None:
    """Install all dependencies listed in pyproject.toml into the project venv."""
    koyo_log.set_verbose(verbose)
    try:
        koyo_deps.install(Path.cwd(), clean=clean, no_dev=no_dev)
    except koyo_deps.DepsError as exc:
        typer.echo(f"error: {exc}")
        raise typer.Exit(code=1)


@app.command()
def build() -> None:
    """Prerender static routes to production HTML in .koyo/build."""
    try:
        run_build(Path.cwd())
    except koyo_deps.DepsError as exc:
        typer.echo(f"error: {exc}")
        raise typer.Exit(code=1)


main = app

if __name__ == "__main__":
    app()