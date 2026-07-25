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
```text
buy_opp/
│
├── script/                              # Workflow scripts
│   ├── buy_opp.sh                       # Step 2: Main workflow controller
│   ├── get_cur_pos_tickers.sh           # Step 3: Extract Schwab positions
│   └── combine_sort_tickers.sh          # Step 6: Combine and sort tickers
│
├── data/                                # Data files
│   ├── tickers_current_positions.csv    # Step 4: Current Schwab positions
│   ├── tickers_s_p_500.csv              # Step 5: S&P 500 ticker list
│   ├── tickers_other.csv                # Step 5: Additional watch list
│   ├── tickers_combined.csv             # Step 7: Final ticker universe
│   └── fundamentals.csv                 # Step 9: Financial data from Python
│
├── py/                                  # Python utilities
│   └── get_financials.py                # Step 8: Update fundamentals.csv
│
├── cpp/                                 # C++ stock scanner
│   ├── bin/
│   │   └── buy_opp                     # Step 10: Compiled scanner executable
│   │
│   ├── include/
│   │   ├── analysis.h
│   │   ├── fundamentals.h
│   │   ├── scoring.h
│   │   ├── yahoo.h
│   │   └── summary.h
│   │
│   └── src/
│       ├── main.cpp                     # Step 10: Main program
│       ├── analysis.cpp
│       ├── fundamentals.cpp
│       ├── scoring.cpp
│       ├── yahoo.cpp
│       └── summary.cpp
│
└── output/
    └── summary_all.csv                  # Step 11: Generated report
```