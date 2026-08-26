#!/usr/bin/env python3

import csv
import html
from collections import defaultdict
from datetime import datetime
from pathlib import Path
import webbrowser

BASE_DIR = Path("/home/dev/stock/gain_loss")
OUTPUT_DIR = BASE_DIR / "output"
INPUT_FILE = OUTPUT_DIR / "gain_loss.csv"
OUTPUT_FILE = OUTPUT_DIR / "days_held.html"


def esc(value):
    return html.escape(str(value))


def fmt_signed_money(value):
    value = float(value)
    if value < 0:
        return f"({abs(value):,.2f})"
    return f"{value:,.2f}"


def fmt_total(value):
    value = float(value)
    if value < 0:
        return f"({abs(value):,.2f})"
    return f"{value:,.2f}"


if not INPUT_FILE.exists():
    raise SystemExit(f"ERROR: Input file not found:\n{INPUT_FILE}")

with open(INPUT_FILE, "r", newline="", encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)
    rows = list(reader)

if not rows:
    raise SystemExit("ERROR: gain_loss.csv contains no data.")

for row in rows:
    row["Avg_Days_Held"] = int(float(row.get("Avg_Days_Held", 0) or 0))
    row["Gain_Loss"] = float(row.get("Gain_Loss", 0.0) or 0.0)

by_date = defaultdict(list)
for row in rows:
    by_date[row["Date"]].append(row)

for key in by_date:
    by_date[key].sort(key=lambda item: item["Symbol"])

report_date = datetime.now().strftime("%B %-d, %Y")
try:
    report_time = datetime.now().strftime("%-I:%M %p")
except ValueError:
    report_time = datetime.now().strftime("%I:%M %p")

total_gain = sum(float(r["Gain_Loss"]) for r in rows)

sections_html = []
for date_key in sorted(by_date):
    day_rows = by_date[date_key]
    day_total = sum(float(r["Gain_Loss"]) for r in day_rows)

    item_rows = []
    for item in day_rows:
        item_rows.append(
            f"""
            <tr>
                <td class=\"symbol\">{esc(item['Symbol'])}</td>
                <td class=\"days\">{item['Avg_Days_Held']}</td>
                <td class=\"gain\">{fmt_signed_money(item['Gain_Loss'])}</td>
            </tr>
            """
        )

    sections_html.append(
        f"""
        <div class=\"date-block\">
            <div class=\"date-label\">Date {esc(date_key)}:</div>
            <table class=\"day-table\" cellspacing=\"0\" cellpadding=\"0\">
                <thead>
                    <tr>
                        <th>Symbol</th>
                        <th>Avg_Days_Held</th>
                        <th>Gain_Loss</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(item_rows)}
                </tbody>
            </table>
            <div class=\"day-total\">Total &nbsp; {fmt_total(day_total)}</div>
        </div>
        """
    )

page = f"""<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"UTF-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />
  <title>Stock Gain / Loss</title>
  <style>
    body {{
      margin: 0;
      padding: 30px;
      background: #f3f4f6;
      font-family: Arial, sans-serif;
      color: #111827;
    }}
    .container {{
      max-width: 1100px;
      margin: 0 auto;
      background: white;
      border-radius: 12px;
      box-shadow: 0 4px 16px rgba(0,0,0,0.08);
      padding: 24px 28px;
    }}
    h1 {{
      margin: 0 0 10px 0;
      font-size: 2rem;
    }}
    .subtitle {{
      margin-bottom: 22px;
      color: #6b7280;
      font-size: 14px;
    }}
    .date-block {{
      margin-bottom: 26px;
      border-top: 1px solid #e5e7eb;
      padding-top: 18px;
    }}
    .date-label {{
      font-weight: 700;
      font-size: 1.2rem;
      margin-bottom: 8px;
    }}
    .day-table {{
      width: 100%;
      border-collapse: collapse;
      table-layout: fixed;
    }}
    th, td {{
      padding: 8px 12px;
      text-align: left;
      border-bottom: 1px solid #e5e7eb;
    }}
    th {{
      font-size: 12px;
      letter-spacing: 0.04em;
      text-transform: uppercase;
      color: #4b5563;
      background: #f9fafb;
    }}
    .symbol {{
      width: 50%;
      font-weight: 600;
    }}
    .days {{
      width: 20%;
      text-align: right;
      font-variant-numeric: tabular-nums;
    }}
    .gain {{
      width: 30%;
      text-align: right;
      font-variant-numeric: tabular-nums;
      font-weight: 700;
    }}
    .day-total {{
      margin-top: 8px;
      text-align: right;
      font-weight: 700;
      font-size: 1.05rem;
    }}
    .period-total {{
      margin-top: 20px;
      border-top: 2px solid #111827;
      padding-top: 12px;
      text-align: right;
      font-size: 1.15rem;
      font-weight: 700;
    }}
  </style>
</head>
<body>
  <div class=\"container\">
    <h1>Stock Gain / Loss</h1>
    <div class=\"subtitle\">{esc(report_date)} at {esc(report_time)}</div>
    {''.join(sections_html)}
    <div class=\"period-total\">Total Gain for Period Entered &nbsp; {fmt_total(total_gain)}</div>
  </div>
</body>
</html>
"""

OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    f.write(page)

print()
print("HTML report created:")
print(OUTPUT_FILE)
print()

webbrowser.open(OUTPUT_FILE.resolve().as_uri())
