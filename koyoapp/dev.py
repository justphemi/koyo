"""The koyoapp dev command: a local dev server with hot reload."""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import watchfiles

from . import config as koyo_config
from . import log as koyo_log
from . import net as koyo_net
from .config import ProjectError, require_project_root
from .reload import apply_pycache_prefix, bump_token, with_pycache_env
from .tailwind import OUTPUT_CSS, compile_tailwind, ensure_tailwind_present, start_tailwind_watch

DEFAULT_PORT = 2309
DEFAULT_HOST = "0.0.0.0"
_MAX_PORT_SCAN = 200

_LOGO = """\
*   *  *****  *   *  *****
*  *   *   *  *   *  *   *
* *    *   *   * *   *   *
***    *   *    *    *   *
* *    *   *    *    *   *
*  *   *   *    *    *   *
*   *  *****    *    *****"""
SERVER_LOG = "dev-server.log"
_WATCH_STEP = 150


def run_dev(
    project_dir: Path,
    port: int | None = None,
    host: str | None = None,
    verbose: bool = False,
) -> None:
    if verbose:
        koyo_log.set_verbose(True)
    started = time.monotonic()
    # Fail fast before creating directories, running npm, or spawning servers:
    # running koyoapp dev outside a project used to scaffold empty app/, public/
    # and styles/ folders into the current directory and then crash.
    project_dir = require_project_root(project_dir)
    apply_pycache_prefix(project_dir)
    explicit_port = port is not None
    bind_host = host or DEFAULT_HOST
    configured = koyo_config.load(project_dir)
    if port is None:
        port = configured.get("PORT", DEFAULT_PORT)
    resolved = resolve_free_port(port)
    if resolved != port:
        koyo_log.info(f"Port {port} is already in use, using {resolved} instead")
        port = resolved

    for name in ("app", "public", "styles"):
        (project_dir / name).mkdir(parents=True, exist_ok=True)

    tailwind_proc = None
    tailwind = ensure_tailwind_present(project_dir, verbose=verbose)
    if tailwind is not None:
        if not compile_tailwind(project_dir, tailwind, verbose=verbose):
            koyo_log.warn("the initial Tailwind build failed")
        tailwind_proc = start_tailwind_watch(project_dir, tailwind, verbose=verbose)
    else:
        koyo_log.warn("tailwindcss could not be found, styles will be served without Tailwind compilation")

    bump_token(project_dir)

    server_proc = _spawn_server(project_dir, port, bind_host, verbose=verbose)
    ready_elapsed = _wait_until_ready(port)
    if ready_elapsed is None:
        koyo_log.warn("the dev server did not respond before the timeout")
    _print_startup(port, int((time.monotonic() - started) * 1000))

    watch_paths: list = [
        project_dir / "app",
        project_dir / "public",
        project_dir / "styles",
        project_dir / "koyo.config.py",
        project_dir / "tailwind.config.js",
    ]
    watch_paths = _existing_watch_paths(watch_paths)
    components_dir = project_dir / "components"
    if components_dir.is_dir():
        watch_paths.append(components_dir)

    try:
        for raw_changes in watchfiles.watch(*watch_paths, step=_WATCH_STEP):
            changes = _drop_tailwind_output(raw_changes)
            if not changes:
                continue
            _report_changes(changes, project_dir)
            if not explicit_port:
                new_port = koyo_config.load(project_dir).get("PORT")
                if new_port is not None and new_port != port:
                    resolved = resolve_free_port(new_port)
                    if resolved != port:
                        port = resolved
                        koyo_log.info(f"Port changed to {port}")
            _stop(server_proc)
            bump_token(project_dir)
            server_proc = _spawn_server(project_dir, port, bind_host, verbose=verbose)
            koyo_log.info("Restarted the dev server")
    except KeyboardInterrupt:
        koyo_log.info("Stopping the Koyo dev server.")
    finally:
        _stop(server_proc)
        if tailwind_proc is not None:
            _stop(tailwind_proc)


def _existing_watch_paths(paths: list) -> list:
    """Drop watched paths that do not exist yet.

    watchfiles' RustNotify raises FileNotFoundError("No path was found.")
    when any watched path is missing, which crashed the dev server for
    projects without a koyo.config.py or tailwind.config.js. Those files are
    optional, so watching a subset is the correct behavior.
    """
    return [path for path in paths if path.exists()]


def _print_startup(port: int, elapsed_ms: int) -> None:
    for line in _LOGO.splitlines():
        koyo_log.info(line.rstrip())
    koyo_log.info("Koyo dev server")
    koyo_log.info(f"Local    http://localhost:{port}")
    lan_ip = koyo_net.detect_lan_ip()
    if lan_ip is not None:
        koyo_log.info(f"Network  http://{lan_ip}:{port}")
    koyo_log.info(f"Ready in {elapsed_ms}ms")


def resolve_free_port(port: int, host: str = "127.0.0.1", timeout: float = 0.3) -> int:
    """Return the first free port at or above ``port``, scanning upward."""
    if not _port_in_use(port, host, timeout):
        return port
    for candidate in range(port + 1, port + 1 + _MAX_PORT_SCAN):
        if not _port_in_use(candidate, host, timeout):
            return candidate
    return port


def _port_in_use(port: int, host: str, timeout: float) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _wait_until_ready(port: int, host: str = "127.0.0.1", timeout: float = 10.0) -> float | None:
    """Return how long the server took to start responding, or None on timeout."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.3):
                return time.monotonic() - deadline + timeout
        except OSError:
            time.sleep(0.1)
    return None


def _spawn_server(
    project_dir: Path, port: int, host: str = DEFAULT_HOST, verbose: bool = False
) -> subprocess.Popen | None:
    env = with_pycache_env(dict(os.environ), project_dir)
    env["KOYO_PROJECT_DIR"] = str(project_dir)
    env["KOYO_DEV"] = "1"
    command = [
        sys.executable,
        "-m",
        "uvicorn",
        "koyoapp.serve:app",
        "--host",
        host,
        "--port",
        str(port),
    ]
    log_handle = None
    if verbose:
        proc = subprocess.Popen(command, cwd=str(project_dir), env=env)
    else:
        log_handle = koyo_log.open_log(project_dir / ".koyo", SERVER_LOG)
        proc = subprocess.Popen(
            command,
            cwd=str(project_dir),
            env=env,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
        )
    time.sleep(0.3)
    if proc.poll() is not None:
        koyo_log.error("the server process exited immediately")
        if log_handle is not None:
            log_handle.flush()
            log_handle.close()
            try:
                sys.stderr.write(
                    (project_dir / ".koyo" / SERVER_LOG).read_text(encoding="utf-8", errors="replace")
                )
            except OSError:
                pass
        proc = None
    elif log_handle is not None:
        log_handle.close()
    return proc


def _stop(proc: subprocess.Popen | None) -> None:
    if proc is None or proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=8)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)


def _report_changes(changes, project_dir: Path) -> None:
    base = str(project_dir)
    for _, path in changes:
        rel = os.path.relpath(str(path), base)
        koyo_log.info(f"Compiled {rel}")


def _drop_tailwind_output(changes) -> set:
    relevant = set()
    for change, path in changes:
        path_str = str(path)
        if path_str.endswith(f"/{OUTPUT_CSS}"):
            continue
        relevant.add((change, path))
    return relevant