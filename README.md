# Koyo

Koyo is a Python web framework that mirrors the developer experience of
Next.js (the app directory convention, file based routing, layouts,
reusable components) but is written entirely in Python and runs as a normal
Python web server. Since it is a normal Python process under the hood, any
package installed with pip is available immediately, with no build step or
compiler touching the Python code.

This is v1, frontend and routing only. No backend API layer, no database,
no auth, no deployment automation.

## Install

Koyo requires Python 3.11 or newer.

```
pip install koyoapp
```

## Quickstart

```
koyoapp create my-app
cd my-app
koyoapp dev
```

Open http://127.0.0.1:2309. The home page renders out of the box with an
animated hero, a call to action linking to the Koyo documentation, and a
live session counter driven by htmx. Edit any file under `app/`, `public/`,
or `styles/` and the page updates in place without a full reload.

## CLI

- `koyoapp create .` scaffolds a Koyo project into the current directory.
- `koyoapp create my-app` creates `my-app` and scaffolds inside it.
- `koyoapp dev` starts the dev server on port 2309 by default, override
  with `--port`.
- `koyoapp build` prerenders every static route into `.koyo/build/site`.

## Project structure

```
my-app/
  app/
    layout.py
    page.py
  components/
    counter.py
    landing.py
    site.py
  public/
  styles/
  koyo.config.py
  pyproject.toml
```

Routing rules follow the Next.js app directory convention. Folders wrapped
in square brackets become dynamic path parameters. A page file must export
a function named `page`, and a layout file must export a function named
`layout(children)`. Layouts nest outward to inward, exactly like Next.js.

## Component system

`koyoapp.html` exposes function based HTML elements. Text content is HTML
escaped by default; use `Markup` (or `raw()`) for raw unescaped output.
Children can be passed positionally as arguments or appended with square
brackets; both styles can be mixed, and a list (or any iterable) passed as
a single child is flattened in place. Attributes map underscores to
hyphens (`hx_`, `data_`, `aria_`), and `class_` / `cls` both mean `class`.

```python
from koyoapp.html import div, h1, p, span

def Card(title: str, body: str):
    return div(class_="p-4 rounded-lg shadow bg-white")[
        h1(class_="text-xl font-bold")[title],
        p(class_="text-gray-600")[body],
    ]

def Row(label: str, value: str):
    return div(span(label, cls="font-medium"), span(value), class_="flex gap-2")
```

## Styles

`koyoapp dev` runs the Tailwind CLI in watch mode against the project and
compiles `styles/globals.css` to `styles/koyo.css`, which the root layout
links automatically. Any other `.css` file under `styles/` is served
untouched from `/styles/` and can be linked directly with a normal `link`
tag. The scaffold ships a light/dark theme switch: `public/theme.js`
applies the saved or system-preferred theme before first paint, the hero
button toggles it and stores the choice in `localStorage`, and dark mode
is class based (`darkMode: "class"`) so any element can use `dark:`
variants.

## Packages

There is no custom package manager. Activate the project virtualenv and use
plain pip:

```
.venv/bin/pip install <package>
```

The package is importable in any `page.py`, `layout.py`, or component file
immediately, since Koyo runs as a normal Python process.