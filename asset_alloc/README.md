# Asset Allocation Workflow

## 1. User-maintained asset mapping (`asset_map.csv`)

`asset_map.csv` defines how Schwab positions are categorized for the asset allocation analysis.

| Symbol | Description             | Category                | SubCategory | SourceType           | RetirementBucket     | StockPct | BondPct | CashPct | InternationalPct |
| :----- | :---------------------- | :---------------------- | :---------- | :------------------- | :------------------- | -------: | ------: | ------: | ---------------: |
| CGDV   | US Dividend             | Equity                  | ETF         | US Equity            | US Equity            |      100 |       0 |       0 |                0 |
| CGUS   | US Large Blend          | Equity                  | ETF         | US Equity            | US Equity            |      100 |       0 |       0 |                0 |
| DTD    | US Dividend             | Equity                  | ETF         | US Equity            | US Equity            |      100 |       0 |       0 |                0 |
| FNDX   | US Large Blend          | Equity                  | ETF         | US Equity            | US Equity            |      100 |       0 |       0 |                0 |
| NTSX   | Balanced                | Balanced                | ETF         | Balanced Funds       | Balanced Funds       |       60 |      40 |       0 |                0 |
| SCHB   | Schwab Broad Market     | US Total Market         | ETF         | US Equity            | US Equity            |      100 |       0 |       0 |                0 |
| SCHD   | Schwab Dividend         | US Dividend             | ETF         | US Equity            | US Equity            |      100 |       0 |       0 |                0 |
| SCHF   | Schwab International    | International Developed | ETF         | International Equity | International Equity |      100 |       0 |       0 |              100 |
| SCHG   | Schwab Growth           | US Large Growth         | ETF         | US Equity            | US Equity            |      100 |       0 |       0 |                0 |
| SCHM   | Schwab Mid Cap          | US Mid Cap              | ETF         | US Equity            | US Equity            |      100 |       0 |       0 |                0 |
| SCHP   | TIPS                    | TIPS                    | Bond        | Fixed Income         | Fixed Income         |        0 |     100 |       0 |                0 |
| SCHZ   | Aggregate Bond          | Bonds                   | Bond        | Fixed Income         | Fixed Income         |        0 |     100 |       0 |                0 |
| SGOV   | Treasury ETF            | Short Treasury          | Cash        | Fixed Income         | Fixed Income         |        0 |     100 |       0 |                0 |
| SNSXX  | Treasury MM             | Treasury Cash           | Cash        | Cash                 | Cash                 |        0 |       0 |     100 |                0 |
| SWVXX  | Money Market            | Cash                    | Cash        | Cash                 | Cash                 |        0 |       0 |     100 |                0 |
| VOO    | Vanguard S&P 500 ETF    | US Large Blend          | ETF         | US Equity            | US Equity            |      100 |       0 |       0 |                0 |
| VTMFX  | Balanced Fund           | Balanced                | Balanced    | Mutual Fund          | Balanced Funds       |       60 |      40 |       0 |                0 |
| VXUS   | International Developed | Equity                  | ETF         | International Equity | International Equity |      100 |       0 |       0 |              100 |

Positions classified as `Equity` that are not explicitly mapped in `asset_map.csv` are automatically classified as `Individual Stock`.

---

## 2. User-maintained allocation targets (`alloc_target.csv`)

`alloc_target.csv` defines the desired portfolio allocation based on the user's selected risk profile and investment objectives.

| Category                | TargetPercent | Reason                                           |
| :---------------------- | ------------: | :----------------------------------------------- |
| Private Equity          |            25 | 5-year company payout / illiquid asset           |
| US Large Blend          |            20 | Core US equity allocation                        |
| US Total Market         |             5 | Broad market diversification                     |
| US Dividend             |             5 | Dividend income and lower volatility tilt        |
| US Large Growth         |             5 | Long-term growth exposure                        |
| US Mid Cap              |             5 | Mid-cap diversification                          |
| US Value                |             5 | Value diversification                            |
| International Developed |            10 | International diversification                    |
| Emerging Markets        |             5 | Global growth diversification                    |
| Balanced                |             5 | Smoother portfolio behavior                      |
| Bonds                   |             5 | Downturn protection and rebalancing              |
| TIPS                    |             2 | Inflation protection                             |
| Cash                    |             3 | Opportunity fund for market downturns            |
| Individual Stock        |             5 | Personal stock selection / opportunity portfolio |

---

## 3. Schwab positions

The program automatically finds and loads the most recent Schwab positions export.
It selects the newest file matching:
`All-Accounts-Positions-YYYY-MM-DD-HHMMSS.csv`
and prints the selected file path and export timestamp to the terminal during execution.

`schwab.py` is responsible for:

1. Finding the latest Schwab positions CSV.
2. Handling the current Schwab file format, including multiple account sections and repeated headers.
3. Combining positions from the Schwab accounts.
4. Applying `asset_map.csv`.
5. Assigning default classifications to unmapped Schwab equities.
6. Setting the source to `Schwab`.
7. Creating `schwab_assets.csv`.

The parser also excludes kids' accounts from import:
`Indiv_Hailey ...647` and `Indiv_Josh ...792`.

---

## 4. Manual assets

`manual.csv` contains assets that are not included in the Schwab positions export but still need to be included in the overall allocation analysis.

`manual.py` processes these entries and creates:

```text
output/manual_assets.csv
```

Examples may include assets such as private equity or other holdings that are maintained outside of the Schwab account data.

---

## 5. Portfolio processing

The individual asset sources are combined into the portfolio analysis:

```text
Schwab positions
       │
       ▼
schwab_assets.csv
       │
       │
Manual assets
       │
       ▼
manual_assets.csv
       │
       └──────────────┐
                      ▼
                portfolio.py
                      │
                      ▼
                 all_assets.csv
                      │
          ┌───────────┴───────────┐
          ▼                       ▼
 allocation analysis        look-through analysis
          │                       │
          └───────────┬───────────┘
                      ▼
                   reports
```

---

## 6. Output reports

The program generates the following reports:

* `all_assets.csv` — combined portfolio holdings
* `allocation_detail.csv` — detailed allocation calculations
* `allocation_report.csv` — primary allocation report
* `allocation_report.html` — HTML allocation report
* `allocation_retirement.csv` — retirement allocation analysis
* `economic_exposure.csv` — economic/underlying exposure
* `manual_assets.csv` — manually entered assets
* `schwab_assets.csv` — processed Schwab positions

---

## Treeview of all related files

```text
/home/dev/stock/asset_alloc
├── input
│   ├── alloc_target.csv
│   ├── asset_map.csv
│   ├── holding_exposure.csv
│   ├── manual.csv
│   └── retirement_target.csv
├── output
│   ├── all_assets.csv
│   ├── allocation_detail.csv
│   ├── allocation_report.csv
│   ├── allocation_report.html
│   ├── allocation_retirement.csv
│   ├── economic_exposure.csv
│   ├── manual_assets.csv
│   └── schwab_assets.csv
├── py
│   ├── asset_alloc.py
│   ├── dashboard.py
│   ├── lookthrough.py
│   ├── manual.py
│   ├── portfolio.py
│   ├── report.py
│   └── schwab.py
└── script
    ├── asset_alloc.png
    └── asset_alloc.sh
```
