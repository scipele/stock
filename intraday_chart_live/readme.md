# intraday_chart_live

Live intraday stock dashboard for the current trading session.

This project uses:
- C++ for fast Yahoo intraday CSV fetch
- Python for multi-ticker candlestick dashboard rendering
- A helper shell script to assemble tickers and launch the full flow

## Quick Commands

Build live C++ fetcher:

```bash
cd /home/dev/stock/intraday_chart_live/cpp/src
g++ fetch_intraday_live.cpp -o ../bin/fetch_intraday_live -lcurl -pthread -std=c++17 -O2
```

Run full live flow (fetch + dashboard):

```bash
cd /home/dev/stock/intraday_chart_live && ./cpp/bin/fetch_intraday_live && /home/dev/py/.venv/bin/python py/chart_live.py --live --cols 4 --refresh-seconds 30
```

Run interactive launcher script:

```bash
cd /home/dev/stock/intraday_chart_live
bash script/chart_live.sh
```

## What This Live Version Does

- Downloads current-session intraday data (range=1d, interval=5m)
- Writes one CSV per ticker to output
- Renders a live multi-panel dashboard for all tickers on one screen
- Refreshes in a loop with configurable refresh seconds
- Uses conservative fetch pacing to reduce Yahoo rate-limit risk

## Project Layout

```text
/home/dev/stock/intraday_chart_live
├── charts/
│   └── live_dashboard.png
├── cpp/
│   ├── bin/
│   │   └── fetch_intraday_live
│   └── src/
│       └── fetch_intraday_live.cpp
├── input/
│   └── tickers.csv
├── output/
│   └── <TICKER>.csv
├── py/
│   └── chart_live.py
├── script/
│   └── chart_live.sh
└── readme.md
```

## Requirements

### C++ fetcher
- g++
- libcurl
- nlohmann/json headers

Build command:

```bash
cd /home/dev/stock/intraday_chart_live/cpp/src
g++ fetch_intraday_live.cpp -o ../bin/fetch_intraday_live -lcurl -pthread -std=c++17 -O2
```

### Python dashboard
Python environment currently used:
- /home/dev/py/.venv/bin/python

Python packages:
- matplotlib
- mplfinance
- pandas
- numpy
- yfinance

## Quick Start (One Terminal)

Run end-to-end manually:

```bash
cd /home/dev/stock/intraday_chart_live && ./cpp/bin/fetch_intraday_live && /home/dev/py/.venv/bin/python py/chart_live.py --live --cols 4 --refresh-seconds 30
```

## Helper Script (Interactive)

Run:

```bash
cd /home/dev/stock/intraday_chart_live
bash script/chart_live.sh
```

The script:
1. Cleans output CSV and chart PNG files
2. Builds ticker list from one or more sources
3. Saves clean ticker list to input/tickers.csv
4. Prompts for live dashboard settings
   - columns (default 4)
   - refresh seconds (default 30)
5. Runs C++ fetcher
6. Runs Python live dashboard
7. Opens charts in gthumb

## Ticker Sources Used by chart_live.sh

Optional sources:
- Previous input/tickers.csv list
- Latest Schwab positions export in Downloads
  - file pattern: Fund-Positions-*.csv
  - exclusion regex: etf|fund|money|adm
- Top buy_opp ranked symbols
  - /home/dev/stock/buy_opp/output/summary_all.csv
- Top intr_buy ranked symbols
  - /home/dev/stock/intr_buy/output/combined_report.csv
- Manual ticker entry

Final ticker list is uppercased, deduplicated, sorted, and written with header:

```text
ticker
```

## Live Dashboard Behavior

chart_live.py live mode:
- Reads ticker symbols from input/tickers.csv
- Reads intraday CSV data from output/<TICKER>.csv (fallback to input/<TICKER>.csv)
- Filters to current session only
- Draws candlesticks plus overlays:
  - session high/low reference lines
  - swing high/low
  - VWAP
  - EMA(9) with directional color
- Saves charts/live_dashboard.png on every refresh

Display behavior:
- If a GUI backend is available, opens an interactive live window
- If GUI is not available, runs headless and updates live_dashboard.png continuously

## Commands

### Fetch only

```bash
cd /home/dev/stock/intraday_chart_live
./cpp/bin/fetch_intraday_live
```

### Dashboard only

```bash
cd /home/dev/stock/intraday_chart_live
/home/dev/py/.venv/bin/python py/chart_live.py --live --cols 4 --refresh-seconds 30
```

### Dashboard help

```bash
/home/dev/py/.venv/bin/python /home/dev/stock/intraday_chart_live/py/chart_live.py --help
```

## Troubleshooting

### Dashboard window does not appear
- Confirm you are in a desktop GUI session.
- If running headless/remote, check charts/live_dashboard.png for updates.

### Panels show Error
- This was previously caused by mplfinance external-axis addplot binding.
- Live version now binds addplots per axis and should render correctly.

### Yahoo rate limiting
Symptoms:
- FAILED <TICKER>
- Edge: Too Many Requests

Current mitigations:
- Current-session-only requests (1d, 5m)
- Retry logic
- Inter-request delay in C++ fetch loop

If failures persist:
- Wait a few minutes and rerun fetch
- Increase refresh/fetch cadence conservatively

## Key Files

- script/chart_live.sh: interactive launcher for live workflow
- cpp/src/fetch_intraday_live.cpp: C++ Yahoo downloader
- cpp/bin/fetch_intraday_live: compiled downloader
- py/chart_live.py: live dashboard renderer
- input/tickers.csv: ticker source list
- output/*.csv: fetched intraday data
- charts/live_dashboard.png: refreshed dashboard image
