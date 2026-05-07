#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON:-python3}"
"$PYTHON_BIN" - <<'PY'
import sys

if sys.version_info < (3, 12):
    raise SystemExit(
        "Python 3.12+ is required. Set PYTHON=/path/to/python3.12 and rerun this script."
    )
PY

"$PYTHON_BIN" -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r backend/requirements-dev.txt
python -m playwright install --with-deps chromium

echo "Test environment is ready. Activate with: source .venv/bin/activate"
