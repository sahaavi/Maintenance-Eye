#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

: "${TEST_ENV:=dev}"
if [[ "$TEST_ENV" == "dev" ]]; then
  set -a
  source ./.env.test.dev
  set +a
elif [[ "$TEST_ENV" == "staging" ]]; then
  set -a
  source ./.env.test.staging
  set +a
elif [[ "$TEST_ENV" == "prod" ]]; then
  set -a
  source ./.env.test.prod
  set +a
else
  echo "Unsupported TEST_ENV: $TEST_ENV"
  exit 2
fi

python -m ruff check backend tests
python -m black --check backend tests
MYPYPATH=backend python -m mypy backend tests
python -m pytest -m "not e2e and not slow"
python -m pytest -m "e2e" --maxfail=1
python -m bandit -r backend -q
python -m pip_audit -r backend/requirements.txt
