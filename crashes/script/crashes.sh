#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(dirname "$SCRIPT_DIR")"
PY_SCRIPT="$BASE_DIR/py/crashes.py"
PYTHON="/home/dev/py/.venv/bin/python"

if [[ ! -x "$PYTHON" ]]; then
    echo "Error: Python interpreter not found or not executable at $PYTHON" >&2
    exit 1
fi

if [[ ! -f "$PY_SCRIPT" ]]; then
    echo "Error: Python script not found at $PY_SCRIPT" >&2
    exit 1
fi

echo "Running crash history dataset builder..."
"$PYTHON" "$PY_SCRIPT"