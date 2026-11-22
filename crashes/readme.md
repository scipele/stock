# Historical Financial Crash & Pullback Analysis

How to run


Step 1: Get the free API key (takes about 1 minute)
   Open any browser (Chrome, Firefox, Edge, whatever you normally use).
   Go to this page:
   [fredaccount.stlouisfed.org/login/secure](https://fredaccount.stlouisfed.org/login/secure)
   Click Register (or “Create New Account”) and sign up with your email + a password.
   After you log in, go here:
   [fred.stlouisfed.org/docs/api/api_key.html](https://fred.stlouisfed.org/docs/api/api_key.html)
   On that page you will see a button to Request API Key. Click it.
   Copy the long 32-character key they give you (it looks something like a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6).
   That’s the only time you need a browser.

Step 2: Put the key into your terminal
   In the same terminal where you run the script, type this (replace the fake key with the real one you just copied):

cd /home/dev/stock/crashes/script
export FRED_API_KEY="5b74460e7cfb6a4d5288e3fae052c271"
./crashes.sh

A Python pipeline that fetches weekly historical market and macroeconomic data from **FRED** and **Yahoo Finance**, aligns all series to Friday closes (`W-FRI`), normalizes timelines relative to each crash's cycle peak (`Week 0`), and exports a multi-tab Excel workbook (`crash_history_analysis.xlsx`) for cross-era graphing.

---

## Directory Structure

```text
/home/dev/stock/crashes/
├── output/
│   └── crash_history_analysis.xlsx   # Generated multi-tab Excel workbook
├── py/
│   └── crashes.py                    # Main data fetching & normalization script
├── script/
│   └── crashes.sh                    # Executable Bash runner using .venv
└── README.md                         # Project documentation
```

---

## Prerequisites & Setup

The project runs using the shared virtual environment at `/home/dev/py/.venv`.

### Required Python Packages
- `pandas`
- `yfinance`
- `openpyxl`
- `requests`

To install or update dependencies:
```bash
/home/dev/py/.venv/bin/pip install pandas yfinance openpyxl requests
```

---

## Usage

Run the pipeline from any working directory using the Bash runner script:

```bash
/home/dev/stock/crashes/script/crashes.sh
```

The script automatically resolves project paths and writes the output workbook to:
`/home/dev/stock/crashes/output/crash_history_analysis.xlsx`

---

## Included Historical Events

Each event is anchored to **Week 0** (the Friday close of the cycle peak preceding the downturn) with a default lookback window of **52 weeks (`Week -52`)** through **full S&P 500 price recovery**:

| Crash ID | Event Name | Peak Date (`Week 0`) | Trough Date | Recovery Date |
| :--- | :--- | :--- | :--- | :--- |
| `1973_STAG` | 1973–74 Stagflation | 1973-01-12 | 1974-10-04 | 1980-07-18 |
| `1980_VOLC` | 1980 Volcker Shock | 1980-02-15 | 1980-03-28 | 1980-07-18 |
| `1981_RECS` | 1981–82 Double-Dip Bear | 1980-11-28 | 1982-08-13 | 1982-11-05 |
| `1987_BLKM` | 1987 Black Monday | 1987-08-21 | 1987-12-04 | 1989-07-28 |
| `2000_DOTC` | 2000 Dot-Com Bust | 2000-03-24 | 2002-10-11 | 2007-05-25 |
| `2008_GFC` | 2008 Financial Crisis | 2007-10-12 | 2009-03-06 | 2013-03-29 |
| `2020_COVD` | 2020 COVID Crash | 2020-02-21 | 2020-03-20 | 2020-08-21 |
| `2022_INFL` | 2022 Inflation Bear | 2021-12-31 | 2022-10-14 | 2024-01-19 |

---

## Data Sources & Normalization Methodology

All daily and monthly series are resampled to **Friday weekly closes (`W-FRI`)** with missing holiday/monthly points forward-filled.

| Metric | Source / Ticker | Normalization Method |
| :--- | :--- | :--- |
| **US Equities (S&P 500)** | Yahoo (`^GSPC`) | Indexed to `100` at Week 0: `(Price_t / Price_0) * 100` |
| **Overnight Interest Rate** | FRED (`DFF` - Effective Fed Funds) | Percentage point spread vs. Week 0: `Rate_t - Rate_0` |
| **10-Year Treasury Yield** | FRED (`DGS10`) | Percentage point spread vs. Week 0: `Yield_t - Yield_0` |
| **Gold Price** | FRED (`GOLDAMGBD228NLBM`) + Yahoo (`GC=F`) | Indexed to `100` at Week 0: `(Price_t / Price_0) * 100` |
| **Real Estate** | Yahoo (`VNQ`) + FRED (`CSUSHPINSA`) | Indexed to `100` at Week 0: `(Index_t / Index_0) * 100` |
| **WTI Crude Oil** | FRED (`DCOILWTICO` + `MCOILWTICO`) | Indexed to `100` at Week 0: `(Price_t / Price_0) * 100` |
| **Corporate Credit Spread** | FRED (`BAA` minus `AAA`) | Percentage point spread vs. Week 0: `Spread_t - Spread_0` |
| **Market Volatility** | Yahoo (`^VIX`, 1990+) | Raw Friday close |

---

## Excel Workbook Tabs

1. **`Event_Metadata`**: Qualitative summary of catalysts, Fed monetary policy responses, peak/trough/recovery dates, relative week durations, and max S&P 500 drawdown percentages.
2. **`Raw_And_Normalized_Data`**: Master long-format dataset stacking all crashes sequentially by `Crash_ID` and `Rel_Week`.
3. **Pre-Pivoted Chart Tabs** (ready for direct multi-crash line charting with `Rel_Week` on the X-axis):
   - `Chart_SP500_Norm`
   - `Chart_FedFunds_Diff`
   - `Chart_10Y_Diff`
   - `Chart_Gold_Norm`
   - `Chart_RealEstate_Norm`
   - `Chart_Oil_Norm`

---

## Customization

Edit the configuration block at the top of `/home/dev/stock/crashes/py/crashes.py`:
- **`PRE_CRASH_WEEKS`**: Adjust the pre-peak lookback window (default: `52`).
- **`FALLBACK_POST_WEEKS`**: Default post-peak window when `"recovery_date": None` is used for ongoing pullbacks (default: `156`).
- **`CRASH_EVENTS`**: Add, remove, or modify event dictionaries to recalculate the entire workbook on the next run.
