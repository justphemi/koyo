#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENV="$ROOT/.venv"
TMP=/tmp/koyo-e2e
DEMO="$TMP/my-app"
LOG="$TMP/dev.log"
PORT=2399

rm -rf "$TMP"
mkdir -p "$TMP"

echo "== create =="
"$VENV/bin/koyoapp" create "$TMP/my-app" > "$TMP/create.log" 2>&1 || { cat "$TMP/create.log"; exit 1; }

echo "== production build =="
(
  cd "$DEMO"
  "$VENV/bin/koyoapp" build > "$TMP/build.log" 2>&1
)
test -f "$DEMO/.koyo/build/site/index.html"
grep -q "Welcome to Koyo" "$DEMO/.koyo/build/site/index.html"
grep -q "<title>Welcome to Koyo</title>" "$DEMO/.koyo/build/site/index.html"
grep -q "koyo-hero-glow" "$DEMO/.koyo/build/site/index.html"
grep -q 'href="https://justphemi.github.io/koyo-docs"' "$DEMO/.koyo/build/site/index.html"
grep -q "Read the docs" "$DEMO/.koyo/build/site/index.html"
test ! -e "$DEMO/.koyo/build/site/about"
test ! -e "$DEMO/.koyo/build/site/docs"
test ! -e "$DEMO/.koyo/build/site/blog"
test -s "$DEMO/.koyo/build/site/styles/koyo.css"
grep -q "koyo-fade-up" "$DEMO/.koyo/build/site/styles/koyo.css"
grep -q "koyo-float" "$DEMO/.koyo/build/site/styles/koyo.css"
grep -q "koyo-glow" "$DEMO/.koyo/build/site/styles/koyo.css"
grep -qE "1800ad|24 0 173" "$DEMO/.koyo/build/site/styles/koyo.css"
test -s "$DEMO/.koyo/build/site/htmx.min.js"
test -s "$DEMO/.koyo/build/site/theme.js"
grep -q 'src="/theme.js"' "$DEMO/.koyo/build/site/index.html"
grep -q 'id="theme-toggle"' "$DEMO/.koyo/build/site/index.html"
test -s "$DEMO/.koyo/build/site/favicon.ico"
grep -q "Built 1 static routes" "$TMP/build.log"

echo "== build session fallback =="
grep -q "Clicks: 0" "$DEMO/.koyo/build/site/index.html"
if grep -q "__koyo_state" "$DEMO/.koyo/build/site/index.html"; then
  echo "FAIL: production build leaked a session state route"
  exit 1
fi

echo "== dev server =="
(
  cd "$DEMO"
  nohup "$VENV/bin/koyoapp" dev --port "$PORT" > "$LOG" 2>&1 &
  echo $! > "$TMP/dev.pid"
)
DEVPID="$(cat "$TMP/dev.pid")"

ready=0
for i in $(seq 1 120); do
  if curl -sf "http://127.0.0.1:$PORT/" > "$TMP/home.html" 2>/dev/null; then ready=1; break; fi
  sleep 1
done
if [ "$ready" -ne 1 ]; then
  echo "dev server never became ready"
  cat "$LOG"
  exit 1
fi

echo "== dev logging =="
grep -q "Koyo dev server" "$LOG"
grep -q "Local    http://127.0.0.1:$PORT" "$LOG"
grep -q "Network  http://" "$LOG"
grep -qE "Ready in [0-9]+ms" "$LOG"
if grep -q "Started server process" "$LOG"; then
  echo "FAIL: raw uvicorn output leaked into the dev log"
  exit 1
fi
test -s "$DEMO/.koyo/dev-server.log"
grep -q "Uvicorn running" "$DEMO/.koyo/dev-server.log"

echo "== routes =="
grep -q "Welcome to Koyo" "$TMP/home.html"
grep -q "koyo-reload-script" "$TMP/home.html"
grep -q 'href="https://justphemi.github.io/koyo-docs"' "$TMP/home.html"
grep -q "Read the docs" "$TMP/home.html"
status=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:$PORT/about")
test "$status" = "404"
status=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:$PORT/docs")
test "$status" = "404"

echo "== metadata =="
grep -q "<title>Welcome to Koyo</title>" "$TMP/home.html"
grep -q 'name="description" content="A Koyo web application."' "$TMP/home.html"

echo "== landing theme =="
grep -q "koyo-hero-glow" "$TMP/home.html"
grep -q "koyo-hero-icon" "$TMP/home.html"
grep -q 'theme-color" content="#1800ad"' "$TMP/home.html"
grep -q 'id="theme-toggle"' "$TMP/home.html"
grep -q 'id="theme-label"' "$TMP/home.html"
grep -q 'src="/theme.js"' "$TMP/home.html"
grep -q "dark:bg-slate-950" "$TMP/home.html"
curl -sf "http://127.0.0.1:$PORT/theme.js" -o "$TMP/theme.js"
grep -q "koyo-theme" "$TMP/theme.js"
curl -sf "http://127.0.0.1:$PORT/styles/koyo.css" -o "$TMP/koyo.css"
grep -q "koyo-fade-up" "$TMP/koyo.css"
grep -q "koyo-float" "$TMP/koyo.css"
grep -q "koyo-glow" "$TMP/koyo.css"
grep -qE "1800ad|24 0 173" "$TMP/koyo.css"
grep -q "\.dark" "$TMP/koyo.css"

echo "== htmx and session state =="
curl -sf -c "$TMP/jar-a.txt" -b "$TMP/jar-a.txt" "http://127.0.0.1:$PORT/" -o "$TMP/session-a.html"
grep -q "Clicks: 0" "$TMP/session-a.html"
grep -q 'id="visit-count"' "$TMP/session-a.html"
grep -q 'id="visit-card"' "$TMP/session-a.html"
STATE_URL="$(grep -oE 'hx-post="/__koyo_state/[^"]+"' "$TMP/session-a.html" | head -n1 | sed -e 's/^hx-post="//' -e 's/"$//' -e 's/&amp;/\&/g')"
if [ -z "$STATE_URL" ]; then
  echo "FAIL: no session state action in home page"
  exit 1
fi
post_state() {
  curl -sf -c "$TMP/jar-a.txt" -b "$TMP/jar-a.txt" -X POST -H "HX-Request: true" "http://127.0.0.1:$PORT$1"
}
state_body1="$(post_state "$STATE_URL")"
echo "$state_body1" | grep -q "Clicks: 1"
if echo "$state_body1" | grep -q "<html"; then
  echo "state endpoint returned a full page instead of a component render"
  exit 1
fi
echo "$state_body1" | grep -q 'id="visit-card"'
state_body2="$(post_state "$STATE_URL")"
echo "$state_body2" | grep -q "Clicks: 2"
curl -sf -c "$TMP/jar-a.txt" -b "$TMP/jar-a.txt" "http://127.0.0.1:$PORT/" | grep -q "Clicks: 2"
curl -sf -c "$TMP/jar-b.txt" -b "$TMP/jar-b.txt" "http://127.0.0.1:$PORT/" | grep -q "Clicks: 0"
if [ "$(awk '/koyo_session/ { n++ } END { print n }' "$TMP/jar-a.txt")" -ne 1 ]; then
  echo "FAIL: expected a single koyo_session cookie in jar a"
  exit 1
fi
curl -sf "http://127.0.0.1:$PORT/htmx.min.js" -o "$TMP/htmx.js"
test -s "$TMP/htmx.js"

echo "== assets =="
curl -sf "http://127.0.0.1:$PORT/favicon.ico" -o "$TMP/fav.bin"
test -s "$TMP/fav.bin"
curl -sf "http://127.0.0.1:$PORT/logo.png" -o "$TMP/logo.bin"
test -s "$TMP/logo.bin"
curl -sf "http://127.0.0.1:$PORT/icon.png" -o "$TMP/icon.bin"
test -s "$TMP/icon.bin"

status=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:$PORT/does-not-exist")
test "$status" = "404"

echo "== hot reload =="
sed -i '' 's/Welcome to Koyo/Welcome to Koyo 2/' "$DEMO/app/page.py"

updated=0
for i in $(seq 1 20); do
  if curl -sf "http://127.0.0.1:$PORT/" | grep -q "Welcome to Koyo 2"; then updated=1; break; fi
  sleep 1
done
if [ "$updated" -ne 1 ]; then
  echo "hot reload did not pick up the edit"
  cat "$LOG"
  exit 1
fi

echo "== pycache cleanup =="
test -d "$DEMO/.koyo/pycache"
if find "$DEMO/app" -name "__pycache__" | grep -q .; then
  echo "FAIL: __pycache__ appeared inside app/"
  exit 1
fi

echo "== dependency add =="
(
  cd "$DEMO"
  "$VENV/bin/koyoapp" add idna
)
grep -q 'idna==' "$DEMO/pyproject.toml"
"$DEMO/.venv/bin/python" -c "import idna"
(
  cd "$DEMO"
  "$VENV/bin/koyoapp" add six --dev
)
grep -q 'six==' "$DEMO/pyproject.toml"
grep -q 'dev =' "$DEMO/pyproject.toml"

echo "== dependency remove =="
(
  cd "$DEMO"
  "$VENV/bin/koyoapp" remove idna six
)
if grep -q 'idna==' "$DEMO/pyproject.toml"; then echo "idna still listed in pyproject"; exit 1; fi
if grep -q 'six==' "$DEMO/pyproject.toml"; then echo "six still listed in pyproject"; exit 1; fi
if "$DEMO/.venv/bin/python" -c "import idna" 2>/dev/null; then echo "idna still importable"; exit 1; fi
if "$DEMO/.venv/bin/python" -c "import six" 2>/dev/null; then echo "six still importable"; exit 1; fi

echo "== dependency install round trip =="
(
  cd "$DEMO"
  "$VENV/bin/koyoapp" add idna
  "$VENV/bin/koyoapp" add six --dev
)
grep -q 'idna==' "$DEMO/pyproject.toml"
grep -q 'six==' "$DEMO/pyproject.toml"
sed -i '' '/"koyoapp>=0.1.0"/d' "$DEMO/pyproject.toml"
rm -rf "$DEMO/.venv"
(
  cd "$DEMO"
  "$VENV/bin/koyoapp" install
)
"$DEMO/.venv/bin/python" -c "import idna"
"$DEMO/.venv/bin/python" -c "import six"
grep -q 'idna==' "$DEMO/pyproject.toml"
grep -q 'six==' "$DEMO/pyproject.toml"

echo "== clean add output =="
(
  cd "$DEMO"
  "$VENV/bin/koyoapp" add charset-normalizer > "$TMP/add-clean.log" 2>&1
)
grep -q 'charset-normalizer==' "$DEMO/pyproject.toml"
if grep -q "Collecting" "$TMP/add-clean.log"; then
  echo "FAIL: default add leaked raw pip resolver output"
  exit 1
fi
if grep -q "Successfully installed" "$TMP/add-clean.log"; then
  echo "FAIL: default add leaked raw pip install output"
  exit 1
fi
grep -q "Added charset-normalizer==" "$TMP/add-clean.log"

echo "== verbose add output =="
(
  cd "$DEMO"
  "$VENV/bin/koyoapp" add defusedxml --verbose > "$TMP/add-verbose.log" 2>&1
)
grep -q 'defusedxml==' "$DEMO/pyproject.toml"
grep -q "Collecting" "$TMP/add-verbose.log"
grep -q "Added defusedxml==" "$TMP/add-verbose.log"
(
  cd "$DEMO"
  "$VENV/bin/koyoapp" remove charset-normalizer defusedxml > /dev/null 2>&1
)
if grep -q 'charset-normalizer==' "$DEMO/pyproject.toml"; then echo "charset-normalizer still listed"; exit 1; fi
if grep -q 'defusedxml==' "$DEMO/pyproject.toml"; then echo "defusedxml still listed"; exit 1; fi

echo "== dev error page =="
mkdir -p "$DEMO/app/broken"
cat > "$DEMO/app/broken/page.py" <<'EOF'
from koyoapp.html import p

def page():
    raise RuntimeError("e2e-broken-marker")
EOF
error_status=000
for i in $(seq 1 20); do
  error_status=$(curl -s -o "$TMP/broken.html" -w "%{http_code}" "http://127.0.0.1:$PORT/broken" || true)
  if [ "$error_status" = "500" ]; then break; fi
  sleep 1
done
if [ "$error_status" != "500" ]; then
  echo "dev error page never appeared, last status $error_status"
  cat "$TMP/broken.html"
  exit 1
fi
grep -q "e2e-broken-marker" "$TMP/broken.html"
grep -q "RuntimeError" "$TMP/broken.html"
rm -rf "$DEMO/app/broken"

kill -TERM "$DEVPID" 2>/dev/null || true
pkill -f "uvicorn koyoapp.serve" 2>/dev/null || true
pkill -f "tailwindcss.*globals.css" 2>/dev/null || true

echo "E2E OK"