#!/usr/bin/env bash
# Full project checkup: backend (ruff/mypy/pytest) + frontend (tsc/eslint/vitest).
# Writes everything to checkup.log so results can be read without re-running.
set +e
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG="$ROOT/checkup.log"
: > "$LOG"
exec >>"$LOG" 2>&1

echo "=== CHECKUP started $(date) ==="

echo
echo "########## BACKEND ##########"
cd "$ROOT/backend" || { echo "no backend dir"; exit 1; }

if command -v uv >/dev/null 2>&1; then
  echo "[using uv $(uv --version)]"
  echo "--- uv sync --extra dev ---"
  uv sync --extra dev 2>&1 | tail -8
  echo "sync_exit=$?"
  echo "--- ruff ---";   uv run ruff check . ; echo "ruff_exit=$?"
  echo "--- mypy ---";   uv run mypy app ;      echo "mypy_exit=$?"
  echo "--- pytest ---"; uv run pytest -q ;     echo "pytest_exit=$?"
else
  echo "[no uv; python venv + pip]"
  python -m venv .venv
  source .venv/Scripts/activate 2>/dev/null || source .venv/bin/activate
  python -m pip install -q -e ".[dev]" 2>&1 | tail -8
  echo "pipinstall_exit=$?"
  echo "--- ruff ---";   ruff check . ; echo "ruff_exit=$?"
  echo "--- mypy ---";   mypy app ;      echo "mypy_exit=$?"
  echo "--- pytest ---"; pytest -q ;     echo "pytest_exit=$?"
fi

echo
echo "########## FRONTEND ##########"
cd "$ROOT/frontend" || { echo "no frontend dir"; exit 1; }
if command -v pnpm >/dev/null 2>&1; then PM=pnpm
elif command -v npm >/dev/null 2>&1; then PM=npm
else PM=""; fi
echo "package_manager=$PM"
if [ -n "$PM" ]; then
  if [ ! -d node_modules ]; then
    echo "--- $PM install ---"; $PM install 2>&1 | tail -12; echo "install_exit=$?"
  fi
  echo "--- typecheck ---"; $PM run typecheck 2>&1 | tail -40 ; echo "tsc_done"
  echo "--- lint ---";      $PM run lint 2>&1 | tail -40 ;      echo "lint_done"
  echo "--- vitest ---";    $PM test 2>&1 | tail -40 ;          echo "vitest_done"
fi

echo "=== CHECKUP done $(date) ==="
