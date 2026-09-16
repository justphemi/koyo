"""File based routing for Koyo, modeled on the Next.js app directory."""

from __future__ import annotations

import importlib.util
import inspect
import sys
from pathlib import Path
from typing import Any

from . import meta as koyo_meta
from .html import Element, Markup, render_html

_MODULE_PREFIX = "__koyo_route__"


class RouteError(Exception):
    """Raised when a page or layout module cannot fulfil the routing contract."""


class RouteEntry:
    """A single route derived from a page.py file."""

    def __init__(
        self,
        page_file: Path,
        segments: tuple[str, ...],
        layout_refs: list[tuple[str, Path]],
        page_module: str,
    ) -> None:
        self.page_file = page_file
        self.segments = segments
        self.layout_refs = layout_refs
        self.page_module = page_module
        self.path = self._build_path(segments)
        self.params = [
            seg[1:-1]
            for seg in segments
            if len(seg) > 2 and seg.startswith("[") and seg.endswith("]")
        ]

    @property
    def is_dynamic(self) -> bool:
        return bool(self.params)

    @staticmethod
    def _build_path(segments: tuple[str, ...]) -> str:
        if not segments:
            return "/"
        parts: list[str] = []
        for seg in segments:
            if len(seg) > 2 and seg.startswith("[") and seg.endswith("]"):
                parts.append("{" + seg[1:-1] + "}")
            else:
                parts.append(seg)
        return "/" + "/".join(parts)


def _sanitize(segment: str) -> str:
    return "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in segment)


def _module_name(segments: tuple[str, ...], kind: str) -> str:
    if not segments:
        return f"{_MODULE_PREFIX}.root.{kind}"
    body = ".".join(_sanitize(seg) or "_" for seg in segments)
    return f"{_MODULE_PREFIX}.{body}.{kind}"


def scan_app_dir(app_dir: Path) -> list[RouteEntry]:
    """Walk app/ and build the route table."""
    app_dir = Path(app_dir)
    entries: list[RouteEntry] = []
    if not app_dir.is_dir():
        return entries
    for page_file in sorted(app_dir.rglob("page.py")):
        rel = page_file.parent.relative_to(app_dir)
        segments = tuple(rel.parts)
        layout_refs: list[tuple[str, Path]] = []
        for i in range(len(segments) + 1):
            layout_dir = app_dir.joinpath(*segments[:i])
            layout_file = layout_dir / "layout.py"
            if layout_file.is_file():
                layout_refs.append((_module_name(segments[:i], "layout"), layout_file))
        page_module = _module_name(segments, "page")
        entries.append(RouteEntry(page_file, segments, layout_refs, page_module))
    return entries


def clear_module_cache() -> None:
    """Drop imported page and layout modules so the next request re-reads them."""
    for name in [name for name in list(sys.modules) if name.startswith(_MODULE_PREFIX)]:
        del sys.modules[name]


def reset_project_modules() -> None:
    """Drop modules imported from this or a previous Koyo project.

    Pages and layouts live under the reserved _MODULE_PREFIX namespace.
    Components are imported under their own names, for example
    components.site, so a stale module from an earlier project would
    otherwise keep resolving. This is safe to run at app build time: the
    routes only re-import their modules when serving the first request.
    """
    drop = []
    for name in list(sys.modules):
        if name.startswith(_MODULE_PREFIX):
            drop.append(name)
        elif name == "components" or name.startswith("components."):
            drop.append(name)
    for name in drop:
        sys.modules.pop(name, None)


def _import_page(page_file: Path, name: str) -> Any:
    if name in sys.modules:
        return sys.modules[name]
    return _load_module(name, page_file)


def _module_metadata(module: Any) -> dict:
    value = getattr(module, "metadata", None)
    if not isinstance(value, dict):
        return {}
    keys = koyo_meta.supported_keys()
    return {
        key: str(item)
        for key, item in value.items()
        if key in keys and item is not None
    }


def merge_metadata(entry: RouteEntry) -> dict:
    """Merge page metadata over its ancestor layouts, root first."""
    merged: dict = {}
    for layout_module, layout_file in entry.layout_refs:
        layout_obj = _load_module(layout_module, layout_file)
        merged.update(_module_metadata(layout_obj))
    page_obj = _import_page(entry.page_file, entry.page_module)
    merged.update(_module_metadata(page_obj))
    return merged


def _load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RouteError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        del sys.modules[name]
        raise
    return module


def _accepts_request(fn) -> bool:
    try:
        return "request" in inspect.signature(fn).parameters
    except (TypeError, ValueError):
        return False


def _call_page(fn, params: dict[str, str], request) -> Any:
    kwargs = dict(params)
    if _accepts_request(fn):
        kwargs["request"] = request
    return fn(**kwargs)


def _call_layout(fn, children: Markup, request) -> Any:
    kwargs: dict[str, Any] = {"children": children}
    if _accepts_request(fn):
        kwargs["request"] = request
    return fn(**kwargs)


def render_route(entry: RouteEntry, params: dict[str, str], request=None) -> str:
    """Render a route entry into a full HTML document string."""
    merged = merge_metadata(entry)
    token = koyo_meta.push(merged)
    try:
        page_module = _import_page(entry.page_file, entry.page_module)
        page_fn = getattr(page_module, "page", None)
        if page_fn is None:
            raise RouteError(f"{entry.page_file} must define a function named page")

        out = _call_page(page_fn, params, request)
        if out is None:
            raise RouteError(f"page() in {entry.page_file} returned None instead of an element tree")
        if not isinstance(out, (Element, str, Markup)):
            raise RouteError(
                f"page() in {entry.page_file} must return an element tree, got {type(out).__name__}"
            )

        tree: Any = out
        for layout_module, layout_file in reversed(entry.layout_refs):
            layout_module_obj = _load_module(layout_module, layout_file)
            layout_fn = getattr(layout_module_obj, "layout", None)
            if layout_fn is None:
                raise RouteError(f"layout module {layout_module} must define a function named layout")
            tree = _call_layout(layout_fn, Markup(str(tree)), request)

        return render_html(tree)
    finally:
        koyo_meta.pop(token)


def _page_module(entry: RouteEntry) -> Any:
    return _import_page(entry.page_file, entry.page_module)


def module_has_fragment(entry: RouteEntry) -> bool:
    return callable(getattr(_page_module(entry), "fragment", None))


def module_has_page(entry: RouteEntry) -> bool:
    return callable(getattr(_page_module(entry), "page", None))


def render_fragment(entry: RouteEntry, params: dict[str, str], request=None) -> str:
    """Render a route's fragment export without any layout wrapping."""
    module = _page_module(entry)
    fragment_fn = getattr(module, "fragment", None)
    if fragment_fn is None:
        raise RouteError(f"{entry.page_file} does not define a function named fragment")
    out = _call_page(fragment_fn, params, request)
    if out is None:
        raise RouteError(
            f"fragment() in {entry.page_file} returned None instead of an element tree"
        )
    if not isinstance(out, (Element, str, Markup)):
        raise RouteError(
            f"fragment() in {entry.page_file} must return an element tree, "
            f"got {type(out).__name__}"
        )
    return render_html(out)