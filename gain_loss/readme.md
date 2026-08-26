# Gain / Loss Calculator

This project follows the same overall structure as the original Schwab stock utility but is focused on computing realized gain/loss by calendar day for a user-selected date range.

## Overview

- Bash script launches the workflow.
- C++ program reads the latest Schwab CSV exports and calculates gain/loss by date and symbol.
- Python builds the HTML report.

The report groups realized symbol activity by date and shows:
- symbol
- average days held for matched buy/sell lots
- gain or loss for that symbol on that date
- a daily total and overall total for the selected range

## Workflow

1. Find the newest Schwab Positions export in /home/ts/Downloads.
2. Find the newest Schwab Transactions export in /home/ts/Downloads.
3. Copy both exports into output/.
4. Run the C++ gain/loss calculator for the selected date range.
5. Generate the HTML report from gain_loss.csv.
6. Open the report in the default browser.

## Example usage

```bash
cd /home/dev/stock/gain_loss
./script/gain_loss.sh 08/25/2026 08/26/2026
```

If no dates are provided, the script prompts for them interactively.

## Folder structure

```text
/home/dev/stock/gain_loss
├── cpp
│   ├── bin
│   └── src
│       └── gain_loss.cpp
├── output
│   ├── days_held.html
│   ├── gain_loss.csv
│   ├── positions.csv
│   └── transactions.csv
├── py
│   └── create_report.py
├── readme.md
└── script
    ├── gain_loss.sh
    ├── days_held.sh
    └── gain_loss.png
```

## Output

- gain_loss.csv: daily symbol-level output from the C++ program.
- days_held.html: HTML summary report generated from the CSV.
- positions.csv and transactions.csv: copied source data used for the calculation.

## Logic notes

The core C++ logic reuses the CSV parsing and transaction handling patterns from the original stock utility, but it focuses on FIFO matched buy/sell lots to estimate:

- realized gain or loss per stock
- average days held for matched pairs
- total gain for the selected date window

This is designed for Schwab export files and expects the standard Schwab headers used by the Position and Transactions reports.
