#!/home/dev/py/.venv/bin/python
from pathlib import Path
import pandas as pd

BASE_DIR = Path("/home/dev/stock/asset_alloc")
OUTPUT_DIR = BASE_DIR / "output"
INPUT_DIR = BASE_DIR / "input"

EXPOSURE_FILE = OUTPUT_DIR / "economic_exposure.csv"
RETIREMENT_FILE = OUTPUT_DIR / "allocation_retirement.csv"
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

def format_dataframe(df):
    df = df.copy()
    for col in df.columns:
        if col in ["Value", "Value_1", "Value_2", "Value_3", "Target $", "Difference $"]:
            df[col] = df[col].apply(money)
        elif ("%" in col or "Percent" in col or "Pct" in col or "Delta" in col):
            df[col] = df[col].apply(percent)
    return df

def table(df):
    return f'<div class="table-wrap">{df.to_html(index=False, classes="table", border=0)}</div>'

# --------------------------------------------------
# Data Loading
# --------------------------------------------------
def load_data():
    exposure = pd.read_csv(EXPOSURE_FILE) if EXPOSURE_FILE.exists() else pd.DataFrame()
    retirement = pd.read_csv(RETIREMENT_FILE) if RETIREMENT_FILE.exists() else pd.DataFrame()
    return (exposure, retirement)


def format_exposure(exposure):
    df = exposure.copy()
    if "Value_3" in df.columns:
        keep_cols = [
            "AssetClass",
            "Value_1", "CurPct_1", "TargetPct_1", "Delta_1",
            "Value_2", "CurPct_2", "TargetPct_2", "Delta_2",
            "Value_3", "CurPct_3", "TargetPct_3", "Delta_3",
            "Reason",
        ]
        for col in keep_cols:
            if col not in df.columns:
                df[col] = pd.NA
        return df[keep_cols]

    if "AssetClass" in df.columns:
        df = df.rename(columns={"AssetClass": "Category"})
    elif "Category" not in df.columns:
        df["Category"] = "Unknown"

    if "Current %" not in df.columns:
        total = df["Value"].sum()
        df["Current %"] = (df["Value"] / total * 100)

    if "TargetPercent" not in df.columns:
        df["TargetPercent"] = pd.NA
    if "Difference %" not in df.columns:
        df["Difference %"] = pd.NA
    if "Reason" not in df.columns:
        df["Reason"] = ""

    return df[["Category", "Value", "Current %", "TargetPercent", "Difference %", "Reason"]]


def format_retirement(retirement):
    df = retirement.copy()
    if "Bucket" in df.columns and "AssetClass" not in df.columns:
        df = df.rename(columns={"Bucket": "AssetClass"})
    if "Cur_Pct_1" in df.columns and "CurPct_1" not in df.columns:
        df = df.rename(
            columns={
                "Cur_Pct_1": "CurPct_1",
                "Targ_Pct_1": "TargetPct_1",
                "Cur_Pct_2": "CurPct_2",
                "Targ_Pct_2": "TargetPct_2",
                "Cur_Pct_3": "CurPct_3",
                "Targ_Pct_3": "TargetPct_3",
            }
        )
    if "Value" in df.columns and "Value_3" not in df.columns:
        df["Value_3"] = pd.to_numeric(df["Value"], errors="coerce").fillna(0)
    if "Value_1" not in df.columns:
        df["Value_1"] = 0.0
    if "Value_2" not in df.columns:
        df["Value_2"] = 0.0

    expected = [
        "AssetClass",
        "Value_1", "CurPct_1", "TargetPct_1", "Delta_1",
        "Value_2", "CurPct_2", "TargetPct_2", "Delta_2",
        "Value_3", "CurPct_3", "TargetPct_3", "Delta_3",
        "Reason",
    ]
    for col in expected:
        if col not in df.columns:
            df[col] = pd.NA
    return df[expected]

# --------------------------------------------------
# HTML Generator
# --------------------------------------------------
def build_html(exposure, retirement):
    if "Category" in exposure.columns:
        exposure = exposure[exposure["Category"] != "Total"]
    elif "AssetClass" in exposure.columns:
        exposure = exposure[exposure["AssetClass"] != "Total"]

    exposure_html = table(format_dataframe(exposure))
    retirement_html = table(format_dataframe(retirement))

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Portfolio Dashboard</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin:40px; background:#f4f6f8; }}
            h1 {{ color:#222; }}
            .card {{ background:white; padding:20px; margin-bottom:25px; border-radius:10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }}
            .table-wrap {{ overflow-x: auto; }}
            .table {{ border-collapse: collapse; width: 100%; min-width: 1540px; table-layout: fixed; }}
            .table th, .table td {{ width: 7.14%; padding: 10px 8px; border-bottom: 1px solid #ddd; text-align: right; vertical-align: top; white-space: normal; overflow-wrap: anywhere; }}
            .table th:first-child, .table td:first-child {{ text-align: left; }}
            .table th:last-child, .table td:last-child {{ text-align: left; }}
            .table th {{ background:#333; color:white; padding:10px; }}
            
            .table tr:last-child, .grand-total-row {{ font-weight: bold; background: #cbd5e1 !important; }}
            .subtotal-row {{ font-weight: bold; background: #f1f5f9; border-top: 2px solid #333; }}
            .break-row td {{ border: none !important; }}
            .legend-title {{ margin: 0 0 8px 0; font-size: 18px; }}
            .legend-list {{ margin: 0; padding-left: 22px; }}
            .legend-list li {{ margin: 3px 0; }}
        </style>
    </head>
    <body>
        <h1>Portfolio Dashboard</h1>
        <div class="card">
            <h3 class="legend-title">Legend</h3>
            <ul class="legend-list">
                <li><b>_1 (Non-Taxable):</b> Roth_Tony ...497, Rollover_IRA_Tony ...871, Roth_Mary ...180</li>
                <li><b>_2 (Taxable):</b> Joint_Tony_Mary ...456, Indiv_Tony ...729, Indiv_Mary ...873</li>
                <li><b>_3 (Combined):</b> Total of _1 + _2</li>
            </ul>
        </div>
        <div class="card">
            <h2>Economic Exposure (_1 Non-Taxable / _2 Taxable / _3 Combined)</h2>
            {exposure_html}
        </div>
        <div class="card">
            <h2>Allocation Retirement (_1 Non-Taxable / _2 Taxable / _3 Combined)</h2>
            {retirement_html}
        </div>
    </body>
    </html>
    """
    return html

# --------------------------------------------------
# Main Orchestrator
# --------------------------------------------------
def main():
    (lookthrough, retirement) = load_data()
    lookthrough = format_exposure(lookthrough)
    retirement = format_retirement(retirement)
    
    html = build_html(lookthrough, retirement)
    HTML_FILE.write_text(html)
    print()
    print("Created:")
    print(HTML_FILE)

if __name__ == "__main__":
    main()
