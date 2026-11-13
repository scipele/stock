# Multi-Stage Fundamental Valuation Engine

Desktop intrinsic value calculator using a Buffett-style owner earnings framework.

The app:
- pulls SEC fundamentals (companyfacts),
- computes owner earnings inputs (Section 1),
- runs a 10-year DCF with growth fade,
- adds cash and subtracts debt for equity value,
- and displays a detailed report + chart.

---

## Current Model Notes

- **Owner earnings baseline**: `1.03 + 1.04 + 1.05 + 1.06`
- **Maintenance CapEx proxy**: `1.06 = -min(CapEx, Depreciation)` (applied quarterly and annually for history)
- **Debt treatment**: explicit subtraction in equity bridge (`+ cash - debt`)
- **Current-year chart behavior**:
  - current year is shown as **FYE** (YTD reported + estimated remainder from annualized run-rate)
  - projections start in the following year (`E`)
- **Valuation baseline period**: DCF starts from **LTM owner earnings**, shown separately in the report
- **Past section** now shows full-year reported owner earnings only:
  - `Year | Owner Earnings`
  - (no Discount Factor / Past Present Value columns)

---

## Project Structure

[`intr_calc/`](/home/dev/stock/intr_calc/)
```text
intr_calc/
├── py/
│   ├── intr_calc_app.py     # Main UI app + SEC extraction + reporting
│   ├── intr_calc_main.py    # Explicit entrypoint wrapper
│   ├── intr_calc_math.py    # DCF math engine
│   └── intr_calc_format.py  # Number/currency formatting helpers
└── readme.md
```

---

## Requirements

- Python 3.9+
- `matplotlib`
- `tkinter` (usually bundled with Python)

> `yfinance` and `pandas` are no longer required by the current implementation.

Install dependencies (if needed):

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r intr_calc/requirements.txt
```

or for a one-off install:

```bash
python3 -m pip install matplotlib
```

---

## Run

Preferred explicit entrypoint:

```bash
python3 /home/dev/stock/intr_calc/py/intr_calc_main.py
```

Direct app-module run:

```bash
python3 /home/dev/stock/intr_calc/py/intr_calc_app.py
```

---

## Usage

1. Enter ticker and click **Fetch SEC Data**.
2. Review Section 1 line items (1.01–1.11), including source notes.
3. Adjust assumptions as needed:
   - discount rate,
   - start/end growth,
   - terminal growth,
   - margin of safety.
4. Click **Calculate Intrinsic Value**.

---

## Output Summary

The report includes:
- intrinsic value per share,
- current price comparison,
- owner earnings line-by-line data,
- historical full-year owner earnings table,
- 10-year forecast + PV,
- terminal value, enterprise/equity bridge.
