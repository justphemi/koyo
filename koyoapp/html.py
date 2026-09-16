"""Function based HTML component system for Koyo.

Components are plain Python functions that return an element tree built with
the tag factories exposed here. Elements support the ``el[children]`` syntax
for passing in child elements or text.
"""

from __future__ import annotations

import html as _stdlib_html
import sys
from collections.abc import Iterable, Mapping
from typing import Any, Callable

__all__ = ["Element", "Markup", "element", "raw", "render_html"]

_VOID_ELEMENTS = {
    "area", "base", "br", "col", "embed", "hr", "img",
    "input", "link", "meta", "param", "source", "track", "wbr",
}

_ATTR_ALIASES = {"class_": "class", "for_": "for"}


class Markup:
    """A string that is rendered without HTML escaping."""

    __slots__ = ("_value",)

    def __init__(self, value: Any) -> None:
        self._value = value

    def __str__(self) -> str:
        return str(self._value)


def raw(value: Any) -> Markup:
    """Wrap a value so it renders as raw, unescaped HTML."""
    return Markup(value)


class Element:
    """A single HTML element with attributes and children."""

    __slots__ = ("tag", "attrs", "children")

    def __init__(
        self,
        tag: str,
        attrs: Mapping[str, Any] | None = None,
        children: Iterable[Any] | None = None,
    ) -> None:
        self.tag = tag
        self.attrs = dict(attrs or {})
        self.children: list[Any] = []
        if children is not None:
            self.children.extend(children)

    def __getitem__(self, children: Any) -> "Element":
        if isinstance(children, (str, bytes, Markup, Element)) or children is None:
            self.children.append(children)
        elif isinstance(children, Mapping):
            self.children.append(children)
        else:
            self.children.extend(children)
        return self

    def render(self) -> str:
        return _render_element(self)

    def __str__(self) -> str:
        return self.render()

    def __repr__(self) -> str:
        return f"<Element {self.tag}>"


def _attr_name(name: str) -> str:
    name = _ATTR_ALIASES.get(name, name)
    if "_" in name and name.startswith(("hx_", "data_", "aria_")):
        return name.replace("_", "-")
    return name


def _render_element(el: Element) -> str:
    parts: list[str] = ["<", el.tag]
    for name, value in el.attrs.items():
        name = _attr_name(name)
        if value is None or value is False:
            continue
        if value is True:
            parts.extend([" ", name])
            continue
        parts.extend([" ", name, '="', _stdlib_html.escape(str(value), quote=True), '"'])
    parts.append(">")
    if el.tag not in _VOID_ELEMENTS:
        parts.append(_render_children(el.children))
        parts.extend(["</", el.tag, ">"])
    return "".join(parts)


def _render_children(children: Iterable[Any]) -> str:
    parts: list[str] = []
    for child in children:
        _render_child(parts, child)
    return "".join(parts)


def _render_child(parts: list[str], child: Any) -> None:
    if child is None:
        return
    if isinstance(child, Element):
        parts.append(child.render())
    elif isinstance(child, Markup):
        parts.append(str(child))
    elif isinstance(child, (str, bytes)):
        parts.append(_stdlib_html.escape(str(child), quote=False))
    elif isinstance(child, Mapping):
        return
    elif isinstance(child, Iterable):
        parts.append(_render_children(child))
    else:
        parts.append(_stdlib_html.escape(str(child), quote=False))


_TAGS = [
    "a", "abbr", "address", "area", "article", "aside", "audio",
    "b", "base", "bdi", "bdo", "blockquote", "body", "br", "button",
    "canvas", "caption", "cite", "code", "col", "colgroup",
    "data", "datalist", "dd", "del", "details", "dfn", "dialog", "div", "dl", "dt",
    "em", "embed",
    "fieldset", "figcaption", "figure", "footer", "form",
    "h1", "h2", "h3", "h4", "h5", "h6", "head", "header", "hgroup", "hr", "html",
    "i", "iframe", "img", "input", "ins",
    "kbd", "label", "legend", "li", "link",
    "main", "map", "mark", "menu", "meta", "meter",
    "nav", "noscript",
    "object", "ol", "optgroup", "option", "output",
    "p", "param", "picture", "pre", "progress",
    "q",
    "rp", "rt", "ruby",
    "s", "samp", "script", "section", "select", "slot", "small", "source", "span",
    "strong", "style", "sub", "summary", "sup",
    "table", "tbody", "td", "template", "textarea", "tfoot", "th", "thead", "time", "title", "tr", "track",
    "u", "ul",
    "var", "video",
    "wbr",
]


def _make_tag_factory(tag: str) -> Callable[..., Element]:
    def factory(**attrs: Any) -> Element:
        return Element(tag, attrs)

    factory.__name__ = tag
    factory.__qualname__ = tag
    return factory


def element(tag: str, **attrs: Any) -> Element:
    """Create an element for a single tag name."""
    return Element(tag, attrs)


def render_html(tree: Any) -> str:
    """Render a tree to a full HTML document string."""
    if isinstance(tree, Element) and tree.tag == "html":
        return "<!doctype html>\n" + str(tree)
    return str(tree)


def _populate_tags() -> None:
    module = sys.modules[__name__]
    for tag in _TAGS:
        setattr(module, tag, _make_tag_factory(tag))


def __getattr__(name: str) -> Callable[..., Element]:
    """Provide a factory for any tag name, known or custom."""
    return _make_tag_factory(name)


_populate_tags()