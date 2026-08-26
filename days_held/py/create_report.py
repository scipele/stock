#!/usr/bin/env python3

import csv
import html
from datetime import datetime
from pathlib import Path
import webbrowser


# ------------------------------------------------------------
# Paths
# ------------------------------------------------------------

BASE_DIR = Path("/home/dev/stock/days_held")
OUTPUT_DIR = BASE_DIR / "output"

INPUT_FILE = OUTPUT_DIR / "days_held.csv"
OUTPUT_FILE = OUTPUT_DIR / "days_held.html"


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------

def esc(value):
    """Safely escape text for HTML."""
    return html.escape(str(value))


def fmt_number(value, decimals=2):
    try:
        return f"{float(value):,.{decimals}f}"
    except (ValueError, TypeError):
        return value


def fmt_money(value):
    try:
        return f"${float(value):,.2f}"
    except (ValueError, TypeError):
        return value


def days_class(days):
    """CSS class based on holding period."""

    try:
        days = int(days)
    except (ValueError, TypeError):
        return "days-none"

    if days <= 7:
        return "days-short"

    if days <= 30:
        return "days-medium"

    if days <= 90:
        return "days-long"

    return "days-very-long"


# ------------------------------------------------------------
# Read CSV
# ------------------------------------------------------------

if not INPUT_FILE.exists():
    raise SystemExit(
        f"ERROR: Input file not found:\n{INPUT_FILE}"
    )


with open(
    INPUT_FILE,
    "r",
    newline="",
    encoding="utf-8-sig"
) as f:

    reader = csv.DictReader(f)

    rows = list(reader)


if not rows:
    raise SystemExit("ERROR: days_held.csv contains no positions.")


# ------------------------------------------------------------
# Sort
#
# Longest days held first.
#
# PARTIAL positions have no reliable DaysHeld value and are
# placed at the bottom.
# ------------------------------------------------------------

def sort_key(row):

    status = row.get("Status", "")

    if status == "PARTIAL":
        return -1

    try:
        return int(float(row.get("DaysHeld", 0)))
    except (ValueError, TypeError):
        return -1


rows.sort(
    key=sort_key,
    reverse=True
)


# ------------------------------------------------------------
# Summary
# ------------------------------------------------------------

total_positions = len(rows)

ok_positions = sum(
    1
    for r in rows
    if r.get("Status") == "OK"
)

partial_positions = sum(
    1
    for r in rows
    if r.get("Status") == "PARTIAL"
)


valid_days = []

for row in rows:

    if row.get("Status") != "OK":
        continue

    try:
        valid_days.append(
            int(float(row.get("DaysHeld", 0)))
        )
    except (ValueError, TypeError):
        pass


if valid_days:
    average_days = sum(valid_days) / len(valid_days)
else:
    average_days = 0


# ------------------------------------------------------------
# Report date
# ------------------------------------------------------------

report_date = datetime.now().strftime("%B %-d, %Y")

try:
    report_time = datetime.now().strftime("%-I:%M %p")
except ValueError:
    report_time = datetime.now().strftime("%I:%M %p")


# ------------------------------------------------------------
# Build table
# ------------------------------------------------------------

table_rows = []

for row in rows:

    symbol = row.get("Symbol", "")
    description = row.get("Description", "")

    current_qty = row.get("CurrentQty", "")
    oldest_buy = row.get("OldestBuyDate", "")
    days_held = row.get("DaysHeld", "")
    avg_price = row.get("AvgBuyPrice", "")
    buy_transactions = row.get("BuyTransactions", "")
    status = row.get("Status", "")

    try:
        days_value = int(float(days_held))
    except (ValueError, TypeError):
        days_value = None

    if days_value is not None and status == "OK":
        days_display = str(days_value)
        days_css = days_class(days_value)
    else:
        days_display = "—"
        days_css = "days-none"

    if status == "OK":
        status_html = '<span class="status-ok">OK</span>'
    else:
        status_html = '<span class="status-partial">PARTIAL</span>'

    table_rows.append(
        f"""
        <tr>
            <td class="symbol">{esc(symbol)}</td>

            <td class="description">
                {esc(description)}
            </td>

            <td class="number">
                {fmt_number(current_qty, 4)}
            </td>

            <td class="date">
                {esc(oldest_buy)}
            </td>

            <td class="days {days_css}">
                {days_display}
            </td>

            <td class="money">
                {fmt_money(avg_price)}
            </td>

            <td class="number">
                {esc(buy_transactions)}
            </td>

            <td class="status">
                {status_html}
            </td>
        </tr>
        """
    )


table_html = "\n".join(table_rows)


# ------------------------------------------------------------
# HTML
# ------------------------------------------------------------

page = f"""<!DOCTYPE html>

<html lang="en">

<head>

<meta charset="UTF-8">

<meta name="viewport"
      content="width=device-width, initial-scale=1.0">

<title>Schwab Days Held</title>


<style>

/* ----------------------------------------------------------
   General
   ---------------------------------------------------------- */

* {{
    box-sizing: border-box;
}}

body {{
    margin: 0;
    padding: 30px;

    background: #f4f6f8;

    font-family:
        -apple-system,
        BlinkMacSystemFont,
        "Segoe UI",
        Roboto,
        Arial,
        sans-serif;

    color: #1f2933;
}}


.container {{
    max-width: 1500px;
    margin: 0 auto;
}}


/* ----------------------------------------------------------
   Header
   ---------------------------------------------------------- */

.header {{
    background: white;

    padding: 25px 30px;

    border-radius: 12px;

    box-shadow:
        0 2px 8px rgba(0,0,0,0.08);

    margin-bottom: 20px;
}}


.title {{
    font-size: 30px;
    font-weight: 700;

    margin: 0 0 5px 0;
}}


.subtitle {{
    color: #6b7280;
    font-size: 14px;
}}


/* ----------------------------------------------------------
   Summary cards
   ---------------------------------------------------------- */

.summary {{
    display: grid;

    grid-template-columns:
        repeat(4, 1fr);

    gap: 15px;

    margin-bottom: 20px;
}}


.card {{
    background: white;

    border-radius: 10px;

    padding: 20px;

    box-shadow:
        0 2px 8px rgba(0,0,0,0.06);
}}


.card-label {{
    font-size: 13px;

    color: #6b7280;

    margin-bottom: 8px;

    text-transform: uppercase;

    letter-spacing: 0.5px;
}}


.card-value {{
    font-size: 28px;

    font-weight: 700;
}}


.card-sub {{
    margin-top: 5px;

    font-size: 12px;

    color: #9ca3af;
}}


/* ----------------------------------------------------------
   Table container
   ---------------------------------------------------------- */

.table-container {{
    background: white;

    border-radius: 12px;

    box-shadow:
        0 2px 8px rgba(0,0,0,0.08);

    overflow: hidden;
}}


.table-header {{
    padding: 18px 25px;

    border-bottom:
        1px solid #e5e7eb;

    font-weight: 600;
}}


.table-scroll {{
    overflow-x: auto;
}}


table {{
    width: 100%;

    border-collapse: collapse;

    font-size: 14px;
}}


thead {{
    background: #f8fafc;
}}


th {{
    text-align: left;

    padding: 13px 15px;

    border-bottom:
        2px solid #e5e7eb;

    color: #4b5563;

    font-size: 12px;

    text-transform: uppercase;

    letter-spacing: 0.4px;

    white-space: nowrap;
}}


td {{
    padding: 13px 15px;

    border-bottom:
        1px solid #edf0f2;

    white-space: nowrap;
}}


tbody tr:hover {{
    background: #f8fafc;
}}


/* ----------------------------------------------------------
   Columns
   ---------------------------------------------------------- */

.symbol {{
    font-weight: 700;

    font-size: 15px;
}}


.description {{
    color: #4b5563;

    min-width: 300px;
}}


.number {{
    text-align: right;

    font-variant-numeric:
        tabular-nums;
}}


.money {{
    text-align: right;

    font-variant-numeric:
        tabular-nums;
}}


.date {{
    white-space: nowrap;
}}


.days {{
    text-align: center;

    font-weight: 700;

    font-size: 15px;

    border-radius: 6px;
}}


/* ----------------------------------------------------------
   Days Held highlighting
   ---------------------------------------------------------- */

.days-short {{
    background: #fff3cd;

    color: #856404;
}}


.days-medium {{
    background: #e8f4ff;

    color: #155b8a;
}}


.days-long {{
    background: #e7f5e9;

    color: #1b6b35;
}}


.days-very-long {{
    background: #dff3e3;

    color: #14532d;
}}


.days-none {{
    color: #9ca3af;
}}


/* ----------------------------------------------------------
   Status
   ---------------------------------------------------------- */

.status {{
    text-align: center;
}}


.status-ok {{
    display: inline-block;

    padding: 4px 9px;

    border-radius: 20px;

    background: #e7f5e9;

    color: #166534;

    font-weight: 600;

    font-size: 12px;
}}


.status-partial {{
    display: inline-block;

    padding: 4px 9px;

    border-radius: 20px;

    background: #fff3cd;

    color: #92400e;

    font-weight: 600;

    font-size: 12px;
}}


/* ----------------------------------------------------------
   Footer
   ---------------------------------------------------------- */

.footer {{
    padding: 18px 5px;

    color: #9ca3af;

    font-size: 12px;

    text-align: right;
}}


/* ----------------------------------------------------------
   Responsive
   ---------------------------------------------------------- */

@media (max-width: 900px) {{

    body {{
        padding: 15px;
    }}

    .summary {{
        grid-template-columns:
            repeat(2, 1fr);
    }}

}}

</style>

</head>


<body>

<div class="container">


    <div class="header">

        <div class="title">
            Schwab Days Held
        </div>

        <div class="subtitle">
            Current equity positions sorted by
            longest holding period first
            &nbsp;•&nbsp;
            {esc(report_date)}
            at {esc(report_time)}
        </div>

    </div>


    <div class="summary">


        <div class="card">

            <div class="card-label">
                Equity Positions
            </div>

            <div class="card-value">
                {total_positions}
            </div>

            <div class="card-sub">
                Current Schwab positions
            </div>

        </div>


        <div class="card">

            <div class="card-label">
                Fully Matched
            </div>

            <div class="card-value">
                {ok_positions}
            </div>

            <div class="card-sub">
                Transaction history sufficient
            </div>

        </div>


        <div class="card">

            <div class="card-label">
                Partial
            </div>

            <div class="card-value">
                {partial_positions}
            </div>

            <div class="card-sub">
                Transaction history incomplete
            </div>

        </div>


        <div class="card">

            <div class="card-label">
                Average Days Held
            </div>

            <div class="card-value">
                {average_days:.1f}
            </div>

            <div class="card-sub">
                Fully matched positions
            </div>

        </div>


    </div>


    <div class="table-container">


        <div class="table-header">

            Current Equity Positions

        </div>


        <div class="table-scroll">

            <table>

                <thead>

                    <tr>

                        <th>Symbol</th>

                        <th>Description</th>

                        <th>Shares</th>

                        <th>Oldest Buy</th>

                        <th>Days Held ↓</th>

                        <th>Avg Cost</th>

                        <th>Buys</th>

                        <th>Status</th>

                    </tr>

                </thead>


                <tbody>

                    {table_html}

                </tbody>

            </table>

        </div>

    </div>


    <div class="footer">

        Schwab Days Held Report

    </div>


</div>

</body>

</html>
"""


# ------------------------------------------------------------
# Write HTML
# ------------------------------------------------------------

with open(
    OUTPUT_FILE,
    "w",
    encoding="utf-8"
) as f:

    f.write(page)


print()
print("HTML report created:")
print(OUTPUT_FILE)
print()


# ------------------------------------------------------------
# Open default browser
# ------------------------------------------------------------

webbrowser.open(
    OUTPUT_FILE.resolve().as_uri()
)