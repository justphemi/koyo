"""Per route merged metadata for pages and layouts.

A page.py or layout.py may export a ``metadata`` dict with keys ``title``,
``description``, and ``og_image``. The router merges page metadata over its
ancestor layouts and exposes the merged dict here, so the root layout can
render the corresponding head tags automatically.
"""

from __future__ import annotations

from contextvars import ContextVar

from .html import meta, title

_SUPPORTED_KEYS = ("title", "description", "og_image")

_METADATA: ContextVar[dict] = ContextVar("koyo_metadata", default={})


def supported_keys() -> tuple[str, ...]:
    return _SUPPORTED_KEYS


def current() -> dict:
    """The merged metadata for the route currently being rendered."""
    return _METADATA.get()


def push(metadata: dict) -> object:
    """Set the metadata for the current render and return a reset token."""
    return _METADATA.set(metadata)


def pop(token: object) -> None:
    _METADATA.reset(token)


def metadata_tags() -> list:
    """Head tags (title, description, og:image) for the current metadata."""
    data = current()
    tags = []
    title_text = data.get("title")
    if title_text:
        tags.append(title()[str(title_text)])
    description = data.get("description")
    if description:
        tags.append(meta(name="description", content=str(description)))
    og_image = data.get("og_image")
    if og_image:
        tags.append(meta(property="og:image", content=str(og_image)))
    return tags