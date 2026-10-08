#!/home/dev/py/.venv/bin/python
from pathlib import Path
import pandas as pd

BASE_DIR = Path("/home/dev/stock/asset_alloc")
OUTPUT_DIR = BASE_DIR / "output"
INPUT_DIR = BASE_DIR / "input"

DETAIL_FILE = OUTPUT_DIR / "allocation_detail.csv"
ALLOC_TARGET_FILE = INPUT_DIR / "alloc_target.csv"
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
    df = df.copy()
    numeric_cols = df.select_dtypes(include=['number']).columns
    total_row = {col: df[col].sum() for col in numeric_cols}
    
    for col in list(total_row.keys()):
        if col not in ["Value", "Current %", "TargetPercent"]:
            total_row[col] = pd.NA

    total_row[label_column] = "Total"
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
    return df.to_html(index=False, classes="table", border=0)

# --------------------------------------------------
# Data Loading
# --------------------------------------------------
def load_data():
    detail = pd.read_csv(DETAIL_FILE)
    exposure = pd.read_csv(EXPOSURE_FILE)
    alloc_target = pd.read_csv(ALLOC_TARGET_FILE)
    return (detail, exposure, alloc_target)
# --------------------------------------------------
# Apply Targets
# --------------------------------------------------
def apply_targets(detail, alloc_target):
    if "Category" in detail.columns and alloc_target is not None:
        if "TargetPercent" in detail.columns:
            detail = detail.drop(columns=["TargetPercent", "Reason", "Difference %"], errors="ignore")
        detail = detail.merge(alloc_target, on="Category", how="left")
        detail["TargetPercent"] = detail["TargetPercent"].fillna(0)
        detail["Reason"] = detail["Reason"].fillna("")
        detail["Difference %"] = detail["Current %"] - detail["TargetPercent"]

    return detail


def format_exposure(exposure):
    df = exposure.copy()
    if "AssetClass" in df.columns:
        df = df.rename(columns={"AssetClass": "Category"})
    elif "Category" not in df.columns:
        df["Category"] = "Unknown"

    total = df["Value"].sum()
    df["Current %"] = (df["Value"] / total * 100)

    if "TargetPercent" not in df.columns:
        df["TargetPercent"] = pd.NA
    if "Difference %" not in df.columns:
        df["Difference %"] = pd.NA
    if "Reason" not in df.columns:
        df["Reason"] = ""

    return df[["Category", "Value", "Current %", "TargetPercent", "Difference %", "Reason"]]

# --------------------------------------------------
# HTML Generator
# --------------------------------------------------
def build_html(detail, exposure):
    # Filter pre-existing totals before processing fresh metrics
    detail = detail[detail["Category"] != "Total"]
    exposure = exposure[exposure["Category"] != "Total"]
    total = detail["Value"].sum()

    detail_with_totals = add_totals(detail, "Category")

    # Isolate Core Risk Investments vs Cash Buffer
    core_exposure = exposure[exposure["Category"].isin(["Total Stocks", "Bonds"])].copy()
    cash_exposure = exposure[exposure["Category"] == "Cash"].copy()

    # CRITICAL MATH MOVE: Re-calculate percents based strictly on Core Subtotal
    core_val_subtotal = core_exposure["Value"].sum()
    
    # Recalculate Current % relative to Core Subtotal
    core_exposure["Current %"] = (core_exposure["Value"] / core_val_subtotal) * 100
    
    # Use the canonical CSV target values instead of re-scaling a 93% subtotal back to 100%. 
    target_map = {}
    if (Path(__file__).resolve().parent.parent / "input" / "economic_target.csv").exists():
        target_df = pd.read_csv(Path(__file__).resolve().parent.parent / "input" / "economic_target.csv")
        target_map = dict(zip(target_df["AssetClass"], target_df["TargetPercent"]))

    core_exposure["TargetPercent"] = core_exposure["Category"].map({
        "Total Stocks": target_map.get("Total Stocks", 80.0),
        "Bonds": target_map.get("Bonds", 20.0),
    })
    core_exposure["Difference %"] = core_exposure["Current %"] - core_exposure["TargetPercent"]

    # Core subtotal variables for the summary row
    core_current_sum = core_exposure["Current %"].sum()
    core_target_sum = core_exposure["TargetPercent"].sum()
    core_diff_sum = core_current_sum - core_target_sum

    # Format data blocks into structured HTML strings
    core_formatted = format_dataframe(core_exposure)
    cash_formatted = format_dataframe(cash_exposure)

    exposure_html = f"""
    <table class="table" border="0">
        <thead>
            <tr>
                <th>Category</th>
                <th>Value</th>
                <th>Current % (of Core)</th>
                <th>TargetPercent</th>
                <th>Difference %</th>
                <th style="text-align: left;">Reason</th>
            </tr>
        </thead>
        <tbody>
    """
    
    # 1. Inject Core Risk Rows (showing purely risk-adjusted percentages)
    for _, row in core_formatted.iterrows():
        exposure_html += f"<tr><td>{row['Category']}</td><td>{row['Value']}</td><td>{row['Current %']}</td><td>{row['TargetPercent']}</td><td>{row['Difference %']}</td><td style='text-align: left;'>{row['Reason']}</td></tr>"
    
    # 2. Inject Sub-Total Line Row (sums neatly to 100.0% of your risk assets)
    exposure_html += f"""
        <tr class="subtotal-row">
            <td>Core Subtotal</td>
            <td>{money(core_val_subtotal)}</td>
            <td>100.0%</td>
            <td>100.0%</td>
            <td>0.0%</td>
            <td style="text-align: left; font-style: italic;">Risk Assets Subtotal Split</td>
        </tr>
        <tr class="break-row"><td colspan="6" style="background: #cbd5e1; height: 4px; padding:0;"></td></tr>
    """

    # 3. Inject Cash Below The Line Row (tracked as absolute weight of grand total)
    for _, row in cash_formatted.iterrows():
        # Get absolute weight of cash relative to total portfolio
        cash_pct = (row['Value'] if isinstance(row['Value'], (int, float)) else float(str(row['Value']).replace('$','').replace(',',''))) / total * 100
        exposure_html += f"<tr><td>{row['Category']}</td><td>{money(cash_exposure['Value'].sum())}</td><td>{cash_pct:.1f}% (of Total)</td><td>7.0%</td><td>{cash_pct - 7.0:+.1f}%</td><td style='text-align: left;'>{row['Reason']}</td></tr>"

    # 4. Inject Grand Total Row
    exposure_html += f"""
        <tr class="grand-total-row">
            <td>Total Portfolio</td>
            <td>{money(total)}</td>
            <td>100.0%</td>
            <td>100.0%</td>
            <td>0.0%</td>
            <td></td>
        </tr>
        </tbody>
    </table>
    """

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Portfolio Dashboard</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin:40px; background:#f4f6f8; }}
            h1 {{ color:#222; }}
            .card {{ background:white; padding:20px; margin-bottom:25px; border-radius:10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }}
            .table {{ border-collapse: collapse; width: 100%; table-layout: fixed; }}
            .table th, .table td {{ padding: 10px 8px; border-bottom: 1px solid #ddd; text-align: right; }}
            .table th:first-child, .table td:first-child {{ text-align: left; }}
            .table th:nth-child(1), .table td:nth-child(1) {{ width: 22%; }}
            .table th:nth-child(2), .table td:nth-child(2) {{ width: 18%; }}
            .table th:nth-child(3), .table td:nth-child(3),
            .table th:nth-child(4), .table td:nth-child(4),
            .table th:nth-child(5), .table td:nth-child(5) {{ width: 12%; }}
            .table th:nth-child(6), .table td:nth-child(6) {{ width: 24%; text-align: left; }}
            .table th {{ background:#333; color:white; padding:10px; }}
            
            .table tr:last-child, .grand-total-row {{ font-weight: bold; background: #cbd5e1 !important; }}
            .subtotal-row {{ font-weight: bold; background: #f1f5f9; border-top: 2px solid #333; }}
            .break-row td {{ border: none !important; }}
            
            .summary {{ font-size:24px; }}
        </style>
    </head>
    <body>
        <h1>Portfolio Dashboard</h1>
        <div class="card">
            <h2>Portfolio Summary</h2>
            <div class="summary">Total Assets: <b>{money(total)}</b></div>
        </div>
        <div class="card">
            <h2>Economic Exposure (Core Portfolio Mix Split)</h2>
            {exposure_html}
        </div>
        <div class="card">
            <h2>Detailed Allocation</h2>
            {table(format_dataframe(detail_with_totals))}
        </div>
    </body>
    </html>
    """
    return html

# --------------------------------------------------
# Main Orchestrator
# --------------------------------------------------
def main():
    (detail, lookthrough, alloc_target) = load_data()
    detail = apply_targets(detail, alloc_target)
    lookthrough = format_exposure(lookthrough)
    
    html = build_html(detail, lookthrough)
    HTML_FILE.write_text(html)
    print()
    print("Created:")
    print(HTML_FILE)

if __name__ == "__main__":
    main()
