#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

: "${TEST_ENV:=dev}"
case "$TEST_ENV" in
  dev|staging|prod) ;;
  *)
    echo "Unsupported TEST_ENV: $TEST_ENV"
    exit 2
    ;;
esac

ENV_FILE="./.env.test.$TEST_ENV"
if [[ -f "$ENV_FILE" ]]; then
  set -a
  source "$ENV_FILE"
  set +a
else
  echo "No $ENV_FILE found; using current environment and test defaults."
fi

PYTHON_BIN="${PYTHON:-python3}"

"$PYTHON_BIN" -m ruff check backend tests
"$PYTHON_BIN" -m black --check backend tests
MYPYPATH=backend "$PYTHON_BIN" -m mypy backend tests
"$PYTHON_BIN" -m pytest -m "not e2e and not slow"
"$PYTHON_BIN" -m pytest -m "e2e" --maxfail=1 --no-cov
"$PYTHON_BIN" -m bandit -r backend -q
"$PYTHON_BIN" -m pip_audit -r backend/requirements.txt
