"""In-memory sessions for use_state.

A session is a random opaque token delivered as an httponly cookie named
koyo_session. Each session maps to a dict of string keyed state values that
components read and update with use_state.

The store is intentionally in-memory only for this pass: it does not
survive a server restart, it has no database or file backing, and it is
not shared between processes or workers. Sessions idle out after a timeout
(default 30 minutes of no requests), checked lazily on access, so no
background thread is needed.
"""

from __future__ import annotations

import secrets
import time

from starlette.middleware.base import BaseHTTPMiddleware

COOKIE_NAME = "koyo_session"
DEFAULT_TIMEOUT = 30 * 60


class SessionStore:
    """A dict of sessions keyed by opaque session id."""

    def __init__(self, timeout: float = DEFAULT_TIMEOUT) -> None:
        self.timeout = timeout
        self._sessions: dict[str, dict] = {}

    def get_or_create(self, sid: str) -> dict:
        now = time.time()
        session = self._sessions.get(sid)
        if session is None or now - session["last_seen"] > self.timeout:
            session = {"last_seen": now, "values": {}}
            self._sessions[sid] = session
        session["last_seen"] = now
        return session

    def get(self, sid: str, key: str, default=None):
        return self.get_or_create(sid)["values"].get(key, default)

    def set(self, sid: str, key: str, value) -> None:
        self.get_or_create(sid)["values"][key] = value

    def new_id(self) -> str:
        return secrets.token_urlsafe(32)


store = SessionStore()


class SessionMiddleware(BaseHTTPMiddleware):
    """Bind a session id to the request and hand it out as a cookie.

    The first request with no koyo_session cookie gets a fresh random id
    which is attached to the session store, stored on request.state for
    use_state and the internal state routes, and set as an httponly cookie
    on the response. Later requests read the cookie instead.
    """

    async def dispatch(self, request, call_next):
        sid = request.cookies.get(COOKIE_NAME)
        created = sid is None
        if created:
            sid = store.new_id()
        store.get_or_create(sid)
        request.state.koyo_session_id = sid
        response = await call_next(request)
        if created:
            response.set_cookie(
                COOKIE_NAME,
                sid,
                httponly=True,
                samesite="lax",
                path="/",
                max_age=DEFAULT_TIMEOUT,
            )
        return response


def get_session_id(request) -> str | None:
    """The session id the request middleware attached, if any."""
    return getattr(request.state, "koyo_session_id", None)