"""Starlette application construction for a Koyo project."""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

from starlette.applications import Starlette
from starlette.responses import HTMLResponse, Response
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from .html import Markup, a, body, div, h1, head, html, meta, p, pre, style, title
from .reload import current_token, dev_mode, inject_dev_reload
from .router import (
    RouteEntry,
    RouteError,
    module_has_fragment,
    module_has_page,
    render_fragment,
    render_route,
    reset_project_modules,
    scan_app_dir,
)
from .session import SessionMiddleware
from .state import STATE_URL_PREFIX, render_state_action

_ERROR_CSS = """\
body { margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
       background: #f1f5f9; color: #0f172a; }
.container { display: flex; min-height: 100vh; align-items: center; justify-content: center; padding: 1.5rem; }
.card { max-width: 40rem; width: 100%; background: #ffffff; border: 1px solid #e2e8f0;
        border-radius: 12px; padding: 2rem; box-shadow: 0 4px 12px rgba(15, 23, 42, 0.06); }
h1 { font-size: 1.5rem; margin: 0 0 0.5rem; }
p { color: #475569; line-height: 1.6; }
a { color: #4f46e5; }
.eyebrow { font-size: 0.75rem; letter-spacing: 0.08em; text-transform: uppercase; color: #ef4444;
           font-weight: 600; margin: 0 0 0.25rem; }
.message { margin: 0; }
.where { margin-top: 1rem; color: #b45309; font-family: ui-monospace, monospace;
         background: #fef3c7; border-radius: 8px; padding: 0.5rem 0.75rem; }
pre.trace { overflow-x: auto; background: #0f172a; color: #e2e8f0; padding: 1rem;
            border-radius: 8px; font-size: 0.8rem; line-height: 1.5; }
"""


def _error_page(status: int, heading: str, message: str, detail: str = "") -> str:
    children = [h1()[heading], p()[message]]
    if detail:
        children.append(pre(class_="trace")[detail])
    children.append(p(class_="home")[a(href="/")["Back to home"]])
    page = html(lang="en")[
        head()[
            meta(charset="utf-8"),
            title()[f"{status} {heading}"],
            style()[Markup(_ERROR_CSS)],
        ],
        body()[
            div(class_="container")[
                div(class_="card")[children]
            ]
        ],
    ]
    return "<!doctype html>\n" + str(page)


def _dev_error_page(exc: BaseException, route_path: str) -> str:
    tb = getattr(exc, "__traceback__", None)
    if tb is not None:
        trace_text = "".join(traceback.format_exception(type(exc), exc, tb))
    else:
        trace_text = f"{type(exc).__name__}: {exc}"
    frames = traceback.extract_tb(tb) if tb is not None else []
    location = ""
    if frames:
        frame = frames[-1]
        location = f"{frame.filename}:{frame.lineno} in {frame.name}"
    heading = type(exc).__name__
    message = str(exc) or heading
    children = [
        p(class_="eyebrow")[f"Error in {route_path}"],
        h1()[heading],
        p(class_="message")[message],
    ]
    if location:
        children.append(p(class_="where")[location])
    children.append(pre(class_="trace")[trace_text])
    children.append(p(class_="home")[a(href="/")["Back to home"]])
    page = html(lang="en")[
        head()[
            meta(charset="utf-8"),
            title()[f"{heading} on {route_path}"],
            style()[Markup(_ERROR_CSS)],
        ],
        body()[
            div(class_="container")[
                div(class_="card")[children]
            ]
        ],
    ]
    return "<!doctype html>\n" + str(page)


def _html_response(content: str, status_code: int = 200) -> HTMLResponse:
    return HTMLResponse(inject_dev_reload(content), status_code=status_code)


async def _not_found(request, exc) -> HTMLResponse:
    message = f"There is no route or public file for {request.url.path}."
    return _html_response(_error_page(404, "Not Found", message), 404)


def _request_wants_fragment(entry: RouteEntry, request) -> bool:
    if not module_has_fragment(entry):
        return False
    if not module_has_page(entry):
        return True
    return (request.headers.get("hx-request") or "").lower() == "true"


def _make_endpoint(entry: RouteEntry):
    async def endpoint(request):
        status = 200
        try:
            params = dict(request.path_params)
            if _request_wants_fragment(entry, request):
                return HTMLResponse(render_fragment(entry, params, request))
            return _html_response(render_route(entry, params, request))
        except RouteError as exc:
            if dev_mode():
                content = _dev_error_page(exc, entry.path)
                status = 500
            else:
                content = _error_page(
                    500, "Internal Server Error", f"Rendering {entry.path} failed."
                )
                status = 500
        except Exception:
            if dev_mode():
                content = _dev_error_page(sys.exc_info()[1], entry.path)
            else:
                content = _error_page(
                    500,
                    "Internal Server Error",
                    f"Rendering {entry.path} raised an unexpected error.",
                )
            status = 500
        return _html_response(content, status_code=status)

    return endpoint


async def _state_endpoint(request):
    token = request.path_params["token"]
    try:
        content, status = render_state_action(request, token)
        return HTMLResponse(content, status_code=status)
    except Exception:
        if dev_mode():
            content = _dev_error_page(sys.exc_info()[1], f"{STATE_URL_PREFIX}/{token}")
            status = 500
        else:
            content = _error_page(
                500,
                "Internal Server Error",
                "The session state update failed.",
            )
            status = 500
        return HTMLResponse(content, status_code=status)


async def _reload_probe(request) -> Response:
    project_dir = request.app.state.koyo_project_dir
    token = current_token(project_dir)
    since = request.query_params.get("since", "")
    headers = {"Cache-Control": "no-store", "X-Koyo-Token": token}
    if not since or since == token:
        return Response(status_code=204, headers=headers)
    return Response(token, status_code=200, headers=headers)


def build_app(project_dir: str | Path) -> Starlette:
    project_dir = Path(project_dir).resolve()
    root = str(project_dir)
    if sys.path and sys.path[0] != root:
        sys.path.insert(0, root)
    reset_project_modules()

    app_dir = project_dir / "app"
    public_dir = project_dir / "public"
    styles_dir = project_dir / "styles"

    public_dir.mkdir(parents=True, exist_ok=True)
    styles_dir.mkdir(parents=True, exist_ok=True)

    entries = scan_app_dir(app_dir)

    routes = [
        Route(
            f"{STATE_URL_PREFIX}/{{token}}",
            _state_endpoint,
            methods=["GET", "HEAD", "POST"],
        )
    ]
    if dev_mode():
        routes.append(Route("/__koyo-reload", _reload_probe))
    for entry in entries:
        routes.append(
            Route(
                entry.path,
                _make_endpoint(entry),
                methods=["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE"],
            )
        )
    if styles_dir.is_dir():
        routes.append(Mount("/styles", StaticFiles(directory=str(styles_dir))))
    if public_dir.is_dir():
        routes.append(Mount("/", StaticFiles(directory=str(public_dir))))

    application = Starlette(routes=routes, exception_handlers={404: _not_found})
    application.add_middleware(SessionMiddleware)
    application.state.koyo_project_dir = str(project_dir)
    return application