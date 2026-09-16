"""use_state: session scoped component state driven by htmx.

A component function that takes ``request`` as its only argument can read
and mutate per session state without a dedicated route file. use_state
returns the current value and a small action object. The action methods
return the htmx attributes (an hx_post pointing at an automatically
registered internal route) needed to update the value and swap in a fresh
render of the calling component.

When use_state runs outside a request context, for example during the
production build's static prerender pass, it falls back to the initial
value and a no-op action so rendering never crashes and produces usable
static HTML.
"""

from __future__ import annotations

import base64
import sys
from importlib import import_module

from . import session as koyo_session

STATE_URL_PREFIX = "/__koyo_state"


def _token_for(module: str, name: str, key: str) -> str:
    raw = f"{module}::{name}::{key}"
    return base64.urlsafe_b64encode(raw.encode("utf-8")).rstrip(b"=").decode("ascii")


def _decode_token(token: str) -> tuple[str, str, str]:
    padded = token + "=" * (-len(token) % 4)
    raw = base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8")
    module, name, key = raw.split("::", 2)
    return module, name, key


def _resolve(module: str, name: str):
    obj = import_module(module)
    for part in name.split("."):
        obj = getattr(obj, part)
    return obj


class _StateAction:
    """Builds the htmx attributes for mutating one session backed value."""

    def __init__(self, token: str) -> None:
        self._token = token

    def increment(self, by: int = 1) -> dict:
        return {
            "hx_post": f"{STATE_URL_PREFIX}/{self._token}?op=increment&by={int(by)}",
        }

    def set(self, value) -> dict:
        return {
            "hx_post": f"{STATE_URL_PREFIX}/{self._token}?op=set&value={int(value)}",
        }


class _NoopAction:
    """Renders no htmx attributes when there is no session context."""

    def increment(self, by: int = 1) -> dict:
        return {}

    def set(self, value) -> dict:
        return {}


def use_state(request, key: str, initial=0):
    """Read the current value for key and return it with an action object.

    The component calling use_state is identified by its module and
    function name via the call stack, which is what the generated action
    route re-renders after applying an update.
    """
    if request is None:
        return initial, _NoopAction()
    frame = sys._getframe(1)
    module = frame.f_globals.get("__name__", "")
    name = frame.f_code.co_name
    sid = koyo_session.get_session_id(request) or koyo_session.store.new_id()
    value = koyo_session.store.get(sid, key, initial)
    return value, _StateAction(_token_for(module, name, key))


def render_state_action(request, token: str) -> tuple[str, int]:
    """Apply the requested update and re-render the calling component.

    Returns the freshly rendered component HTML and a status code. The
    update operation and its arguments arrive on the query string, which is
    how the auto generated hx_post attributes send them.
    """
    module, name, key = _decode_token(token)
    fn = _resolve(module, name)
    sid = koyo_session.get_session_id(request)
    op = request.query_params.get("op")
    if op == "increment":
        by = int(request.query_params.get("by", "1"))
        value = koyo_session.store.get(sid, key, 0) + by
        koyo_session.store.set(sid, key, value)
    elif op == "set":
        value = int(request.query_params.get("value", "0"))
        koyo_session.store.set(sid, key, value)
    else:
        return "unknown state operation", 400
    return str(fn(request)), 200