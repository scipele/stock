# Asset Allocation Workflow

## 1. - User to manually setup relative mapping of () positions held (asset_map.csv)

| Symbol | Description | Category | SubCategory | SourceType | RetirementBucket | StockPct | BondPct | CashPct | InternationalPct |
|:---|:---|:---|:---|:---|:---|---:|---:|---:|---:|
| CGDV | US Dividend | Equity | ETF | US Equity | US Equity | 100 | 0 | 0 | 0 |
| CGUS | US Large Blend | Equity | ETF | US Equity | US Equity | 100 | 0 | 0 | 0 |
| DTD | US Dividend | Equity | ETF | US Equity | US Equity | 100 | 0 | 0 | 0 |
| FNDX | US Large Blend | Equity | ETF | US Equity | US Equity | 100 | 0 | 0 | 0 |
| NTSX | Balanced | Balanced | ETF | Balanced Funds | Balanced Funds | 60 | 40 | 0 | 0 |
| SCHB | Schwab Broad Market | US Total Market | ETF | US Equity | US Equity | 100 | 0 | 0 | 0 |
| SCHD | Schwab Dividend | US Dividend | ETF | US Equity | US Equity | 100 | 0 | 0 | 0 |
| SCHF | Schwab International | International Developed | ETF | International Equity | International Equity | 100 | 0 | 0 | 100 |
| SCHG | Schwab Growth | US Large Growth | ETF | US Equity | US Equity | 100 | 0 | 0 | 0 |
| SCHM | Schwab Mid Cap | US Mid Cap | ETF | US Equity | US Equity | 100 | 0 | 0 | 0 |
| SCHP | TIPS | TIPS | Bond | Fixed Income | Fixed Income | 0 | 100 | 0 | 0 |
| SCHZ | Aggregate Bond | Bonds | Bond | Fixed Income | Fixed Income | 0 | 100 | 0 | 0 |
| SGOV | Treasury ETF | Short Treasury | Cash | Fixed Income | Fixed Income | 0 | 100 | 0 | 0 |
| SNSXX | Treasury MM | Treasury Cash | Cash | Cash | Cash | 0 | 0 | 100 | 0 |
| SWVXX | Money Market | Cash | Cash | Cash | Cash | 0 | 0 | 100 | 0 |
| VOO | Vanguard S&P 500 ETF | US Large Blend | ETF | US Equity | US Equity | 100 | 0 | 0 | 0 |
| VTMFX | Balanced Fund | Balanced | Balanced | Mutual Fund | Balanced Funds | 60 | 40 | 0 | 0 |
| VXUS | International Developed | Equity | ETF | International Equity | International Equity | 100 | 0 | 0 | 100 |
| JH Multimanager 2040 Lifetime | JH Multimanager 2040 Lifetime | Balanced | Balanced | Mutual Fund | Balanced Funds | 70 | 30 | 0 | 0 |
| AF The Growth Fund of America | AF The Growth Fund of America | US Large Growth | Equity | Mutual Fund | US Equity | 100 | 0 | 0 | 0 |
| DFA US Targeted Value Fund | DFA US Targeted Value Fund | US Value | Equity | Mutual Fund | US Equity | 100 | 0 | 0 | 0 |
| Fidelity ContraFund | Fidelity ContraFund | US Large Growth | Equity | Mutual Fund | US Equity | 100 | 0 | 0 | 0 |
| AF American Balanced Fund | AF American Balanced Fund | Balanced | Balanced | Mutual Fund | Balanced Funds | 60 | 40 | 0 | 0 |

## 2. User to setup allocation target based on their risk profile in csv file (alloc_target.csv)

| Category | TargetPercent | Reason |
|:---|---:|:---|
| Private Equity | 25 | 5-year company payout / illiquid asset |
| US Large Blend | 20 | Core US equity allocation |
| US Total Market | 5 | Broad market diversification |
| US Dividend | 5 | Dividend income and lower volatility tilt |
| US Large Growth | 5 | Long-term growth exposure |
| US Mid Cap | 5 | Mid-cap diversification |
| US Value | 5 | Value diversification |
| International Developed | 10 | International diversification |
| Emerging Markets | 5 | Global growth diversification |
| Balanced | 5 | Smoother portfolio behavior |
| Bonds | 5 | Downturn protection and rebalancing |
| TIPS | 2 | Inflation protection |
| Cash | 3 | Opportunity fund for market downturns |
| Individual Stock | 5 | Personal stock selection / opportunity portfolio |

## 3. User to 




## Treeview of all related files
```text
/home/dev/stock/asset_alloc
├── input
│   ├── alloc_target.csv
│   ├── asset_map.csv
│   ├── holding_exposure.csv
│   ├── jh_map.csv
│   ├── john_hancock.txt
│   ├── manual.csv
│   └── retirement_target.csv
├── output
│   ├── all_assets.csv
│   ├── allocation_detail.csv
│   ├── allocation_report.csv
│   ├── allocation_report.html
│   ├── allocation_retirement.csv
│   ├── economic_exposure.csv
│   ├── jh_assets.csv
│   ├── manual_assets.csv
│   └── schwab_assets.csv
├── py
│   ├── asset_alloc.py
│   ├── dashboard.py
│   ├── jh.py
│   ├── lookthrough.py
│   ├── manual.py
│   ├── portfolio.py
│   ├── report.py
│   └── schwab.py
└── script
    ├── asset_alloc.png
    └── asset_alloc.sh
```