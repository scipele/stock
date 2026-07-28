#!/home/dev/py/.venv/bin/python
from pathlib import Path
import pandas as pd

BASE_DIR = Path("/home/dev/stock/asset_alloc")
OUTPUT_DIR = BASE_DIR / "output"
INPUT_DIR = BASE_DIR / "input"

DETAIL_FILE = OUTPUT_DIR / "allocation_detail.csv"
RETIREMENT_FILE = OUTPUT_DIR / "allocation_retirement.csv"
ALLOC_TARGET_FILE = INPUT_DIR / "alloc_target.csv"
RETIREMENT_TARGET_FILE = INPUT_DIR / "retirement_target.csv"
EXPOSURE_FILE = OUTPUT_DIR / "economic_exposure.csv"
HTML_FILE = OUTPUT_DIR / "allocation_report.html"

# --------------------------------------------------
# Formatting & Calculations
# --------------------------------------------------
def money(value):
    if pd.isna(value): return ""
    return f"${value:,.2f}"

def percent(value):
    if pd.isna(value): return ""
    return f"{value:.1f}%"

def add_totals(df, label_column):
    """Appends a summary/total row to the dataframe."""
    df = df.copy()
    
    # Identify numeric columns
    numeric_cols = df.select_dtypes(include=['number']).columns
    
    # Create total row mapping
    total_row = {col: df[col].sum() for col in numeric_cols}
    
    # Keep sum for value and standard percentages, clear out difference percentages
    for col in list(total_row.keys()):
        # Explicitly keep sums for Current % and TargetPercent, skip others like Difference %
        if col not in ["Value", "Current %", "TargetPercent"]:
            total_row[col] = pd.NA

    # Set label for the row (e.g., "Total")
    total_row[label_column] = "Total"
    
    # Append the total row to the dataframe
    return pd.concat([df, pd.DataFrame([total_row])], ignore_index=True)

def format_dataframe(df):
    df = df.copy()
    for col in df.columns:
        if col in ["Value", "Target $", "Difference $"]:
            df[col] = df[col].apply(money)
        elif ("%" in col or "Percent" in col):
            df[col] = df[col].apply(percent)
    return df

def table(df):
    return df.to_html(
        index=False,
        classes="table",
        border=0
    )

# --------------------------------------------------
# Data Loading
# --------------------------------------------------
def load_data():
    detail = pd.read_csv(DETAIL_FILE)
    retirement = pd.read_csv(RETIREMENT_FILE)
    exposure = pd.read_csv(EXPOSURE_FILE)
    alloc_target = pd.read_csv(ALLOC_TARGET_FILE)
    retirement_target = pd.read_csv(RETIREMENT_TARGET_FILE)
    return (detail, retirement, exposure, alloc_target, retirement_target)


# --------------------------------------------------
# Apply Targets
# --------------------------------------------------
def apply_targets(detail, retirement, alloc_target, retirement_target):

    # Detail report already contains targets
    if "TargetPercent" not in detail.columns:
        detail = detail.merge(
            alloc_target,
            on="Category",
            how="left"
        )
        detail["TargetPercent"] = detail["TargetPercent"].fillna(0)

    detail["Difference %"] = (
        detail["Current %"] -
        detail["TargetPercent"]
    )

    # Retirement targets + reasons
    retirement = retirement.merge(
        retirement_target[
            [
                "RetirementBucket",
                "TargetPercent",
                "Reason"
            ]
        ],
        on="RetirementBucket",
        how="left"
    )

    retirement["TargetPercent"] = (
        retirement["TargetPercent"]
        .fillna(0)
    )

    retirement["Reason"] = (
        retirement["Reason"]
        .fillna("")
    )

    retirement["Difference %"] = (
        retirement["Current %"]
        - retirement["TargetPercent"]
    )

    retirement = retirement[
        [
            "RetirementBucket",
            "Value",
            "Current %",
            "TargetPercent",
            "Difference %",
            "Reason"
        ]
    ]

    return detail, retirement


def format_exposure(exposure):
    """
    Converts economic exposure into dashboard standard columns.
    """

    df = exposure.copy()

    df = df.rename(
        columns={
            "AssetClass": "Category"
        }
    )

    total = df["Value"].sum()

    df["Current %"] = (
        df["Value"] / total * 100
    )

    df["TargetPercent"] = pd.NA
    df["Difference %"] = pd.NA
    df["Reason"] = ""

    return df[
        [
            "Category",
            "Value",
            "Current %",
            "TargetPercent",
            "Difference %",
            "Reason"
        ]
    ]

# --------------------------------------------------
# HTML
# --------------------------------------------------
def build_html(detail, retirement, exposure):
    total = retirement["Value"].sum()
    
    # Add subtotals to tables before formatting them into HTML strings
    retirement_with_totals = add_totals(retirement, "RetirementBucket")
    detail_with_totals = add_totals(detail, "Category")
    
    # Look through exposure fallback logic
    lt_label = exposure.columns[0] if len(exposure.columns) > 0 else ""
 
    exposure = format_exposure(exposure)

    exposure_with_totals = add_totals(
        exposure,
        "Category"
)

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Retirement Portfolio Dashboard</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin:40px; background:#f4f6f8; }}
            h1 {{ color:#222; }}
            .card {{ background:white; padding:20px; margin-bottom:25px; border-radius:10px; }}
            .table {{ border-collapse: collapse; width: 100%; table-layout: fixed; }}
            .table th, .table td {{ padding: 8px; border-bottom: 1px solid #ddd; text-align: right; }}
            .table th:first-child, .table td:first-child {{ text-align: left; }}
            .table th:nth-child(1), .table td:nth-child(1) {{ width: 25%; }}
            .table th:nth-child(2), .table td:nth-child(2) {{ width: 20%; }}
            .table th:nth-child(3), .table td:nth-child(3),
            .table th:nth-child(4), .table td:nth-child(4),
            .table th:nth-child(5), .table td:nth-child(5) {{ width: 12%; }}

            .table th:nth-child(6), .table td:nth-child(6) {{ 
                width: 30%; 
                text-align: left;
            }}
            .table th {{ background:#333; color:white; padding:10px; }}
            .table tr:last-child {{ font-weight: bold; background: #eee; }} /* Style for Total row */
            .summary {{ font-size:24px; }}
        </style>
    </head>
    <body>
        <h1>Retirement Portfolio Dashboard</h1>
        <div class="card">
            <h2>Portfolio Summary</h2>
            <div class="summary">
                Total Assets: <b>{money(total)}</b>
            </div>
        </div>
        <div class="card">
            <h2>Retirement Allocation</h2>
            {table(format_dataframe(retirement_with_totals))}
        </div>
        <div class="card">
            <h2>Detailed Allocation</h2>
            {table(format_dataframe(detail_with_totals))}
        </div>
        <div class="card">
            <h2>Economic Exposure</h2>
            {table(format_dataframe(exposure_with_totals))}
        </div>
    </body>
    </html>
    """
    return html

# --------------------------------------------------
# Main
# --------------------------------------------------
def main():
    (detail, retirement, lookthrough, alloc_target, retirement_target) = load_data()
    detail, retirement = apply_targets(detail, retirement, alloc_target, retirement_target)
    html = build_html(detail, retirement, lookthrough)
    HTML_FILE.write_text(html)
    print()
    print("Created:")
    print(HTML_FILE)

if __name__ == "__main__":
    main()
