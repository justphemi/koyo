"""Small shared logging for the koyoapp CLI.

Keeps developer facing output short and consistent. By default the raw
output of subprocesses (pip, npm, the Tailwind CLI, uvicorn) is captured
instead of streamed, and only surfaces when a command actually fails. The
--verbose flag turns that back into full streaming output for debugging.
"""

from __future__ import annotations

import subprocess
import sys

verbose_enabled = False


def set_verbose(enabled: bool) -> None:
    global verbose_enabled
    verbose_enabled = bool(enabled)


def info(msg: str) -> None:
    print(msg)
    sys.stdout.flush()


def success(msg: str) -> None:
    print(msg)
    sys.stdout.flush()


def warn(msg: str) -> None:
    print(f"warning: {msg}")
    sys.stderr.flush()


def error(msg: str) -> None:
    print(f"error: {msg}")
    sys.stderr.flush()


def run(command: list[str], cwd: str | None = None) -> subprocess.CompletedProcess:
    """Run a subprocess, capturing its output by default.

    In verbose mode the output is echoed back to the terminal as it
    finishes, so a debugging session sees the full raw output. Outside
    verbose mode the captured output is only written when the command
    fails, so success stays quiet and failures are never hidden.
    """
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True)
    if verbose_enabled:
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


def open_log(directory, name: str):
    """Open an append mode file handle for long running subprocess output."""
    directory.mkdir(parents=True, exist_ok=True)
    return (directory / name).open("ab")