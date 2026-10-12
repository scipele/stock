# stock

Monorepo of stock-related utilities and reports.

## Key folders
- [gain_loss/](/home/dev/stock/gain_loss) — realized gain/loss pipeline and HTML reporting
- [asset_alloc/](/home/dev/stock/asset_alloc)
- [buy_opp/](/home/dev/stock/buy_opp)
- [days_held/](/home/dev/stock/days_held)
- [momentum/](/home/dev/stock/momentum)
- [top_tickers/](/home/dev/stock/top_tickers)

## Gain/Loss quick start
Run the full pipeline:

```bash
/home/dev/stock/gain_loss/script/gain_loss.sh 07/09/2026 10/11/2026
```

This script:
1. Builds the C++ calculator if needed.
2. Merges/normalizes transactions and prepares positions input.
3. Produces:
   - [gain_loss.csv](/home/dev/stock/gain_loss/output/gain_loss.csv)
   - [gain_loss.html](/home/dev/stock/gain_loss/output/gain_loss.html)

## Current trading-capital definition (Gain/Loss report)
In [create_report.py](/home/dev/stock/gain_loss/py/create_report.py), `Average Trading Capital` is computed as:
- average **daily tied-up cost basis** over the selected date range,
- transfer-aware for journaled share moves between accounts,
- using stock-only filtering (excluding ETF/fund/money-market-like symbols and CUSIP-style fixed-income symbols).

## Developer checks
- Python syntax:
  ```bash
  python3 -m py_compile /home/dev/stock/gain_loss/py/create_report.py
  ```
- C++ build:
  ```bash
  g++ -std=c++17 -O2 /home/dev/stock/gain_loss/cpp/src/gain_loss.cpp -o /home/dev/stock/gain_loss/cpp/bin/gain_loss
  ```


## Folder structure

```text
/home/dev/stock/gain_loss
├── cpp
│   ├── bin
│   └── src
│       └── gain_loss.cpp
├── output
│   ├── days_held.html
│   ├── gain_loss.csv
│   ├── positions.csv
│   └── transactions.csv
├── py
│   └── create_report.py
├── readme.md
└── script
    ├── gain_loss.sh
    ├── days_held.sh
    └── gain_loss.png
```