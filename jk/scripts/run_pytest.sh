#!/usr/bin/env bash
# Run pytest with PYTHONPATH=src using the first Python on PATH that has pytest.
# Use when `python3` is 3.14+ without dev deps: ./scripts/run_pytest.sh -q

set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="${ROOT}/src"

pick_py() {
  for cmd in python3.13 python3.12 python3.11 python3; do
    if command -v "$cmd" &>/dev/null && "$cmd" -c "import pytest" 2>/dev/null; then
      echo "$cmd"
      return 0
    fi
  done
  echo "No Python with pytest found. Install test deps from repo root:" >&2
  echo "  pip install -e '.[test]'   # or: pip install pytest" >&2
  exit 1
}

PY="$(pick_py)"
exec "$PY" -m pytest "$@"
