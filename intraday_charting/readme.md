# Intraday Charting

## Purpose

The `intraday_charting` project downloads **5-minute intraday stock data**, generates annotated charts, and provides a convenient way to review stocks for short-term trading opportunities.

The main entry point is:

```bash
/home/dev/stock/intraday_charting/script/chart.sh
```

The script is designed to make it easy to build a list of stocks from several sources, download the latest intraday data, generate charts, and open all of the charts in a gallery.

The ticker list can be built from:

* Previously used tickers
* Current positions from the latest Schwab **Community Property-Positions** export
* Top-ranked stocks from the `buy_opp` report
* Top-ranked stocks from the `intr_buy` report
* Manually entered tickers

The final ticker list is automatically **combined, converted to uppercase, deduplicated, sorted, and saved** back to `input/tickers.csv`.

---

## Directory Structure

```text
/home/dev/stock/intraday_charting
├── charts
│   ├── adm.png                         # Example generated chart
│   └── _readme_placeholder_charts.md
│
├── cpp
│   ├── bin
│   │   └── fetch_intraday               # Compiled C++ downloader
│   └── src
│       └── fetch_intraday.cpp           # C++ source
│
├── input
│   ├── readme_placeholder_input.md
│   └── tickers.csv                      # Current ticker list
│
├── output
│   ├── ADM.csv                          # Example downloaded data
│   └── _readme_placeholder_output.md
│
├── py
│   └── chart.py                         # Python chart generator
│
├── script
│   ├── chart_open.sh                    # Chart generation/opening helper
│   ├── chart.png                        # Script/icon graphic
│   └── chart.sh                         # Main orchestration script
│
└── readme.md
```

---

# Main Script: `script/chart.sh`

`chart.sh` is the primary orchestration script for the entire charting process.

It performs the following major operations:

1. Cleans old chart and data files
2. Builds the ticker list
3. Saves the final ticker list
4. Asks how many days of data should appear on the charts
5. Runs the C++ intraday data downloader
6. Runs the Python chart generator
7. Opens the resulting charts in `gthumb`

---

## 1. Clean Previous Data

At the beginning of each run, the script removes previous generated files:

```text
output/*.csv
charts/*.png
```

This ensures that old charts and stale intraday data are not accidentally mixed with the new run.

The source files and programs are not deleted.

---

# 2. Assemble the Ticker List

One of the main purposes of `chart.sh` is to make building the ticker list quick and flexible.

The script can combine tickers from multiple sources.

The user is prompted individually for each source.

---

## 2.1 Reuse Previous Tickers

If `input/tickers.csv` already exists, the script displays the tickers from the previous run and asks:

```text
Use these previous tickers? [Y/n]:
```

If accepted, those tickers are reused as the starting list.

This is useful when repeatedly reviewing the same group of stocks.

---

## 2.2 Load Current Positions from Schwab

The script can automatically find the newest file matching:

```text
~/Downloads/Community Property-Positions-*.csv
```

It selects the most recently modified file.

For example:

```text
Community Property-Positions-2026-08-18-123456.csv
```

The script extracts the ticker symbols from the Schwab export.

### Position filtering

Certain securities are intentionally excluded based on their description.

The current exclusion pattern is:

```text
etf|fund|money|adm
```

The comparison is case-insensitive.

This prevents ETFs, funds, money-market holdings, and matching descriptions from being automatically added to the intraday stock charts.

The purpose is to concentrate the charts on individual stocks rather than investment vehicles that are not normally appropriate for this type of intraday analysis.

---

## 2.3 Add Top `buy_opp` Stocks

The script can optionally add the highest-ranked stocks from:

```text
/home/dev/stock/buy_opp/output/summary_all.csv
```

The user is asked how many top-ranked stocks should be added.

For example:

```text
How many top stocks would you like to add?
```

The script reads the ticker from the ranking file and takes the first `N` stocks.

This allows the intraday charts to be automatically generated for the stocks currently ranking highest in the broader `buy_opp` analysis.

---

## 2.4 Add Top `intr_buy` Stocks

The script can also add the highest-ranked stocks from:

```text
/home/dev/stock/intr_buy/output/combined_report.csv
```

Again, the user chooses how many stocks to add.

This provides a direct connection between the `intr_buy` ranking system and the intraday charting system.

For example, the workflow can be:

```text
intr_buy analysis
       ↓
combined_report.csv
       ↓
select top-ranked stocks
       ↓
intraday_charting
       ↓
5-minute charts
```

This makes it possible to visually inspect the highest-ranked intraday candidates.

---

## 2.5 Manually Add Tickers

Additional tickers can be entered manually.

The script accepts:

* One ticker per line
* Comma-separated tickers
* A combination of the two

The user can paste a group of symbols and finish by pressing:

```text
Ctrl+D
```

This is useful for quickly adding a stock that is not contained in the other lists.

---

# 2.6 Clean and Finalize the Ticker List

After all requested sources have been processed, the script creates the final ticker list.

The list is:

1. Converted to uppercase
2. Blank entries are removed
3. Duplicate tickers are removed
4. Tickers are sorted alphabetically

For example, if the various sources produce:

```text
AMD
AAPL
AMD
msft
AAPL
NVDA
```

the final list becomes:

```text
AAPL
AMD
MSFT
NVDA
```

The cleaned list is then written to:

```text
/home/dev/stock/intraday_charting/input/tickers.csv
```

This file therefore represents the exact group of stocks that will be processed during the current run.

---

# 3. Select Chart Period

The script asks:

```text
Enter how many days to include on the chart:
```

This controls how many days of the downloaded intraday data are displayed by the Python charting program.

For example:

```text
3
```

will generate charts covering three days.

The C++ downloader still obtains the available intraday data needed for the charting process, while the Python program controls the number of days displayed.

---

# 4. Download Intraday Data

The script changes to:

```text
/home/dev/stock/intraday_charting/cpp/bin
```

and executes:

```text
./fetch_intraday
```

The C++ program reads:

```text
input/tickers.csv
```

and downloads 5-minute OHLCV data for each ticker.

The resulting files are written to:

```text
/home/dev/stock/intraday_charting/output/
```

Example:

```text
output/ADM.csv
output/AAPL.csv
output/AMD.csv
output/NVDA.csv
```

### Why C++?

The downloader is written in C++ to keep the data collection process fast and efficient when processing a larger group of tickers.

---

# 5. Generate Charts

After the C++ downloader completes successfully, `chart.sh` runs:

```text
/home/dev/py/.venv/bin/python \
/home/dev/stock/intraday_charting/py/chart.py \
--days "$chart_days"
```

The Python program reads the downloaded CSV files and generates PNG charts.

The resulting charts are saved in:

```text
/home/dev/stock/intraday_charting/charts/
```

Example:

```text
charts/ADM.png
charts/AAPL.png
charts/AMD.png
```

If the C++ downloader fails, chart generation is skipped.

---

# 6. Open the Chart Gallery

After the charts are generated, the script automatically opens the chart directory using `gthumb`.

This provides a convenient visual gallery for quickly reviewing all of the generated stocks.

The charts are sorted by name so that the ticker symbols appear in alphabetical order.

---

# Chart Generator: `py/chart.py`

`chart.py` is responsible for converting the downloaded 5-minute data into readable trading charts.

It reads the CSV files from:

```text
/home/dev/stock/intraday_charting/output/
```

and creates PNG files in:

```text
/home/dev/stock/intraday_charting/charts/
```

---

## Chart Information

Each chart contains several technical reference points and indicators intended to make short-term price action easier to evaluate.

### Price Levels

**Previous Day High / Low**

Shows the high and low from the previous trading session.

These levels are useful because they often act as support, resistance, breakout, or rejection areas.

**Swing High / Swing Low**

Identifies recent significant price pivots.

The swing levels are selected using the chart's price-action rules and are intended to highlight areas where price has recently changed direction.

**Entry Price**

The chart can automatically display the user's average entry price based on the latest Schwab positions export.

This makes it possible to compare the current price directly against the position's cost basis.

---

# Technical Indicators

### 50-Day Moving Average

The 50-day Simple Moving Average (SMA) provides a longer-term trend reference.

It is calculated using daily data and aligned with the intraday chart.

The primary purpose is to provide context for the shorter-term 5-minute price action.

---

### VWAP

VWAP means **Volume Weighted Average Price**.

The VWAP calculation resets at the beginning of each trading day.

It provides an intraday reference for the average price paid based on trading volume.

---

### 9-Period EMA

The 9-period Exponential Moving Average (EMA) is used as a short-term trend indicator.

The line changes appearance based on its direction:

* **Green** = rising
* **Red** = falling

This provides a quick visual indication of the short-term price trend.

---

# Other Chart Features

Each chart also includes:

* Large ticker symbol
* Company name
* 5-minute candlesticks
* Volume
* Previous-day reference levels
* Swing levels
* VWAP
* 9 EMA
* 50-day SMA
* Average entry price when available
* Beginner-friendly explanations of the indicators

The goal is to provide enough information to evaluate a potential trade without filling the chart with unnecessary indicators.

---

# Typical Workflow

The intended workflow is:

```text
                    ┌──────────────────────┐
                    │ Previous Tickers     │
                    └──────────┬───────────┘
                               │
                    ┌──────────▼───────────┐
                    │ Current Schwab       │
                    │ Positions            │
                    └──────────┬───────────┘
                               │
                    ┌──────────▼───────────┐
                    │ Top buy_opp Stocks   │
                    └──────────┬───────────┘
                               │
                    ┌──────────▼───────────┐
                    │ Top intr_buy Stocks  │
                    └──────────┬───────────┘
                               │
                    ┌──────────▼───────────┐
                    │ Manual Tickers       │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │ Combine / Deduplicate│
                    │ / Sort Tickers       │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │ input/tickers.csv    │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │ C++ Downloader       │
                    │ 5-Minute OHLCV Data  │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │ output/*.csv         │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │ Python chart.py      │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │ charts/*.png         │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │ gthumb Chart Gallery │
                    └──────────────────────┘
```

---

# Example Daily Use

A typical run might look like this:

### Step 1 — Start the chart script

```bash
/home/dev/stock/intraday_charting/script/chart.sh
```

### Step 2 — Select ticker sources

The script asks whether to:

* Reuse yesterday's ticker list
* Load current Schwab positions
* Add the top `buy_opp` stocks
* Add the top `intr_buy` stocks
* Add additional stocks manually

### Step 3 — Review the final list

The script displays the final combined ticker list before saving it to:

```text
input/tickers.csv
```

### Step 4 — Select the chart period

Enter the desired number of days.

### Step 5 — Download

The C++ program retrieves the 5-minute data.

### Step 6 — Generate

Python creates the annotated PNG charts.

### Step 7 — Review

`gthumb` opens the complete chart gallery for visual review.

---

# Notes for New Users

The charts are intentionally designed to be relatively simple.

The primary visual cues are:

| Element           | Meaning                                      |
| ----------------- | -------------------------------------------- |
| 50-day SMA        | Longer-term trend/bias                       |
| VWAP              | Intraday volume-weighted average price       |
| 9 EMA             | Short-term trend direction                   |
| Previous Day High | Important prior-session resistance/reference |
| Previous Day Low  | Important prior-session support/reference    |
| Swing High        | Recent significant price pivot               |
| Swing Low         | Recent significant price pivot               |
| Entry Price       | Average cost basis of an existing position   |
| Volume            | Trading activity                             |

The purpose is **not** to create a chart containing every possible technical indicator.

Instead, the goal is to provide a clean visual reference for evaluating:

* Current price direction
* Short-term momentum
* Important support/resistance
* Position relative to VWAP
* Position relative to the 50-day trend
* Recent swing points
* Existing cost basis
* Volume confirmation

---

# Integration With Other Stock Analysis Projects

`intraday_charting` is designed to work alongside the other stock-analysis projects under:

```text
/home/dev/stock/
```

In particular:

### `buy_opp`

Provides a broader stock-ranking system.

```text
buy_opp/output/summary_all.csv
```

can be used to automatically select the highest-ranked stocks for charting.

### `intr_buy`

Provides an additional ranking specifically related to buying opportunities.

```text
intr_buy/output/combined_report.csv
```

can also be used to automatically select the highest-ranked stocks for charting.

This allows the workflow to move from **quantitative screening to visual chart analysis**:

```text
Stock Universe
      ↓
buy_opp / intr_buy
      ↓
Ranked Candidates
      ↓
Select Top Stocks
      ↓
Intraday Charting
      ↓
5-Minute Price Action
      ↓
Visual Trade Evaluation
```

---

# Key Design Goals

The project is designed around several principles:

* **Fast** — C++ handles the intraday data download.
* **Automated** — ticker lists can be built from existing stock-analysis reports.
* **Flexible** — stocks can be added from multiple sources or manually.
* **Clean** — duplicate tickers are automatically removed.
* **Readable** — charts emphasize important levels rather than excessive indicators.
* **Repeatable** — old generated files are cleaned before each run.
* **Integrated** — connects portfolio holdings and stock-ranking systems with intraday charting.
* **Beginner-friendly** — charts include explanations of the major indicators.
* **Trading-focused** — emphasizes price action, trend, VWAP, volume, and important support/resistance levels.

---

## Important Files

| File                                  | Purpose                                        |
| ------------------------------------- | ---------------------------------------------- |
| `script/chart.sh`                     | Main program that controls the entire workflow |
| `cpp/src/fetch_intraday.cpp`          | C++ source for downloading intraday data       |
| `cpp/bin/fetch_intraday`              | Compiled C++ downloader                        |
| `py/chart.py`                         | Generates the annotated charts                 |
| `input/tickers.csv`                   | Final ticker list used for the current run     |
| `output/*.csv`                        | Downloaded 5-minute stock data                 |
| `charts/*.png`                        | Finished chart images                          |
| `buy_opp/output/summary_all.csv`      | Source of top `buy_opp` ranked stocks          |
| `intr_buy/output/combined_report.csv` | Source of top `intr_buy` ranked stocks         |

---

*Generated for personal use — focused on speed, clarity, repeatability, and visual evaluation of short-term trading opportunities.*
