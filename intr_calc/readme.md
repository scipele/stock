# Multi-Stage Fundamental Valuation Engine

A desktop DCF (Discounted Cash Flow) valuation tool built with Python, Tkinter, yfinance, and Matplotlib.

It projects revenue with a constant CAGR, fades net profit margin over a 5-year forecast period, discounts the resulting net income, and applies an exit P/S multiple to estimate intrinsic value per share.

---

## Features

- Fetch live financial data from Yahoo Finance (revenue, net margin, cash, debt, shares, current price)
- Manual override of all key assumptions (CAGR, margins, discount rate, exit multiple, margin of safety)
- 5-year explicit forecast with linear margin fade
- Terminal value using Year-5 Revenue × Exit P/S Multiple
- Clear step-by-step calculation report with abbreviated currency (B / T)
- Historical + projected Net Income bar chart (years auto-update based on current calendar year)
- Margin of Safety “Maximum Buy Price”

---

## Project Structure
intr_calc/
├── output/                 # (reserved for future exports)
├── py/
│   └── intr_calc.py        # Main application
└── script/
├── intr_calc.png       # Screenshot
└── intr_calc.sh        # Launcher script


---

## Requirements

- Python 3.9+
- Packages:
  - `yfinance`
  - `matplotlib`
  - `pandas`
  - `tkinter` (usually included with Python)

Install dependencies (if needed):

Manual run:

```bash
/home/dev/py/.venv/bin/pip install yfinance matplotlib pandas
