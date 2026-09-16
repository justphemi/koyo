"""File contents for projects produced by koyoapp create."""

from __future__ import annotations

FILES: dict[str, str] = {
    "app/layout.py": '''\
from koyoapp.html import body, head, html, link, meta, script
from koyoapp.meta import metadata_tags

from components.site import site_footer

metadata = {
    "title": "Koyo App",
    "description": "A Koyo web application.",
}

def layout(children, request):
    return html(lang="en")[
        head()[
            meta(charset="utf-8"),
            meta(name="viewport", content="width=device-width, initial-scale=1"),
            meta(name="theme-color", content="#1800ad"),
            script(src="/theme.js"),
            link(rel="icon", href="/favicon.ico", sizes="32x32"),
            link(rel="icon", href="/favicon.svg", type="image/svg+xml"),
            link(rel="apple-touch-icon", href="/apple-touch-icon.png"),
            link(rel="manifest", href="/site.webmanifest"),
            link(rel="stylesheet", href="/styles/koyo.css"),
            script(src="/htmx.min.js"),
            metadata_tags(),
        ],
        body(class_="min-h-screen bg-white text-slate-800 antialiased transition-colors dark:bg-slate-950 dark:text-slate-200")[
            children,
            site_footer(),
        ],
    ]
''',
    "app/page.py": '''\
from components.landing import hero

metadata = {
    "title": "Welcome to Koyo",
}

def page(request):
    return hero(request)
''',
    "components/landing.py": '''\
from koyoapp.html import a, button, div, h1, img, main, p, section, span

from components.counter import visit_counter

DOCS_URL = "https://justphemi.github.io/koyo-docs"


def hero(request):
    return main(class_="relative overflow-hidden bg-gradient-to-b from-slate-50 to-white dark:from-slate-900 dark:to-slate-950")[
        div(class_="pointer-events-none absolute inset-x-0 top-16 flex justify-center")[
            div(
                class_="koyo-hero-glow h-72 w-72 rounded-full bg-brand/20 blur-3xl sm:h-96 sm:w-96",
            ),
        ],
        section(class_="relative mx-auto max-w-3xl px-6 py-20 text-center sm:py-28")[
            div(
                class_="koyo-hero-icon mx-auto flex h-20 w-20 items-center justify-center rounded-2xl shadow-lg shadow-brand/30 sm:h-24 sm:w-24",
            )[
                img(src="/icon.png", alt="Koyo logo", class_="h-12 w-12 sm:h-14 sm:w-14"),
            ],
            h1(
                class_="mt-10 text-4xl font-bold tracking-tight text-slate-900 animate-koyo-fade-up dark:text-white sm:text-5xl md:text-6xl",
                style="animation-delay: 120ms",
            )[
                "Welcome to Koyo"
            ],
            p(
                class_="mx-auto mt-5 max-w-xl text-lg text-slate-600 animate-koyo-fade-up dark:text-slate-400 sm:text-xl",
                style="animation-delay: 240ms",
            )[
                "Koyo brings the Next.js app directory experience to pure Python. "
                "This page was rendered on a plain Python web server, with no build "
                "step and no JavaScript framework."
            ],
            div(
                class_="mt-10 flex items-center justify-center gap-3 animate-koyo-fade-up",
                style="animation-delay: 360ms",
            )[
                a(
                    href=DOCS_URL,
                    class_="rounded-full bg-brand px-8 py-3 text-base font-semibold text-white shadow-lg shadow-brand/30 transition hover:-translate-y-0.5 hover:bg-brand-dark hover:shadow-xl",
                )[
                    "Read the docs"
                ],
                button(
                    id="theme-toggle",
                    aria_label="Toggle color theme",
                    class_="cursor-pointer rounded-full border border-slate-300 bg-white/80 px-8 py-3 text-base font-medium text-slate-600 shadow-sm backdrop-blur transition hover:text-slate-900 dark:border-slate-700 dark:bg-slate-800/80 dark:text-slate-300 dark:hover:text-white",
                )[
                    span(id="theme-label")["Theme changer"],
                ],
            ],
            visit_counter(request),
        ],
    ]
''',
    "components/counter.py": '''\
from koyoapp.html import button, div, p, span
from koyoapp.state import use_state


def visit_counter(request):
    count, count_action = use_state(request, "visit_count", 0)

    return div(
        id="visit-card",
        class_="mx-auto mt-12 max-w-sm rounded-2xl border border-slate-200 bg-white/80 p-6 text-center shadow-sm backdrop-blur dark:border-slate-800 dark:bg-slate-900/70",
    )[
        p(class_="text-sm font-semibold text-slate-700 dark:text-slate-300")[
            "Session state, live right here"
        ],
        div(class_="mt-3 flex items-center justify-center gap-4")[
            span(id="visit-count", class_="text-lg font-bold text-brand")[
                f"Visits: {count}"
            ],
            button(
                class_="cursor-pointer rounded-full bg-brand px-5 py-2 text-sm font-medium text-white transition hover:bg-brand-dark",
                **count_action.increment(by=1),
                hx_target="#visit-card",
                hx_swap="outerHTML",
            )["+"],
        ],
    ]
''',
    "components/site.py": '''\
from koyoapp.html import a, div, footer, img, p, span

DOCS_URL = "https://justphemi.github.io/koyo-docs"


def site_footer():
    return footer(class_="border-t border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-950")[
        div(class_="mx-auto flex max-w-4xl flex-col items-center justify-between gap-4 px-6 py-8 text-sm text-slate-500 sm:flex-row sm:px-8 dark:text-slate-400")[
            div(class_="flex items-center gap-2.5")[
                img(src="/icon.png", alt="Koyo logo", class_="h-6 w-6 rounded-md"),
                p(class_="flex items-center gap-2")[
                    span(class_="font-semibold text-slate-700 dark:text-slate-200")["Built with"],
                    span()["pure Python"],
                ],
            ],
            a(
                href=DOCS_URL,
                class_="font-medium text-slate-500 hover:text-slate-700 dark:hover:text-slate-300",
            )["Documentation"],
        ],
    ]
''',
    "public/theme.js": '''\
(function () {
  var KEY = "koyo-theme";
  var root = document.documentElement;
  var stored = null;
  try { stored = localStorage.getItem(KEY); } catch (e) {}
  var prefersDark = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
  var dark = stored ? stored === "dark" : prefersDark;

  function apply(value) {
    root.classList.toggle("dark", value);
    root.style.colorScheme = value ? "dark" : "light";
  }

  apply(dark);

  function init() {
    var button = document.getElementById("theme-toggle");
    if (!button) { return; }
    button.addEventListener("click", function () {
      var next = !root.classList.contains("dark");
      apply(next);
      try { localStorage.setItem(KEY, next ? "dark" : "light"); } catch (e) {}
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
''',
    "styles/globals.css": '''\
@tailwind base;
@tailwind components;
@tailwind utilities;

@keyframes koyo-fade-up {
  from {
    opacity: 0;
    transform: translateY(14px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes koyo-float {
  0%, 100% {
    transform: translateY(0);
  }
  50% {
    transform: translateY(-10px);
  }
}

@keyframes koyo-glow {
  0%, 100% {
    opacity: 0.35;
    transform: scale(0.95);
  }
  50% {
    opacity: 0.75;
    transform: scale(1.1);
  }
}

.animate-koyo-fade-up {
  animation: koyo-fade-up 0.6s ease-out both;
}

.koyo-hero-icon {
  animation: koyo-float 6s ease-in-out infinite;
  will-change: transform;
}

.koyo-hero-glow {
  animation: koyo-glow 6s ease-in-out infinite;
  will-change: transform, opacity;
}
''',
    "koyo.config.py": '''\
PORT = 2309
PROJECT_NAME = "__PROJECT_NAME__"
''',
    "pyproject.toml": '''\
[project]
name = "__PROJECT_NAME__"
version = "0.1.0"
description = "A Koyo web application"
requires-python = ">=3.11"
dependencies = [
    "koyoapp>=0.1.0",
]
''',
    "tailwind.config.js": '''\
/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: "class",
  content: [
    "./app/**/*.py",
    "./components/**/*.py",
    "./styles/**/*.css",
    "!./styles/koyo.css",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          DEFAULT: "#1800ad",
          dark: "#13008a",
        },
      },
    },
  },
  plugins: [],
};
''',
    "package.json": '''\
{
  "name": "__PROJECT_NAME__",
  "version": "0.1.0",
  "private": true,
  "devDependencies": {
    "tailwindcss": "^3.4.10"
  }
}
''',
    ".gitignore": '''\
.venv/
__pycache__/
*.py[cod]
node_modules/
.koyo/
dist/
.DS_Store
''',
    "README.md": '''\
# __PROJECT_NAME__

A Koyo web application. Koyo is a Python web framework that brings the
Next.js app directory experience, file based routing, nested layouts, and
reusable components, to a plain Python web server.

The full framework reference lives at
https://justphemi.github.io/koyo-docs.

## Develop

Start the dev server with hot reload:

    koyoapp dev

Open http://localhost:2309. The server listens on port 2309 by default.
Override it with --port. The dev server binds all interfaces, so other
devices on your network can open the printed Network URL, useful for
testing on a phone. Override the bind address with --host. Subprocess
output from pip, npm, Tailwind, and uvicorn is quiet by default; pass
--verbose to stream it.

## Routing

The scaffold ships a single page:

- app/page.py renders /

Folders wrapped in square brackets become dynamic path parameters and are
passed to the page function as arguments. Adding app/blog/[slug]/page.py
makes /blog/:any-slug render.

## Landing page

app/page.py renders hero(request) from components/landing.py: the animated
app icon, the brand headline, and a call to action linking to the Koyo
documentation at https://justphemi.github.io/koyo-docs. The looping intro
animation is plain CSS in styles/globals.css (koyo-float and koyo-glow
keyframes), so there is no JavaScript and no build step involved.

## Theme

The app brand color is #1800ad, defined in tailwind.config.js as the
brand palette. Use it anywhere with classes such as bg-brand,
text-brand, border-brand, or with opacity modifiers like bg-brand/20.
The root layout also sets theme-color to #1800ad in the head, so mobile
browsers tint the address bar. Override brand or add shades by editing
tailwind.config.js and resaving; the dev server recompiles Tailwind for
you.

The scaffold also ships a light/dark switch. public/theme.js applies the
saved or system-preferred theme before first paint, and the button in
the hero toggles it and remembers the choice in localStorage. Tailwind
dark mode is class based (darkMode: "class"), so use dark: variants on
any element:

    <p class="text-slate-600 dark:text-slate-400">Body text</p>

The root layout, landing hero, counter card, and footer all carry dark:
variants already as examples.

## Layouts

A layout.py wraps every page beneath it in the directory tree. The root
layout at app/layout.py renders the html, head, and body skeleton and the
footer from components/site.py, which links back to the documentation.

## Components

The components/ folder is created by default and is watched by the dev
server, so a save in there also reloads the page. Files in components/
export plain functions that return HTML:

    # components/site.py
    from koyoapp.html import div, p

    def badge(label):
        return p(class_="text-sm text-slate-600")[label]

Children can be passed positionally or appended with square brackets; the
two styles mix freely, and attributes use class_ (or cls) as a shorthand
for the class keyword:

    def badge(label):
        return p("Hello ", label, class_="text-sm text-slate-600")

Because the project root is on the Python path in the dev server, any page
or layout can import them with an absolute import:

    from components.site import badge

Subfolders work too, for example components/cards/page_card.py imported as
from components.cards.page_card import page_card. There is no need for an
__init__.py; the folders behave as namespace packages.

## Session state

The hero includes a working counter from components/counter.py. Every
visitor gets their own session counter via the koyo_session cookie; the +
button posts to an automatically registered internal route and htmx swaps
in a freshly rendered copy of the counter with no full page reload:

    from koyoapp.state import use_state

    def visit_counter(request):
        count, count_action = use_state(request, "visit_count", 0)
        return div(id="visit-card")[
            span(id="visit-count")[f"Visits: {count}"],
            button(
                **count_action.increment(by=1),
                hx_target="#visit-card",
                hx_swap="outerHTML",
            )["+"],
        ]

use_state registers an internal route behind the scenes. Posting the
increment attributes swaps in a fresh render of the component with the new
value. Every visitor gets their own session via an httponly koyo_session
cookie, so two tabs or two devices never share counts. State lives in
memory only: it resets when the server restarts, it does not sync across
processes, and it is not shared with any database. The production build
prerenders safely because use_state called outside a request returns the
initial value without touching a session.

## Per page metadata

Any page.py or layout.py can export a metadata dict, and the rendered head
tags build themselves from it:

    metadata = {
        "title": "About Koyo",
        "description": "Learn more about the Koyo framework.",
        "og_image": "/og-about.png",
    }

The page's values win over its nearest layout, which wins over each outer
layout, ending at the root layout's own metadata defaults. Supported keys
are title, description, and og_image. The root layout already calls
metadata_tags() in its head, so there are no manual tags to write.

## Interactivity with htmx

htmx ships with every scaffold at /htmx.min.js, loaded automatically by
the root layout. An htmx attribute is just an underscore keyword on any
element:

    button(hx_post="/like", hx_target="#like-count", hx_swap="outerHTML")

Underscores in hx_, data_, and aria_ attributes become hyphens on render.
The counter on the home page is a working example of this pattern.

## Production build

    koyoapp build

Prerenders every static route into .koyo/build/site as plain HTML files
(with the public assets and compiled CSS alongside), ready for any static
file host. Dynamic routes are skipped with a printed notice, they must be
served by the running Koyo server. Compiling Tailwind here runs in
production mode, minified, with no watch.

## Styles

- styles/globals.css is the Tailwind entry point and is compiled to
  /styles/koyo.css, which the root layout links.
- Any other .css file under styles/ is served untouched from /styles/ and
  can be linked directly with a normal link tag.

## Assets

Everything in public/ is served from the site root. The scaffold copies
the bundled artwork into public/ automatically: favicon.ico, favicon.svg,
apple-touch-icon.png, site.webmanifest, the web app manifest icons,
logo.png, and icon.png. Swap any of these files for your own artwork with
no code changes; the root layout already links the favicon set.

## Python packages

Install any package into the project virtualenv and import it anywhere:

    .venv/bin/pip install requests

or, with the virtualenv activated:

    pip install requests
''',
}