
---

## What Each Component Does

### 1. Data Downloader (`cpp/`)
- Written in C++ for speed.
- Reads tickers from `input/tickers.csv`.
- Downloads 5-minute OHLCV data from Yahoo Finance (default lookback: 20 days).
- Saves one CSV per ticker into the `output/` folder.

### 2. Chart Generator (`py/chart.py`)
Reads the CSVs and produces annotated charts with:

**Price Levels**
- Previous Day High / Low
- Swing High / Swing Low (most recent pivot that also respects the previous-day levels)
- Entry Price (pulled automatically from the latest Schwab positions export)

**Indicators**
- 50-day Simple Moving Average (daily data, aligned to the intraday chart)
- VWAP (resets each trading day)
- 9-period EMA (colored green when rising, red when falling)

**Other Features**
- Large ticker symbol + company name header
- Volume pane
- Beginner-friendly notes at the bottom explaining every acronym
- Automatic filtering of ETFs/funds via Schwab description matching

### 3. Orchestration Scripts (`script/`)
- `chart.sh` – typical entry point (fetch data → generate charts)
- `chart_open.sh` – generate charts and open them

---

## Typical Workflow

1. Put the tickers you want in `input/tickers.csv` (one ticker per line, header optional).
2. Run the downloader (or the shell script that calls it).
3. Run the Python charting script (or the shell wrapper).
4. Find the finished PNG files in the `charts/` folder.

---

## Key Design Goals

- Keep the charts clean and readable
- Surface only the most useful levels and indicators for short-term decision making
- Automatically pull cost basis from Schwab so entry price is always present
- Stay fast and simple to re-run daily

---

## Notes for New Users

The charts are intentionally minimal. The main visual cues are:

| Element          | Meaning                                      |
|------------------|----------------------------------------------|
| 50-day MA        | Longer-term bias                             |
| VWAP             | Intraday “fair value”                        |
| 9 EMA (green/red)| Short-term trend direction                   |
| Prev Day H/L     | Key reaction levels from the prior session   |
| Swing H/L        | Most recent significant pivot points         |
| Purple Dot       | Your average entry price                     |

---

*Generated for personal use – focused on clarity over complexity.*