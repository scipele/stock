# Asset Allocation Workflow

## 1. User-maintained asset definitions (`asset_definitions.csv`)

`asset_definitions.csv` is the single source of truth for position classification and holding exposure used by the allocation analysis.

| Symbol | Category | RetirementBucket | StockPct | BondPct | CashPct | InternationalPct |
| :----- | :------- | :--------------- | -------: | ------: | ------: | ---------------: |
| CGDV   | US Dividend | US Dividend | 100 | 0 | 0 | 0 |
| CGUS   | US Large Blend | US Equity | 100 | 0 | 0 | 0 |
| SCHP   | TIPS | Fixed Income | 0 | 100 | 0 | 0 |
| SGOV   | Cash Equiv (SWVXX_Short Treasury SGOV) | Fixed Income | 0 | 0 | 100 | 0 |
| SWVXX  | Cash Equiv (SWVXX_Short Treasury SGOV) | Cash | 0 | 0 | 100 | 0 |

Positions classified as `Equity` that are not explicitly mapped in `asset_definitions.csv` are automatically classified as `Individual Stock`.

---

## 2. User-maintained allocation targets (`alloc_target.csv`)

`alloc_target.csv` defines the desired portfolio targets by bucket. Each category has separate non-taxable and taxable targets, and the report computes the combined target percentage from the relative totals of those two groups.

| Category | Non_Tax_Target_Pct | Taxable_Target_Pct | Reason |
| :------- | ----------------: | ----------------: | :----- |
| US Large Blend | 15.0 | 17.0 | Core US equity allocation |
| US Value | 8.0 | 8.0 | Value diversification |
| International Developed | 16.0 | 17.0 | International diversification |

---

## 3. Current workflow

The program uses a simplified workflow with the active files below:

```text
all_assets.csv
       │
       ▼
asset_alloc.py
       │
       ▼
allocation_retirement.csv
       │
       ▼
dashboard.py
       │
       ▼
allocation_report.html
```

This workflow does not include the old combined John Hancock + Schwab aggregation path.

---

## 4. Output reports

The program generates the following reports:

* `all_assets.csv` — portfolio holdings used as the analytical input
* `allocation_retirement.csv` — retirement allocation analysis
* `allocation_report.html` — final dashboard report
* `economic_exposure.csv` — economic/underlying exposure

---

## Treeview of active files

```text
/home/dev/stock/asset_alloc
├── input
│   ├── alloc_target.csv
│   ├── asset_definitions.csv
│   └── manual.csv
├── output
│   ├── all_assets.csv
│   ├── allocation_report.html
│   ├── allocation_retirement.csv
│   └── economic_exposure.csv
├── py
│   ├── asset_alloc.py
│   └── dashboard.py
├── script
│   └── asset_alloc.sh
└── README.md
```
