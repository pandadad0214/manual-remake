#!/usr/bin/env bash
# Run before committing (daily build routine). Autofixes then verifies clean.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
RUFF_VER="${RUFF_VER:-0.17.3}"

if [[ -f uv.lock ]] && grep -q 'name = "ruff"' uv.lock; then
  uv sync --frozen --all-groups
  run_ruff() { uv run ruff "$@"; }
else
  run_ruff() { uv run --with "ruff==${RUFF_VER}" ruff "$@"; }
fi

run_ruff check . --fix
run_ruff format .
run_ruff check .
run_ruff format --check .
echo "lint-fix: clean"
