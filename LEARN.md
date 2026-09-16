# LEARN.md

A deep technical reference for koyoapp v0.4.0. This document explains how
every part of the framework is built, how the pieces connect, and where the
boundaries are. It is written so you can defend having built this yourself.

---

## Table of contents

1. [What koyoapp is](#what-koyoapp-is)
2. [Architecture overview](#architecture-overview)
3. [Module by module](#module-by-module)
4. [The request lifecycle](#the-request-lifecycle)
5. [File-based routing](#file-based-routing)
6. [Layouts](#layouts)
7. [The HTML builder](#the-html-builder)
8. [Session state with use_state](#session-state-with-use_state)
9. [Metadata and head tags](#metadata-and-head-tags)
10. [Live reload](#live-reload)
11. [The dev server](#the-dev-server)
12. [The production build](#the-production-build)
13. [CLI commands](#cli-commands)
14. [Dependency management](#dependency-management)
15. [Tailwind CSS integration](#tailwind-css-integration)
16. [Network detection](#network-detection)
17. [Logging](#logging)
18. [Scaffolding](#scaffolding)
19. [Deploy files](#deploy-files)
20. [The CLI architecture](#the-cli-architecture)
21. [Error handling](#error-handling)
22. [What it CAN do](#what-it-can-do)
23. [What it CANNOT do](#what-it-cannot-do)
24. [Key design decisions](#key-design-decisions)

---

## What koyoapp is

koyoapp is a Python web framework that brings the Next.js app directory
model (file-based routing, nested layouts, reusable components, hot
reloading) to a plain Python web server. It is a single pip-installable
package with zero required external services. There is no database, no
JavaScript build step, no Node.js requirement (Tailwind is optional and
auto-installs if npm is present), and no Docker requirement.

The framework sits on top of **Starlette** (ASGI) and **uvicorn**. The
HTML is built with a function-based element DSL in Python, not templates.
Interactivity is powered by **htmx**, which ships in the scaffold. Session
state is in-memory only. The entire framework is around 20 Python files
totaling roughly 3,000 lines of implementation code.

Current version: **0.4.0** (defined in `koyoapp/__init__.py` and
`pyproject.toml`).

---

## Architecture overview

```
koyoapp/
  __init__.py          version string
  __main__.py          entry for `python -m koyoapp`
  cli.py               typer CLI (create, dev, build, add, remove, install, upgrade)
  app.py               Starlette app construction, error pages, route endpoints
  router.py            file-based route scanning, layout chaining, rendering
  html.py              element DSL (Element class, tag factories, render)
  session.py           in-memory session store, cookie middleware
  state.py             use_state hook, htmx attribute generation, state route
  meta.py              ContextVar-based per-route metadata, head tag generation
  config.py            importlib-based koyo.config.py loader
  build.py             production prerender (static routes only)
  dev.py               dev server: watchfiles, tailwind, server process, free port
  reload.py            token bump, reload probe, live reload JS serving
  serve.py             uvicorn entry point (imports build_app at module level)
  scaffold.py          project scaffolding, placeholder generation
  templates.py         all scaffold file contents
  deps.py              pyproject.toml management, pip wrapper
  venv.py              .venv creation
  tailwind.py          tailwindcss detection, compilation, watch mode
  net.py               LAN IP detection
  log.py               quiet/verbose logging helpers
  _placeholders.py     pure-Python PNG and ICO generation
  assets/              favicon.ico, logo.png, icon.png, htmx.min.js, etc.
  vendor/              morphdom.min.js, koyo-live-reload.js
```

Project structure created by `koyoapp create`:

```
myapp/
  app/
    page.py            homepage
    layout.py          root layout (html/head/body skeleton)
    blog/
      [slug]/
        page.py        dynamic route
      layout.py        nested layout
  components/          reusable functions, watched by dev server
  public/              static files served at root
  styles/
    globals.css        Tailwind entry point
    koyo.css           compiled output (generated)
  koyo.config.py       PORT, PROJECT_NAME
  pyproject.toml       project metadata, dependencies
  tailwind.config.js   Tailwind config
  package.json         tailwindcss devDependency
  Procfile             deploy entry point
  requirements.txt     pinned koyoapp version for deploy
  .railwayignore       keeps .venv out of deploy uploads
  .gitignore
  README.md
```

---

## Module by module

### app.py (240 lines)

This is the core. `build_app(project_dir)` constructs a Starlette ASGI
application.

**What build_app does:**

1. Adds `project_dir` to `sys.path[0]` so that `from components.site import badge` works.
2. Calls `reset_project_modules()` to clear any stale page/layout modules from a previous project (important when reloading config or switching projects).
3. Creates `app/`, `public/`, and `styles/` directories if they do not exist.
4. Calls `scan_app_dir(app_dir)` to get the route table (list of `RouteEntry` objects).
5. Registers three internal routes:
   - `POST /__koyo_state/{token}` -- session state mutations via use_state
   - `GET /__koyo-reload` -- the dev reload probe (token comparison)
   - `GET /__koyo-live-reload.js` -- serves the concatenated morphdom + live-reload JS
6. For each `RouteEntry`, creates a Starlette `Route` supporting GET, HEAD, POST, PUT, PATCH, DELETE.
7. Mounts `/styles` as a `StaticFiles` directory, and `/` as a `StaticFiles` directory for `public/`.
8. Adds the `SessionMiddleware` (from session.py).
9. Stores the project path on `application.state.koyo_project_dir`.

**The endpoint factory `_make_endpoint(entry)`** creates a closure that:
- Extracts path params from the request.
- If the request is an htmx request (`hx-request: true` header) and the page module exports a `fragment` function, it renders only the fragment (no layout wrapping). This is the htmx partial rendering path.
- Otherwise calls `render_route(entry, params, request)` for a full page render.
- Catches `RouteError` and generic exceptions. In dev mode, renders a detailed error page with file location and full traceback. In production, renders a generic 500 page.

**Error pages** use the same `koyoapp.html` DSL as normal pages. The `_ERROR_CSS` string is embedded inline. The dev error page (`_dev_error_page`) shows the exception type, message, file location, and full traceback in a monospace pre block.

**The reload probe** (`_reload_probe`):
- Reads the current token from `.koyo/reload-token` (its mtime_ns).
- Compares it to the `since` query parameter.
- Returns 204 (no change) if they match, or 200 (new token) if they differ.
- Always sets `X-Koyo-Token` and `Cache-Control: no-store`.

**The live reload script** (`_live_reload_script`):
- Returns `live_reload_js()` which is the concatenated morphdom.min.js + koyo-live-reload.js.
- Cached with `@functools.lru_cache(maxsize=1)` in reload.py.

---

### router.py (238 lines)

File-based routing modeled on the Next.js app directory.

**Route scanning (`scan_app_dir`):**

1. Recursively globs for `page.py` files under `app/`.
2. For each `page.py`, computes the segments (folder parts relative to `app/`).
3. Walks upward from the page directory to `app/` root, collecting any `layout.py` files in ancestor directories. These are stored as `layout_refs` on the `RouteEntry`.
4. Builds the URL path: static segments become literal path parts, `[slug]` segments become `{slug}` (Starlette's path param syntax).
5. The module name is computed as `__koyo_route__.<sanitized_segments>.page` (or `.layout`). This reserved namespace keeps page/layout modules separate from component modules.

**RouteEntry** stores:
- `page_file`: the Path to `page.py`
- `segments`: tuple of folder parts (e.g., `("blog", "[slug]")`)
- `layout_refs`: list of `(module_name, layout_file_path)` pairs from root to nearest
- `page_module`: the importlib module name
- `path`: the Starlette route path (e.g., `/blog/{slug}`)
- `params`: list of parameter names (e.g., `["slug"]`)
- `is_dynamic`: True if any params exist

**Module loading** (`_load_module`):
- Uses `importlib.util.spec_from_file_location` to load page/layout modules from their file paths.
- Stores them in `sys.modules` so subsequent imports (like `from components.site import badge`) resolve correctly within the page.
- On load failure, removes the module from `sys.modules` and raises `RouteError`.

**Module cache** (`clear_module_cache`):
- Drops all modules whose names start with `__koyo_route__`.
- Called implicitly at app build time via `reset_project_modules()`.
- This is what makes hot reload work: when a file changes, the dev server bumps the token and restarts uvicorn, which calls `build_app` again, which calls `reset_project_modules()`, which clears all cached page/layout modules, so the next request re-reads them from disk.

**Page rendering** (`render_route`):
1. Merges metadata from the page and all ancestor layouts (page wins).
2. Pushes the merged metadata into a `ContextVar` (meta.py) so the root layout can call `metadata_tags()`.
3. Imports the page module and calls its `page()` function, passing path params and optionally `request` (if the function signature includes it).
4. Wraps the page output in each layout from innermost to outermost (using `reversed(entry.layout_refs)`). Each layout receives `children` (the inner HTML as a `Markup` string) and optionally `request`.
5. Calls `render_html(tree)` to produce the final `<!doctype html>` string.
6. Pops the metadata ContextVar in a `finally` block.

**Fragment rendering** (`render_fragment`):
- If a page module exports a `fragment()` function (in addition to `page()`), htmx requests to that route will render only the fragment output, without any layout wrapping.
- This is how htmx partial updates work: the full page loads on first visit, but subsequent htmx requests get just the fragment HTML, which htmx swaps into the DOM.
- The check is in `app.py:_request_wants_fragment`: it returns True if the module has a fragment export AND either (a) the module does NOT have a page export, or (b) the request has `hx-request: true`.

---

### html.py (191 lines)

A function-based HTML component system. No templates, no JSX, no build step.

**Element class:**
- Stores `tag`, `attrs` (dict), and `children` (list).
- The `el[children]` syntax calls `__getitem__`, which appends children and returns the element. This enables the fluent builder pattern: `div(class_="foo")[p()["Hello"], span()["World"]]`.
- `__str__` calls `render()` which calls `_render_element`.

**Tag factories:**
- Every standard HTML tag (153 tags listed in `_TAGS`) has a factory function generated by `_make_tag_factory` and set as a module attribute.
- Custom tags also work: `__getattr__` on the module catches any unknown name and returns a factory for it.
- A factory accepts positional children and keyword attributes, creates an `Element`, and returns it.

**Rendering** (`_render_element`):
- Iterates over attrs. Attribute name aliases: `class_` and `cls` become `class`, `for_` becomes `for`. Underscores in `hx_*`, `data_*`, and `aria_*` prefixes become hyphens (e.g., `hx_post` becomes `hx-post`, `data_test` becomes `data-test`).
- `None` and `False` attrs are skipped. `True` attrs render as a bare attribute (e.g., `disabled`).
- Children are rendered by `_render_children` / `_render_child`:
  - `None` is skipped.
  - `Element` calls its own `.render()`.
  - `Markup` is inserted raw (no escaping).
  - `str` / `bytes` are HTML-escaped with `html.escape`.
  - `Mapping` is silently skipped (a quirk, not a feature).
  - Other iterables are recursed into.
  - Anything else is converted to string and escaped.

**Markup class:**
- Wraps a string so it renders without escaping. Created by the `raw()` helper.
- Used when you need to inject raw HTML (e.g., `style()[Markup(_ERROR_CSS)]`).

**render_html:**
- If the root element is `<html>`, prepends `<!doctype html>\n`.
- Otherwise returns `str(tree)`.

**Void elements:** The 14 HTML void elements (area, br, col, embed, hr, img, input, link, meta, etc.) are self-closed and do not get closing tags.

---

### session.py (85 lines)

In-memory session store for use_state.

**SessionStore:**
- A dict of `{session_id: {"last_seen": timestamp, "values": {key: value}}}`.
- Sessions idle out after 30 minutes of no requests (`DEFAULT_TIMEOUT = 30 * 60`).
- Timeout is checked lazily on access (no background thread).
- `get_or_create` creates a new session dict if the ID is missing or expired.
- `new_id` generates a `secrets.token_urlsafe(32)` string.

**SessionMiddleware:**
- A Starlette `BaseHTTPMiddleware`.
- On every request, reads the `koyo_session` cookie.
- If no cookie exists, generates a new session ID and sets it as an httponly, samesite=lax cookie with `max_age=DEFAULT_TIMEOUT`.
- Stores the session ID on `request.state.koyo_session_id`.

**Global store instance:** `store = SessionStore()` at module level. This is the single in-memory store. It does not survive server restarts, is not shared across processes, and has no database backing.

**Critical limitation:** The store is a Python dict in a single process. If you run multiple uvicorn workers, each has its own store. Two visitors hitting different workers will have different session data. This is by design for v0.4.0 -- the framework is a single-replica, single-process system.

---

### state.py (110 lines)

Session-scoped component state driven by htmx. This is the closest thing koyoapp has to React hooks.

**use_state(request, key, initial=0):**

1. If `request is None` (e.g., during a build prerender), returns `(initial, _NoopAction())`. The NoopAction's methods return empty dicts, so no htmx attributes are generated and the static HTML just shows the initial value.
2. Otherwise, uses `sys._getframe(1)` to introspect the caller:
   - Gets the caller's `__name__` (the module name, e.g., `components.counter`).
   - Gets the caller's `co_name` (the function name, e.g., `visit_counter`).
3. Generates a base64url token encoding `module::name::key` (e.g., `components.counter::visit_counter::visit_count`).
4. Reads the current value from the session store using the session ID from the request.
5. Returns `(current_value, _StateAction(token))`.

**_StateAction(token):**
- `increment(by=1)` returns `{"hx_post": "/__koyo_state/{token}?op=increment&by={by}"}`.
- `set(value)` returns `{"hx_post": "/__koyo_state/{token}?op=set&value={value}"}`.

When the user writes `button(**count_action.increment(by=1), hx_target="#visit-card", hx_swap="outerHTML")`, the `**count_action.increment(by=1)` unpacks the hx_post attribute into the element's kwargs. This is the magic: the button's hx-post URL is auto-generated to point at the internal state route.

**render_state_action(request, token):**
1. Decodes the token back to `module`, `name`, `key`.
2. Uses `_resolve(module, name)` which does `importlib.import_module(module)` then `getattr` chain to get the actual function.
3. Reads the `op` query parameter: `increment` or `set`.
4. Updates the session store.
5. Re-renders the component by calling `fn(request)` (the original page/component function).
6. Returns the freshly rendered HTML string.

This is the full cycle:
- User clicks button
- htmx POSTs to `/__koyo_state/{token}?op=increment&by=1`
- Server decodes token, updates session store, re-renders the component
- htmx swaps the response HTML into the DOM (targeted by hx_target)

The component function is re-invoked with the updated session value, so the HTML it returns reflects the new count.

---

### meta.py (51 lines)

Per-route metadata for `<title>`, `<meta description>`, and `<meta og:image>`.

Uses a `ContextVar` (`_METADATA`) to hold the currently active metadata dict during a request. This is safe for async because ContextVars are request-scoped.

- `push(metadata)` sets the value and returns a reset token.
- `pop(token)` resets to the previous value.
- `current()` returns the current metadata dict.
- `metadata_tags()` reads `current()` and generates the appropriate HTML elements: `title()`, `meta(name="description")`, `meta(property="og:image")`.

The flow: `render_route` calls `merge_metadata(entry)` which walks the page and all ancestor layouts collecting `metadata` dicts, then pushes the merged dict before rendering and pops it after.

Supported keys: `title`, `description`, `og_image`. Any other keys in the dict are ignored.

---

### config.py (31 lines)

Loads `koyo.config.py` from the project root using `importlib.util`.

- Finds the file, creates a module spec, executes it.
- Collects all public (non-underscore) attributes that are str, int, float, or bool.
- Returns them as a dict.
- Currently only `PORT` and `PROJECT_NAME` are used, but the system is open-ended.

Silently returns `{}` if the file does not exist or fails to load.

---

### build.py (82 lines)

Production build. Prerenders static routes into `.koyo/build/site`.

**What run_build does:**

1. Calls `ensure_project_dir` to verify `koyo.config.py` exists.
2. Adds the project root to `sys.path`.
3. Redirects bytecode cache to `.koyo/pycache` via `apply_pycache_prefix`.
4. Creates `.koyo/build/site/` directory.
5. Copies `public/` into `site/` root.
6. Copies `styles/` into `site/styles/`.
7. Runs Tailwind CSS in production mode (minified) to `site/styles/koyo.css`.
8. Calls `scan_app_dir` to get the route table.
9. Separates static routes from dynamic routes.
10. For each static route, calls `render_route(entry, {})` with empty params and writes the result to `site/{path}/index.html`.
11. Prints a notice listing any dynamic routes that were skipped.

**What it produces:** A complete static website in `.koyo/build/site/` with:
- `index.html` (and nested `*/index.html` for each route)
- `styles/koyo.css` (compiled Tailwind)
- All files from `public/` (favicon, icons, JS, etc.)

**What it skips:** Dynamic routes (those with `[param]` segments). These cannot be prerendered because the param values are unknown at build time. They must be served by the running server.

---

### serve.py (11 lines)

The uvicorn entry point. Two lines of real code:

```python
project_dir = os.environ.get("KOYO_PROJECT_DIR") or "."
app = build_app(project_dir)
```

When uvicorn loads `koyoapp.serve:app`, it executes this module, which calls `build_app` and assigns the result to `app`. The `KOYO_PROJECT_DIR` environment variable is set by the dev server (`dev.py`) or can be set manually for production.

This is why the Procfile uses `python -m uvicorn koyoapp.serve:app`: it needs to load this module to get the `app` object.

---

### dev.py (225 lines)

The dev server orchestrator. This is the most complex module.

**run_dev flow:**

1. Resolves the project directory.
2. Applies `.koyo/pycache` bytecode cache prefix.
3. Loads `koyo.config.py` for the PORT setting.
4. Resolves the free port: if the requested port is in use, scans up to 200 ports higher. Logs "Port X is already in use, using Y instead" if it shifts.
5. Creates `app/`, `public/`, `styles/` directories.
6. Ensures Tailwind is present (auto-installs via npm if needed), compiles it once, then starts Tailwind in watch mode as a subprocess.
7. Bumps the reload token (writes current timestamp to `.koyo/reload-token`).
8. Spawns the uvicorn server as a subprocess with `KOYO_DEV=1` and `KOYO_PROJECT_DIR` set.
9. Waits up to 10 seconds for the server to respond on the port.
10. Prints the ASCII logo, local URL, LAN URL (if detectable), and startup time.
11. Enters a watchfiles loop watching `app/`, `public/`, `styles/`, `koyo.config.py`, `tailwind.config.js`, and `components/` (if it exists).
12. On any file change:
    - Drops tailwind output changes (to avoid infinite loops).
    - Reports changed files.
    - If the port was not explicitly set, checks if PORT changed in config and re-resolves.
    - Stops the old uvicorn process.
    - Bumps the token again.
    - Spawns a new uvicorn process.
13. On KeyboardInterrupt, stops both processes cleanly.

**Server subprocess:**
- Command: `sys.executable -m uvicorn koyoapp.serve:app --host {host} --port {port}`
- Environment: `KOYO_PROJECT_DIR`, `KOYO_DEV=1`, `PYTHONPYCACHEPREFIX` (for .koyo/pycache).
- Output: captured to `.koyo/dev-server.log` unless `--verbose` is set, in which case it streams to stdout.

**Free port logic:**
- `resolve_free_port(port, host="127.0.0.1", timeout=0.3)`: tries to `socket.create_connection` to the port. If it connects (port in use), scans upward.
- `_port_in_use` returns True if `create_connection` succeeds.
- Max scan range: 200 ports above the requested port.
- Applied at startup AND during config reload (if PORT changes in koyo.config.py).

---

### reload.py (91 lines)

Dev reload coordination.

**Token system:**
- `.koyo/reload-token` is a file whose content is `time.time_ns()`.
- `current_token(project_dir)` reads `path.stat().st_mtime_ns` (does not even read the file contents).
- `bump_token(project_dir)` writes the current nanosecond timestamp.

The dev server calls `bump_token` whenever a file changes. The reload probe endpoint compares the current token to what the client last saw.

**inject_dev_reload(content):**
- Only runs when `KOYO_DEV=1` (checked via `dev_mode()`).
- Injects `<script id="koyo-reload-script" src="/__koyo-live-reload.js"></script>` before `</body>`.
- Skips injection if the script is already present (idempotent).

**live_reload_js():**
- Concatenates `vendor/morphdom.min.js` + `vendor/koyo-live-reload.js`.
- Cached with `@functools.lru_cache(maxsize=1)` so the concatenation happens once per process.

---

### The live reload client (vendor/koyo-live-reload.js, 145 lines)

The client-side live reload system. This is vanilla JavaScript, no build step.

**How it works:**

1. On page load, polls `/__koyo-reload?since={token}` every 700ms.
2. The server returns 204 (no change) or 200 (change happened) with the new token in `X-Koyo-Token`.
3. On change, fetches the full current page HTML from the current URL.
4. Uses **morphdom** to diff the new HTML against the current DOM and surgically update only what changed.
5. After morphing, refreshes stylesheet `href` attributes (appends `?koyo={timestamp}` bust) so CSS updates appear immediately.

**What morphdom preserves across the morph:**

- **Form state:** Snapshots all inputs, textareas, and selects by ID before morphing, restores values after. This means typed text, checked boxes, and selected dropdowns survive a live reload.
- **Active element focus:** Saves `document.activeElement`'s ID, value, checked state, and selection range (for text inputs). Restores focus and cursor position after morph.
- **The reload script itself:** The `<script id="koyo-reload-script">` element is never added or removed by morphdom (`onBeforeNodeAdded` returns false for SCRIPT tags, `onBeforeElUpdated` returns false for the reload script).
- **Other script tags:** All SCRIPT tags are excluded from both addition and updating during morph.
- **New htmx-processed nodes:** When morphdom adds new DOM nodes, it calls `htmx.process(node)` so htmx attributes on the new nodes are wired up immediately.

**Why this matters:** The live reload is a full-page morph, not a simple location.reload(). This means:
- Scroll position is preserved (morphdom does not touch the scroll container).
- CSS transitions and animations continue without interruption.
- Typed form data is not lost.
- The page does not flash white.
- The experience feels like a React hot-reload, not a traditional page refresh.

---

### tailwind.py (86 lines)

Tailwind CSS integration.

**ensure_tailwind_present(project_dir):**
1. Checks for `node_modules/.bin/tailwindcss` (locally installed).
2. If not found, checks for `npm` on PATH and runs `npm install --no-fund --no-audit` in the project directory. This auto-installs tailwindcss from package.json.
3. Checks again for the local binary.
4. Falls back to checking for a system-wide `tailwindcss` binary.
5. Returns the path to the binary, or None.

**compile_tailwind:** Runs `tailwindcss -i styles/globals.css -o styles/koyo.css -c tailwind.config.js`.

**compile_tailwind_prod:** Same but with `--minify`.

**start_tailwind_watch:** Starts Tailwind in `--watch` mode as a subprocess. Output goes to `.koyo/tailwind.log` (or stdout in verbose mode).

---

### net.py (35 lines)

LAN IP detection for the dev server startup message.

Uses a UDP socket trick: `socket.connect(("8.8.8.8", 80))` on a SOCK_DGRAM socket. This does not send any packets; it only tells the kernel which local interface would route to that destination. `getsockname()` then returns the local IP address of that interface.

Validates the result looks like an IPv4 address (`inet_aton` + exactly 3 dots).

Returns None if the detection fails (e.g., no network interface).

---

### log.py (70 lines)

Shared logging for the CLI. Two modes:
- **Quiet (default):** Subprocess output is captured and only shown on failure.
- **Verbose (`--verbose`):** Subprocess output streams to stdout/stderr as-is.

Functions: `info`, `success`, `warn`, `error` (print to stdout/stderr). `run(command, cwd)` runs a subprocess with `capture_output=True` and conditionally echoes output. `open_log(directory, name)` opens an append-mode file handle for long-running subprocess output (used for the dev server and Tailwind logs).

---

### scaffold.py (76 lines)

Project scaffolding for `koyoapp create`.

1. Resolves the target directory.
2. Refuses to scaffold if `app/` or `koyo.config.py` already exist.
3. Creates all files from `templates.FILES`, replacing `__PROJECT_NAME__` and `__KOYO_VERSION__` placeholders.
4. Copies bundled assets from `koyoapp/assets/` into `public/`. If the assets directory is empty (not installed from PyPI), generates placeholder PNGs and ICO using `_placeholders.py`.
5. Creates a `.venv` using `sys.executable -m venv`.

---

### templates.py (518 lines)

All scaffold file contents as a dict of `{relative_path: content_string}`.

Key files:
- `app/layout.py`: Root layout with html/head/body, metadata_tags(), site footer, dark mode classes.
- `app/page.py`: Homepage that calls `hero(request)` from components.
- `components/landing.py`: Hero section with animated logo, headline, CTA button, and visit counter.
- `components/counter.py`: Working use_state counter example (Clicks: N + button).
- `components/site.py`: Footer with documentation link.
- `public/theme.js`: Inline script that applies dark/light theme from localStorage before first paint.
- `styles/globals.css`: Tailwind directives plus keyframe animations.
- `koyo.config.py`: PORT and PROJECT_NAME defaults.
- `pyproject.toml`: Project metadata with `koyoapp>=0.1.0` dependency.
- `tailwind.config.js`: Dark mode class-based, brand color palette, content paths.
- `package.json`: tailwindcss devDependency.
- `Procfile`, `requirements.txt`, `.railwayignore`: Deploy files.
- `.gitignore`, `README.md`.

The `__KOYO_VERSION__` placeholder is replaced at scaffold time with the running koyoapp version, so `requirements.txt` always pins the exact version used to create the project.

---

### _placeholders.py (56 lines)

Pure-Python PNG and ICO file generation with zero external dependencies.

- `make_png(width, height, rgb)`: Creates a minimal valid PNG file by building the IHDR chunk, compressing raw scanlines with `zlib.compress`, and wrapping in PNG chunks with CRC checksums.
- `make_ico(entries)`: Creates a valid ICO file with a header, directory entries, and embedded PNG payloads.
- `make_favicon_ico()`: Generates a multi-size ICO with 16x16, 32x32, 48x48, and 256x256 PNGs.
- Color constants: `LOGO_RGB = (79, 70, 229)` (indigo), `ICON_RGB = (15, 118, 110)` (teal), `FAVICON_RGB = (30, 27, 75)` (dark blue).

This is used as a fallback when the bundled `assets/` directory is not available (e.g., when the package was installed from PyPI and the assets were not included in the wheel).

---

### deps.py (347 lines)

Dependency management: `koyoapp add`, `remove`, `install`, `upgrade`.

**Core operations:**
- `add(project_dir, packages, dev)`: Runs `pip install` for the packages, then updates `pyproject.toml` with the exact installed versions. Supports both main and dev (optional-dependencies) sections.
- `remove(project_dir, packages)`: Removes from `pyproject.toml` and runs `pip uninstall`.
- `install(project_dir, clean, no_dev)`: Creates `.venv` if needed, reads all dependencies from `pyproject.toml`, runs `pip install` for them all. Supports `--clean` (delete and recreate .venv) and `--no-dev` (skip dev dependencies).
- `upgrade(project_dir, version)`: Upgrades koyoapp to latest or a specific version, then pins it in `pyproject.toml`.

**pyproject.toml management:**
- Uses `tomlkit` to preserve formatting and comments when editing.
- `_upsert` deduplicates by package name (case-insensitive, hyphens normalized to underscores).
- `_split_requirement` parses `package[extras]>=1.0` into `(base, extras, spec)`.
- `ensure_project_dir` checks for `koyo.config.py` as the project marker.

**Pip wrapper** (`run_pip`):
- Runs the project venv's pip (not the system pip).
- Captures output by default; shows it only on failure or in verbose mode.

---

### venv.py (17 lines)

Single function: `create_venv(project_dir)` runs `sys.executable -m venv {project_dir}/.venv`. Returns True on success.

Uses the current Python interpreter, so the venv inherits the same Python version.

---

### cli.py (171 lines)

The `koyoapp` CLI, built with **typer**.

**Commands:**
- `koyoapp create <target>`: Scaffolds a new project.
- `koyoapp dev [--port] [--host] [--verbose]`: Runs the dev server.
- `koyoapp build`: Prerenders static routes.
- `koyoapp add <packages> [--dev] [--verbose]`: Installs and records dependencies.
- `koyoapp remove <packages> [--verbose]`: Uninstalls and removes from pyproject.toml.
- `koyoapp install [--clean] [--no-dev] [--verbose]`: Installs all dependencies from pyproject.toml.
- `koyoapp upgrade [version] [--verbose]`: Upgrades koyoapp itself.
- `koyoapp --version` / `-v`: Prints version and exits.

`invoke_without_command=True` on the typer app means running just `koyoapp` with no subcommand shows the help text.

`__main__.py` enables `python -m koyoapp` as an alternative to `koyoapp`.

---

## The request lifecycle

1. **Incoming request** hits the Starlette ASGI app.
2. **SessionMiddleware** reads or creates the `koyo_session` cookie, attaches the session ID to `request.state.koyo_session_id`.
3. **Starlette router** matches the path to a `Route` created by `build_app`.
4. **For a page route:** The endpoint function calls `render_route(entry, params, request)`.
   - Metadata is merged and pushed to the ContextVar.
   - The page module is imported (or reused from sys.modules cache).
   - `page(params, request)` is called.
   - Each ancestor layout wraps the output.
   - `render_html(tree)` produces the final string.
   - `inject_dev_reload(content)` adds the live-reload script in dev mode.
   - Returns `HTMLResponse`.
5. **For an htmx fragment request:** Same as above, but `render_fragment(entry, params, request)` is called instead, which only calls the `fragment()` function without layout wrapping.
6. **For a state mutation:** The `/__koyo_state/{token}` endpoint decodes the token, updates the session store, re-renders the component, and returns the HTML.
7. **For the reload probe:** Returns 204 or 200 based on token comparison.
8. **For the live reload script:** Returns the concatenated JS.
9. **For static files:** Starlette's `StaticFiles` mount serves them.

---

## File-based routing

Routes are derived from the filesystem:

```
app/page.py              -> /
app/about/page.py        -> /about
app/blog/[slug]/page.py  -> /blog/{slug}
```

Dynamic segments use square brackets in folder names and become Starlette path parameters (curly braces in the route path). The `page()` function receives them as keyword arguments.

There is no explicit route registration. The framework walks `app/` on startup, finds all `page.py` files, and builds the route table. Adding a new route is just adding a new `page.py` file.

---

## Layouts

`layout.py` files in the `app/` directory tree wrap all pages beneath them:

```
app/layout.py            -> wraps everything
app/blog/layout.py       -> wraps everything under /blog/
app/blog/[slug]/layout.py -> wraps everything under /blog/{slug}/
```

A layout must export a `layout(children, request)` function. `children` is the rendered HTML of the inner page (or inner layout) as a `Markup` string. The layout returns an element tree that includes `children`.

Layout nesting is bottom-up: the page output is wrapped by the innermost layout first, then each outer layout, ending at the root layout.

---

## The HTML builder

Instead of templates, koyoapp uses a Python function DSL:

```python
from koyoapp.html import div, p, span

def badge(label):
    return div(class_="card")[
        p(class_="title")[label],
        span(class_="meta")["active"],
    ]
```

Key patterns:
- **Children via brackets:** `div()["Hello", " ", "World"]` or `div()["Hello"]`.
- **Attributes via kwargs:** `div(class_="foo", id="bar")`.
- **Attribute aliases:** `class_` and `cls` both map to `class`. `for_` maps to `for`.
- **Hyphen conversion:** `hx_post` becomes `hx-post`, `data_test` becomes `data-test`, `aria_label` becomes `aria-label`.
- **Boolean attributes:** `disabled=True` renders as `disabled`. `disabled=False` or `disabled=None` is omitted.
- **Raw HTML:** `raw("<b>bold</b>")` returns a `Markup` object that renders without escaping.
- **Custom tags:** Any tag name works, even non-standard ones: `my-component()["content"]`.
- **Void elements:** `<br>`, `<img>`, `<input>`, etc. are self-closing.

The rendering is pure string concatenation using `html.escape` for safety. There is no DOM, no virtual DOM, no diffing on the server side.

---

## Session state with use_state

The full state flow:

```
1. Component calls use_state(request, "visit_count", 0)
   -> sys._getframe(1) captures module="components.counter", name="visit_counter"
   -> Token: base64("components.counter::visit_counter::visit_count")
   -> Reads session store: returns (0, _StateAction(token))

2. Component renders with count=0
   -> button(**count_action.increment(by=1)) produces:
      hx_post="/__koyo_state/{token}?op=increment&by=1"
      hx_target="#visit-card"
      hx_swap="outerHTML"

3. User clicks button
   -> htmx POSTs to /__koyo_state/{token}?op=increment&by=1

4. Server:
   -> _state_endpoint decodes token -> module, name, key
   -> _resolve("components.counter", "visit_counter") imports and gets the function
   -> Updates session store: set(sid, "visit_count", 0 + 1)
   -> Re-renders: fn(request) with session store now returning 1
   -> Returns HTML with "Clicks: 1"

5. htmx swaps #visit-card outerHTML with the new HTML
```

The call-stack introspection (`sys._getframe(1)`) is what makes this work without any decorator or registration. The framework automatically knows which function called `use_state` and re-renders that exact function after the update.

---

## Metadata and head tags

Any page or layout can export a metadata dict:

```python
metadata = {
    "title": "About",
    "description": "Learn more about us.",
    "og_image": "/og-about.png",
}
```

The root layout calls `metadata_tags()` in its `<head>`, which reads the current metadata from the ContextVar and generates `<title>`, `<meta name="description">`, and `<meta property="og:image">` tags.

Metadata is merged page-over-layout, root-first. The page's values win over the nearest layout, which wins over each outer layout, ending at the root layout's own defaults.

---

## Live reload

The live reload system has three parts:

**Server side:**
1. Dev server bumps `.koyo/reload-token` (mtime_ns) on every file change.
2. `/__koyo-reload` endpoint compares client's `since` token to current token.
3. `/__koyo-live-reload.js` serves the concatenated morphdom + reload script.
4. `inject_dev_reload` adds the script tag before `</body>` in dev mode.

**Client side (koyo-live-reload.js):**
1. Polls `/__koyo-reload?since={token}` every 700ms.
2. On token change, fetches the full current page HTML.
3. Parses it with DOMParser.
4. Uses morphdom to diff and update the live DOM.
5. Preserves form state, focus, cursor position.
6. Refreshes stylesheet hrefs for CSS updates.

**Morphdom:**
- A 4KB (minified) library that morphs one DOM tree into another.
- Only updates what actually changed (text content, attributes, node structure).
- Skips script tags entirely.
- The live-reload wrapper adds htmx.process() calls for new nodes so htmx attributes are wired up.

The result: file save -> token change detected within 700ms -> full page morph in the browser -> visual update with no flash, no scroll jump, no lost form data.

---

## The production build

`koyoapp build` produces a static site in `.koyo/build/site/`:

1. Copies `public/` to `site/` root.
2. Copies `styles/` to `site/styles/`.
3. Compiles Tailwind in production mode (minified) to `site/styles/koyo.css`.
4. For each static route, renders the full HTML (page + layouts + metadata) and writes it to `site/{path}/index.html`.
5. Dynamic routes are skipped with a printed notice.

The output is a plain static site that can be deployed to any static host: Cloudflare Pages, Netlify, Vercel, GitHub Pages, S3+CloudFront, etc.

For dynamic routes (use_state, request-dependent content), you need a live server: `python -m uvicorn koyoapp.serve:app`.

---

## CLI commands

| Command | What it does |
|---|---|
| `koyoapp create <dir>` | Scaffolds a new project with all files, .venv, and assets |
| `koyoapp dev` | Starts dev server with hot reload, Tailwind watch, file watching |
| `koyoapp build` | Prerenders static routes to .koyo/build/site |
| `koyoapp add <pkg>` | pip installs into .venv, pins in pyproject.toml |
| `koyoapp remove <pkg>` | pip uninstalls, removes from pyproject.toml |
| `koyoapp install` | Creates .venv if needed, installs all deps from pyproject.toml |
| `koyoapp upgrade [ver]` | Upgrades koyoapp, pins version in pyproject.toml |
| `koyoapp --version` | Prints version |

---

## Dependency management

koyoapp manages dependencies through `pyproject.toml`, similar to how npm manages through `package.json`.

- `dependencies = ["koyoapp==0.4.0", "requests==2.31.0"]` for main deps.
- `[project.optional-dependencies] dev = ["pytest"]` for dev deps.
- `koyoapp install` reads both sections and pip-installs them.
- `koyoapp add` auto-pins exact versions (e.g., `requests==2.31.0`).
- `koyoapp upgrade` upgrades koyoapp and re-pins.
- All pip operations run through the project's `.venv/bin/python -m pip`, not the system pip.

---

## Tailwind CSS integration

- Entry point: `styles/globals.css` with `@tailwind base/components/utilities`.
- Output: `styles/koyo.css` (linked by the root layout).
- Config: `tailwind.config.js` with dark mode class-based, brand color palette.
- Content scanning: `app/**/*.py`, `components/**/*.py`, `styles/**/*.css`.
- Dev mode: Tailwind runs in `--watch` mode, recompiles on CSS/content changes.
- Build mode: Tailwind runs once with `--minify`.
- Auto-install: If `tailwindcss` is not found, runs `npm install` using the project's `package.json`.

---

## Network detection

`net.detect_lan_ip()` uses a UDP socket trick to find the machine's outbound LAN IP without sending any network traffic:

```python
sock = socket.socket(AF_INET, SOCK_DGRAM)
sock.connect(("8.8.8.8", 80))
ip = sock.getsockname()[0]
```

This tells the kernel which interface would route to 8.8.8.8, and `getsockname()` returns that interface's IP. No packets are sent. The result is shown in the dev server startup message so other devices on the LAN can access the dev server.

---

## Logging

Two modes controlled by `--verbose`:
- **Quiet (default):** Subprocess output (pip, npm, Tailwind, uvicorn) is captured and only shown on failure. Success is silent.
- **Verbose:** Full streaming output from all subprocesses.

The dev server and Tailwind subprocess output goes to log files in `.koyo/` (dev-server.log, tailwind.log) unless verbose is on.

---

## Scaffolding

`koyoapp create` generates a complete project:

1. All files from `templates.FILES` with `__PROJECT_NAME__` and `__KOYO_VERSION__` substituted.
2. Bundled assets from `koyoapp/assets/` (favicon, icons, htmx.min.js, manifest). Falls back to pure-Python placeholder generation if assets are missing.
3. A `.venv` with `sys.executable -m venv`.
4. Checks for existing `app/` or `koyo.config.py` and refuses to overwrite.

The scaffold includes deploy files (Procfile, requirements.txt, .railwayignore) so the project is deploy-ready immediately after creation.

---

## Deploy files

Scaffolded into every new project:

- **Procfile:** `web: python -m uvicorn koyoapp.serve:app --host 0.0.0.0 --port $PORT`
- **requirements.txt:** `koyoapp=={version}` (pinned at scaffold time)
- **.railwayignore:** Excludes `.venv/`, `__pycache__/`, `node_modules/`, `.koyo/`, `dist/`, `.DS_Store`

These are for platforms that run the app as a live server (Railway, Render, Fly.io, VPS). For static hosts, use `koyoapp build` and deploy `.koyo/build/site/`.

---

## Error handling

**In dev mode:**
- `RouteError` (bad page function, missing export, wrong return type): Shows the exception type, message, file location, and full traceback in a styled error page.
- Generic exceptions: Same treatment.
- The traceback includes the filename, line number, and function name of the last frame.

**In production:**
- `RouteError`: Generic "Internal Server Error" page with no details.
- Generic exceptions: Same generic page.

**404:** Custom error page showing the requested path and a "Back to home" link.

All error pages use the same `koyoapp.html` DSL and inline CSS.

---

## What it CAN do

- File-based routing with dynamic path parameters.
- Nested layouts (page-over-layout merging).
- A function-based HTML component system (no templates, no build step for HTML).
- Session-scoped state with automatic htmx integration (use_state).
- htmx partial rendering via fragment exports.
- Per-route metadata (title, description, og_image) with automatic head tag generation.
- Live reload with DOM morphing (preserves form state, focus, scroll).
- Hot reload (file change -> server restart -> module cache clear -> fresh render).
- Tailwind CSS with auto-install, dev watch mode, and production minification.
- Production prerendering of static routes to plain HTML.
- Deploy scaffolding (Procfile, requirements.txt, .railwayignore) with pinned versions.
- Automatic port selection (scans up to 200 ports if the default is taken).
- LAN IP detection for phone testing.
- Pure-Python placeholder asset generation (no ImageMagick, no Sharp).
- Dependency management through pyproject.toml (add, remove, install, upgrade).
- Project-level Python venv with isolated pip.
- Quiet CLI output by default with --verbose override.

---

## What it CANNOT do

- **No database or ORM.** Sessions are in-memory only. Data does not survive server restarts and is not shared across processes.
- **No authentication or authorization.** There is no login, no session-to-user mapping, no role system.
- **No API routes.** All routes return HTML. There is no JSON endpoint, no REST API, no GraphQL.
- **No server-side form handling.** Forms can POST via htmx, but there is no CSRF protection, no form validation library, no file upload handling.
- **No WebSocket or SSE.** All communication is request/response.
- **No background jobs or cron.** No task queue, no worker processes.
- **No multi-process or multi-replica sessions.** The in-memory store is per-process. Running multiple workers breaks session continuity.
- **No middleware beyond sessions.** No rate limiting, no CORS, no request logging middleware (though Starlette middleware can be added manually).
- **No i18n or localization.** No translation system, no locale detection.
- **No image optimization.** Static images are served as-is.
- **No SSR streaming.** The entire page is rendered synchronously before sending.
- **No TypeScript or JavaScript build.** htmx and morphdom are vendored as plain JS. No webpack, no Vite, no esbuild.
- **No testing framework.** No built-in test runner, no test utilities, no snapshot testing.
- **No CI/CD configuration.** No GitHub Actions, no Dockerfile.
- **No migration system.** No schema versioning, no data migration.
- **No caching layer.** No Redis, no memcached, no HTTP cache headers beyond `no-store` on dev routes.
- **No rate limiting or throttling.**
- **No WebSocket support for live updates.** Live reload uses polling, not WebSocket.
- **No progressive web app features** beyond the scaffolded manifest and icons.
- **No service worker.**

---

## Key design decisions

1. **Starlette over Flask/Django.** Starlette is async-native, has a clean ASGI interface, and its routing/StaticFiles/middleware are well-suited for this use case. Flask is WSGI and would require async wrappers. Django is too opinionated and heavy for a micro-framework.

2. **Function-based HTML over templates.** Templates (Jinja2, Mako) require a separate syntax, a build step for type checking, and are harder to compose. Python functions are immediately composable, type-checkable, and debuggable with standard tools.

3. **htmx over React/Vue/Svelte.** htmx lets you write HTML attributes instead of JavaScript components. The server renders HTML, htmx swaps it in. No build step, no npm for the frontend (except Tailwind), no hydration, no client-side state management.

4. **In-memory sessions over database sessions.** For a micro-framework targeting small projects and prototyping, a database is overhead. In-memory sessions are zero-config and fast. The limitation is documented.

5. **morphdom over full page reload.** A full `location.reload()` is jarring: scroll position lost, CSS animations restart, form data lost. morphdom surgically updates only what changed, preserving the user's context.

6. **Call-stack introspection for use_state.** Using `sys._getframe(1)` to detect the calling function avoids decorators, registration, or class-based components. The developer writes a plain function and calls `use_state(request, key)` -- the framework figures out the rest.

7. **pyproject.toml over requirements.txt.** Modern Python packaging uses pyproject.toml. The scaffold uses it. Deploy uses a separate requirements.txt (with pinned version) because many deploy platforms expect it.

8. **No emoji, no em dash.** A deliberate aesthetic choice for a professional, clean codebase.

9. **Vendor over npm for runtime JS.** htmx and morphdom are committed as vendored files in the package. This means the framework works without npm for runtime behavior. npm is only used for Tailwind CSS (a build-time tool).

10. **PyPI distribution.** The framework is a pip-installable package. `pip install koyoapp` gives you the CLI and all runtime code. The scaffold is generated from templates within the package.
