#!/usr/bin/env bash
# setup_venv.sh – create / update a project-local .venv and install dependencies
set -euo pipefail

#    BASE_DIR="/home/dev/stock/Optim_ETF_Mix"
# VENV_DIR="${BASE_DIR}/.venv"

# Allow override if you prefer your shared venv
VENV_DIR="/home/dev/py/.venv"

echo "Using venv: ${VENV_DIR}"

if [[ ! -d "${VENV_DIR}" ]]; then
  echo "Creating virtual environment..."
  python3 -m venv "${VENV_DIR}"
fi

# shellcheck disable=SC1091
source "${VENV_DIR}/bin/activate"

echo "Upgrading pip..."
pip install --upgrade pip

echo "Installing required packages..."
pip install \
  yfinance \
  pandas \
  numpy \
  matplotlib \
  scipy \
  seaborn

echo ""
echo "Installed versions:"
python -c "
import yfinance, pandas, numpy, matplotlib, scipy, seaborn
print(f'  yfinance   {yfinance.__version__}')
print(f'  pandas     {pandas.__version__}')
print(f'  numpy      {numpy.__version__}')
print(f'  matplotlib {matplotlib.__version__}')
print(f'  scipy      {scipy.__version__}')
print(f'  seaborn    {seaborn.__version__}')
"

echo ""
echo "Done. Activate with:  source ${VENV_DIR}/bin/activate"
echo "Or just use the runner:  ${BASE_DIR}/script/run_optim_etf_mix.sh"