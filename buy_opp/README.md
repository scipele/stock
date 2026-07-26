# Stock - Buy Opportunity

## Workflow
1. Download Schwab positions
2. Extract current position tickers
3. Combine:
   - Current positions
   - S&P 500
   - Additional watch list
4. Update fundamentals using Python/yfinance
5. Run C++ scanner
6. Generate stock opportunity report

Run everything:
./script/buy_opp.sh

```text
buy_opp/
│
├── script/                             # Workflow scripts
│   ├── buy_opp.sh                      # Step 1: Main workflow controller
│   ├── get_cur_pos_tickers.sh          # Step 2a: Extract Schwab positions
│   └── combine_sort_tickers.sh         # Step 3: Combine and sort tickers
│
├── data/                               # Data files
│   ├── tickers_current_positions.csv   # Step 2b: Current Schwab positions
│   ├── tickers_s_p_500.csv             # Step 3a: S&P 500 ticker list
│   ├── tickers_other.csv               # Step 3b: Additional tickers
│   ├── tickers_combined.csv            # Step 3c: Final ticker
│   └── fundamentals.csv                # Step 4a: Financial data from Python
│
├── py/                                 # Python utilities
│   └── get_financials.py               # Step 4: Update fundamentals.csv
│
├── cpp/                                # C++ stock scanner
│   ├── bin/
│   │   └── buy_opp                     # Step 5: Run Compiled scanner executable
│   │
│   ├── include/                        # Header Files
│   │   ├── analysis.h
│   │   ├── fundamentals.h
│   │   ├── scoring.h
│   │   ├── yahoo.h
│   │   └── summary.h
│   │
│   └── src/                            # C++ Source / Implementation Files
│       ├── main.cpp                     
│       ├── analysis.cpp
│       ├── fundamentals.cpp
│       ├── scoring.cpp
│       ├── yahoo.cpp
│       └── summary.cpp
│
└── output/
    └── summary_all.csv                  # Step 5a: Generated report
```