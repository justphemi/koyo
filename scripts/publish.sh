#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENV="$ROOT/.venv"

echo "== running the test suite =="
"$VENV/bin/pytest" -q "$ROOT/tests"

echo "== checking build tooling =="
if ! "$VENV/bin/python" -c "import build" > /dev/null 2>&1; then
  "$VENV/bin/pip" install -q build twine
fi

echo "== building sdist and wheel =="
cd "$ROOT"
rm -rf dist
"$VENV/bin/python" -m build
echo "== built =="
ls -1 "$ROOT"/dist

cat <<'EOF'

Upload is intentionally NOT run by this script. It never holds or uses a
PyPI token and never executes the upload commands. Do it by hand in order:

1. Publish to TestPyPI first:
     .venv/bin/twine upload --repository testpypi dist/*

2. Verify the TestPyPI install in a throwaway venv:
     python -m venv /tmp/koyo-verify
     /tmp/koyo-verify/bin/pip install --index-url https://test.pypi.org/simple/ koyoapp
     /tmp/koyo-verify/bin/koyoapp --help

3. Only when the TestPyPI install works, publish to the real PyPI:
     .venv/bin/twine upload dist/*

Have your PyPI and TestPyPI API tokens ready in ~/.pypirc or via
TWINE_USERNAME / TWINE_PASSWORD environment variables.
EOF