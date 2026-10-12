# AGENTS

This repository contains multiple stock-analysis tools.  
When making changes, follow these project-level rules:

## General
- Keep changes scoped to the requested tool/subproject.
- Prefer minimal, surgical fixes over broad refactors.
- Preserve existing CLI workflows and output paths.
- Update documentation when behavior or formulas change.

## Gain/Loss (`gain_loss/`)
- The report pipeline is:
  1. [gain_loss.sh](/home/dev/stock/gain_loss/script/gain_loss.sh)
  2. C++ calculator [gain_loss.cpp](/home/dev/stock/gain_loss/cpp/src/gain_loss.cpp)
  3. Python report [create_report.py](/home/dev/stock/gain_loss/py/create_report.py)
- `Average Trading Capital` in the Python report is intended to represent:
  - average **daily tied-up cost basis** across the selected date range,
  - with sells reducing tied-up capital,
  - and transfer-aware handling for journaled share moves between accounts.
- Stock-only mode should exclude ETFs, mutual funds, money-market-like fund symbols, and CUSIP-style fixed-income symbols.

## Validation
- For Python changes, run:
  - `python3 -m py_compile /home/dev/stock/gain_loss/py/create_report.py`
- For C++ changes, run:
  - `g++ -std=c++17 -O2 /home/dev/stock/gain_loss/cpp/src/gain_loss.cpp -o /home/dev/stock/gain_loss/cpp/bin/gain_loss`
- For end-to-end gain/loss validation, run:
  - `/home/dev/stock/gain_loss/script/gain_loss.sh MM/DD/YYYY MM/DD/YYYY`
