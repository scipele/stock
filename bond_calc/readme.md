# Bond Calculator

Analyzes Fixed Income positions from a Schwab-style multi-account positions export.

## What it does

1. **Auto-finds** the newest `All-Accounts-Positions-YYYY-MM-DD-HHMMSS.csv`
2. **Filters** only rows where `Asset Type = Fixed Income`
3. **Parses** each Treasury (CUSIP, description → coupon rate + maturity date)
4. **Builds remaining cash flows** by calendar period `yyyy_mm`
5. **Computes** YTM (from market price) and CAGR (from cost basis) per bond + portfolio
6. **Outputs** Excel tables + stacked column chart with cumulative on secondary axis

## Directory layout

```
bond_calc/
├── output/          # generated Excel + PNG
├── py/
│   ├── bond_calculator.py
│   └── sample_positions.txt
├── readme.md
└── script/
    └── run_bond_calc.sh
```

## Requirements (Ubuntu)

```bash
sudo apt update
sudo apt install -y python3 python3-pip
pip3 install --user pandas numpy matplotlib scipy openpyxl
```

## Quick start

Drop your Schwab export (named like `All-Accounts-Positions-2026-11-24-125028.csv`) into:

- the current directory, or
- `~/Downloads`, or
- `~/Desktop`, or
- the `bond_calc` folder itself

Then:

```bash
cd /path/to/bond_calc
chmod +x script/run_bond_calc.sh
./script/run_bond_calc.sh
```

The program automatically picks the **newest** file by the date/time in the filename and sets the valuation date from it.

### Other ways to run

```bash
# Search only a specific folder
./script/run_bond_calc.sh --dir ~/Downloads

# Explicit file
./script/run_bond_calc.sh -i ~/Downloads/All-Accounts-Positions-2026-11-24-125028.csv

# Override valuation date
./script/run_bond_calc.sh --valuation-date 2026-11-25
```

## Notes / assumptions

- Face value = Qty column (standard for Treasuries quoted as % of par).
- Coupons are assumed semi-annual and aligned to the maturity day-of-month.
- Accrued interest is ignored (clean ≈ dirty). Near a coupon date the difference is small.
- Day-count for year fractions is Actual/365.25.
- Filename pattern required for auto-detect: `All-Accounts-Positions-YYYY-MM-DD-HHMMSS.csv`

## Sample bonds in the included dump

| Symbol     | Type   | Coupon | Maturity   | Face    |
|------------|--------|--------|------------|---------|
| 912797WS2  | T-Bill | 0 %    | 2027-02-02 | 101,000 |
| 91282CJG7  | T-Note | 4.875% | 2030-10-31 |  36,000 |
| 91282CMC2  | T-Note | 4.500% | 2031-12-31 | 100,000 |
