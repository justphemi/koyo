"""Serves a Koyo app. Used by koyoapp dev via uvicorn."""

from __future__ import annotations

import os

from .app import build_app

project_dir = os.environ.get("KOYO_PROJECT_DIR") or "."

app = build_app(project_dir)