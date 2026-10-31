#!/usr/bin/env bash
# Run every skill test and the repo-level tests. Extra args go to pytest, e.g. scripts/run_tests.sh -k pr_audit
# Set PYTHON to pick the interpreter (default python3, or python if that is missing).
set -eu
cd "$(dirname "$0")/.." || exit 2
PY="${PYTHON:-}"
if [ -z "$PY" ]; then
  if command -v python3 >/dev/null 2>&1; then PY=python3; else PY=python; fi
fi
exec "$PY" -m pytest "$@"
