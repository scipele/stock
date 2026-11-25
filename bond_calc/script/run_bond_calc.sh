#!/usr/bin/env bash
# Bond Calculator runner (Ubuntu / Linux)
#
# Uses the virtualenv at /home/dev/py/.venv
#
# Usage:
#   ./run_bond_calc.sh
#       → auto-finds the newest All-Accounts-Positions-YYYY-MM-DD-HHMMSS.csv
#         in the current directory, ~/Downloads, ~/Desktop, or the project.
#
#   ./run_bond_calc.sh --dir ~/Downloads
#       → search only that directory for the latest matching CSV
#
#   ./run_bond_calc.sh -i /path/to/All-Accounts-Positions-2026-11-24-125028.csv
#       → use an explicit file
#
#   ./run_bond_calc.sh --valuation-date 2026-11-25

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
PY_DIR="${ROOT_DIR}/py"
OUT_DIR="${ROOT_DIR}/output"

# Prefer the user's project venv
VENV_PYTHON="/home/dev/py/.venv/bin/python"
if [[ ! -x "${VENV_PYTHON}" ]]; then
  # fallback if the venv path differs on this machine
  if [[ -x "${HOME}/dev/py/.venv/bin/python" ]]; then
    VENV_PYTHON="${HOME}/dev/py/.venv/bin/python"
  else
    echo "WARNING: /home/dev/py/.venv not found – falling back to system python3" >&2
    VENV_PYTHON="python3"
  fi
fi

mkdir -p "${OUT_DIR}"

echo "Running Bond Calculator"
echo "  Python: ${VENV_PYTHON}"
echo "  Output: ${OUT_DIR}"
echo

"${VENV_PYTHON}" "${PY_DIR}/bond_calculator.py" \
  --outdir "${OUT_DIR}" \
  "$@"

echo
echo "Outputs are in: ${OUT_DIR}"
ls -la "${OUT_DIR}"
