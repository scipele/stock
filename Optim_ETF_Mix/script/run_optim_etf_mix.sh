#!/usr/bin/env bash
# run_optim_etf_mix.sh
# Launch Optim_ETF_Mix.py from the project .venv (or a shared venv).
#
# Expected layout (adjust BASE_DIR if you move the project):
#   /home/dev/stock/Optim_ETF_Mix
#   ├── output/
#   ├── py/Optim_ETF_Mix.py
#   └── script/run_optim_etf_mix.sh  (this file)

set -euo pipefail

# ---------------------------------------------------------------------------
# Paths – edit these to match your machine
# ---------------------------------------------------------------------------
BASE_DIR="/home/dev/stock/Optim_ETF_Mix"

# Prefer a project-local venv if it exists, otherwise fall back to your shared one
if [[ -x "${BASE_DIR}/.venv/bin/python" ]]; then
  PYTHON="${BASE_DIR}/.venv/bin/python"
elif [[ -x "/home/dev/py/.venv/bin/python" ]]; then
  PYTHON="/home/dev/py/.venv/bin/python"
else
  echo "ERROR: No suitable Python venv found."
  echo "  Looked for: ${BASE_DIR}/.venv/bin/python"
  echo "          and: /home/dev/py/.venv/bin/python"
  exit 1
fi

PYTHON_SCRIPT="${BASE_DIR}/py/Optim_ETF_Mix.py"
OUTPUT_DIR="${BASE_DIR}/output"
mkdir -p "${OUTPUT_DIR}"

# ---------------------------------------------------------------------------
# Starting capital – prompt interactively so the number never lives in the repo
# (still accepts --capital on the command line or CAPITAL env var if preferred)
# ---------------------------------------------------------------------------
CAPITAL="${CAPITAL:-}"

# If user already passed --capital in "$@", don't prompt
if printf '%s\n' "$@" | grep -q -- '--capital'; then
  :
elif [[ -z "${CAPITAL}" ]]; then
  echo ""
  echo "============================================================"
  echo " Optim_ETF_Mix – Portfolio starting value"
  echo "============================================================"
  while true; do
    read -r -p "Enter starting portfolio amount (numbers only, e.g. 1000000): " CAPITAL
    # Allow commas or dollar signs for convenience, then strip them
    CAPITAL="${CAPITAL//\$/}"
    CAPITAL="${CAPITAL//,/}"
    CAPITAL="${CAPITAL// /}"
    if [[ "${CAPITAL}" =~ ^[0-9]+([.][0-9]+)?$ ]] && [[ "${CAPITAL}" != "0" ]] && [[ "${CAPITAL}" != "0.0" ]]; then
      break
    fi
    echo "  Please enter a positive number."
  done
  echo ""
fi

# ---------------------------------------------------------------------------
# Default arguments (override by passing extra flags on the command line)
# ---------------------------------------------------------------------------
DEFAULT_ARGS=(
  --start 2014-01-01
  --min-equity 0.60
  --max-equity 0.80
  --roll-years 5
  --n-combos 35
  --step 0.10
  --n-random 400
  --n-sims 2500
  --top 8
)

# Build final argument list
ARGS=()
if [[ -n "${CAPITAL}" ]]; then
  ARGS+=(--capital "${CAPITAL}")
fi
ARGS+=("${DEFAULT_ARGS[@]}")
ARGS+=("$@")   # user flags win / can override defaults

echo "============================================================"
echo " Optim_ETF_Mix"
echo " Python : ${PYTHON}"
echo " Script : ${PYTHON_SCRIPT}"
echo " Output : ${OUTPUT_DIR}"
echo "============================================================"

cd "${BASE_DIR}"
"${PYTHON}" "${PYTHON_SCRIPT}" "${ARGS[@]}"

echo ""
echo "Finished. Plots and any logs are in: ${OUTPUT_DIR}"