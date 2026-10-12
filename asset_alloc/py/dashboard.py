#!/home/dev/py/.venv/bin/python
from pathlib import Path
import html
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
    if pd.isna(value):
        return ""
    numeric_value = pd.to_numeric(value, errors="coerce")
    if pd.isna(numeric_value):
        return value
    return f"${numeric_value:,.2f}"


def signed_money(value):
    if pd.isna(value):
        return ""
    numeric_value = pd.to_numeric(value, errors="coerce")
    if pd.isna(numeric_value):
        return value
    if numeric_value > 0:
        return f"+${numeric_value:,.2f}"
    if numeric_value < 0:
        return f"-${abs(numeric_value):,.2f}"
    return "$0.00"


def percent(value):
    if pd.isna(value):
        return ""
    numeric_value = pd.to_numeric(value, errors="coerce")
    if pd.isna(numeric_value):
        return value
    return f"{numeric_value:.1f}%"

def format_dataframe(df):
    df = df.copy()
    for col in df.columns:
        if col in ["Value", "Value_1", "Value_2", "Value_3", "Target $", "Difference $"]:
            df[col] = df[col].apply(money)
        elif col.startswith("Balance_"):
            df[col] = df[col].apply(signed_money)
        elif ("%" in col or "Percent" in col or "Pct" in col or "Delta" in col):
            df[col] = df[col].apply(percent)
    return df


def add_balance_columns(df, split_cash_basis=False, label_col="AssetClass", cash_label="Cash"):
    for suffix in ("1", "2", "3"):
        value_col = f"Value_{suffix}"
        target_col = f"TargetPct_{suffix}"
        balance_col = f"Balance_{suffix}"
        if value_col not in df.columns or target_col not in df.columns:
            continue

        values = pd.to_numeric(df[value_col], errors="coerce").fillna(0)
        targets = pd.to_numeric(df[target_col], errors="coerce").fillna(0)

        total_all = values.sum()
        basis = pd.Series(total_all, index=df.index, dtype="float64")

        if split_cash_basis and label_col in df.columns:
            labels = df[label_col].fillna("").astype(str).str.strip()
            cash_mask = labels.eq(cash_label)
            non_cash_total = values[~cash_mask].sum()
            basis = pd.Series(non_cash_total, index=df.index, dtype="float64")
            basis.loc[cash_mask] = total_all

        target_values = (targets / 100.0) * basis
        df[balance_col] = target_values - values

    return df


def add_totals_row(df, label_col, label):
    total_row = {}
    for col in df.columns:
        if col == label_col:
            total_row[col] = label
        elif col.startswith("Value_"):
            total_row[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).sum()
        elif col.startswith("CurPct_") or col.startswith("TargetPct_"):
            total_row[col] = 100.0
        elif col.startswith("Delta_"):
            total_row[col] = 0.0
        elif col.startswith("Balance_"):
            total_row[col] = 0.0
        elif col == "Reason":
            total_row[col] = ""
        else:
            total_row[col] = ""
    return pd.concat([df, pd.DataFrame([total_row])], ignore_index=True)


def add_core_total_row(df, label_col, label):
    core_df = df[df[label_col] != "Cash"].copy()
    core_row = {}
    for col in df.columns:
        if col == label_col:
            core_row[col] = label
        elif col.startswith("Value_") or col.startswith("CurPct_") or col.startswith("TargetPct_") or col.startswith("Delta_"):
            core_row[col] = pd.to_numeric(core_df[col], errors="coerce").fillna(0).sum()
        elif col.startswith("Balance_"):
            core_row[col] = 0.0
        elif col in {"Reason", "Symbols"}:
            core_row[col] = ""
        else:
            core_row[col] = ""
    return pd.DataFrame([core_row])


def swap_tax_group_columns(df):
    swapped = df.copy()
    column_pairs = [
        ("Value_1", "Value_2"),
        ("CurPct_1", "CurPct_2"),
        ("TargetPct_1", "TargetPct_2"),
        ("Delta_1", "Delta_2"),
        ("Balance_1", "Balance_2"),
    ]
    for left_col, right_col in column_pairs:
        if left_col in swapped.columns and right_col in swapped.columns:
            swapped[left_col], swapped[right_col] = swapped[right_col].copy(), swapped[left_col].copy()
    return swapped


def table(df):
    formatted_df = format_dataframe(df)
    delta_columns = {"Delta_1", "Delta_2", "Delta_3"}
    balance_columns = {"Balance_1", "Balance_2", "Balance_3"}

    grouped_layout = all(
        col in formatted_df.columns
        for col in [
            "AssetClass",
            "Value_1", "CurPct_1", "TargetPct_1", "Delta_1", "Balance_1",
            "Value_2", "CurPct_2", "TargetPct_2", "Delta_2", "Balance_2",
            "Value_3", "CurPct_3", "TargetPct_3", "Delta_3", "Balance_3",
            "Reason", "Symbols",
        ]
    )

    if grouped_layout:
        headers = (
            "<tr class=\"group-header\">"
            "<th rowspan=\"2\">AssetClass</th>"
            "<th colspan=\"5\">Taxable</th>"
            "<th colspan=\"5\">Non-Taxable (IRAs)</th>"
            "<th colspan=\"5\">Combined</th>"
            "<th rowspan=\"2\">Reason</th>"
            "<th rowspan=\"2\">Symbols</th>"
            "</tr>"
            "<tr class=\"sub-header\">"
            "<th>Value_1</th><th>CurPct_1</th><th>TargetPct_1</th><th>Delta_1</th><th>Balance_1</th>"
            "<th>Value_2</th><th>CurPct_2</th><th>TargetPct_2</th><th>Delta_2</th><th>Balance_2</th>"
            "<th>Value_3</th><th>CurPct_3</th><th>TargetPct_3</th><th>Delta_3</th><th>Balance_3</th>"
            "</tr>"
        )
    else:
        headers = f"<tr>{''.join(f'<th>{html.escape(str(col))}</th>' for col in formatted_df.columns)}</tr>"

    body_rows = []

    for idx in formatted_df.index:
        row_class = ""
        row_label = str(df.at[idx, df.columns[0]]) if pd.notna(df.at[idx, df.columns[0]]) else ""
        if row_label == "__BREAK__":
            row_class = "break-row"
        elif row_label in {"Total Portfolio", "Total"}:
            row_class = "grand-total-row"
        elif row_label.startswith("Core Total"):
            row_class = "subtotal-row"
        elif row_label == "Cash":
            row_class = "below-line-row"

        row_cells = []
        for col in formatted_df.columns:
            display_value = formatted_df.at[idx, col]
            if pd.isna(display_value):
                display_text = ""
            else:
                display_text = html.escape(str(display_value))
            if row_label == "__BREAK__":
                display_text = ""

            classes = []
            if col in delta_columns and row_class not in {"break-row", "grand-total-row"}:
                raw_value = pd.to_numeric(df.at[idx, col], errors="coerce")
                if pd.notna(raw_value):
                    if raw_value >= 2:
                        classes.append("delta-red")
                    elif raw_value <= -2:
                        classes.append("delta-green")
            if col in balance_columns and row_class not in {"break-row", "grand-total-row"}:
                raw_value = pd.to_numeric(df.at[idx, col], errors="coerce")
                if pd.notna(raw_value):
                    if raw_value > 0:
                        classes.append("delta-red")
                    elif raw_value < 0:
                        classes.append("delta-green")

            class_attr = f' class="{" ".join(classes)}"' if classes else ""
            row_cells.append(f"<td{class_attr}>{display_text}</td>")

        row_class_attr = f' class="{row_class}"' if row_class else ""
        body_rows.append(f"<tr{row_class_attr}>{''.join(row_cells)}</tr>")

    table_html = f"<table class=\"table\"><thead>{headers}</thead><tbody>{''.join(body_rows)}</tbody></table>"
    return f'<div class="table-wrap">{table_html}</div>'

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
        df = add_balance_columns(df, split_cash_basis=True, label_col="AssetClass", cash_label="Cash")
        keep_cols = [
            "AssetClass",
            "Value_1", "CurPct_1", "TargetPct_1", "Delta_1", "Balance_1",
            "Value_2", "CurPct_2", "TargetPct_2", "Delta_2", "Balance_2",
            "Value_3", "CurPct_3", "TargetPct_3", "Delta_3", "Balance_3",
            "Reason", "Symbols",
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

    if "Symbols" not in df.columns:
        df["Symbols"] = ""

    return df[["Category", "Value", "Current %", "TargetPercent", "Difference %", "Reason", "Symbols"]]


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
    df = add_balance_columns(df, split_cash_basis=False, label_col="AssetClass", cash_label="Cash")

    expected = [
        "AssetClass",
        "Value_1", "CurPct_1", "TargetPct_1", "Delta_1", "Balance_1",
        "Value_2", "CurPct_2", "TargetPct_2", "Delta_2", "Balance_2",
        "Value_3", "CurPct_3", "TargetPct_3", "Delta_3", "Balance_3",
        "Reason", "Symbols",
    ]
    for col in expected:
        if col not in df.columns:
            df[col] = pd.NA
    return df[expected]

# --------------------------------------------------
# HTML Generator
# --------------------------------------------------
import pandas as pd
def build_html(exposure, retirement):
    if "AssetClass" in exposure.columns:
        exposure = exposure[~exposure["AssetClass"].isin(["Total", "Total Portfolio"])].copy()

    non_cash_mask = exposure["AssetClass"] != "Cash"

    for suffix in ("1", "2", "3"):
        value_col = f"Value_{suffix}"
        cur_col = f"CurPct_{suffix}"
        target_col = f"TargetPct_{suffix}"
        delta_col = f"Delta_{suffix}"
        balance_col = f"Balance_{suffix}"

        if value_col not in exposure.columns:
            continue

        non_cash_values = pd.to_numeric(exposure.loc[non_cash_mask, value_col], errors="coerce").fillna(0)
        core_total = non_cash_values.sum()

        if cur_col in exposure.columns:
            if core_total > 0:
                exposure.loc[non_cash_mask, cur_col] = (non_cash_values / core_total) * 100.0
            else:
                exposure.loc[non_cash_mask, cur_col] = 0.0

        if delta_col in exposure.columns and cur_col in exposure.columns and target_col in exposure.columns:
            cur_vals = pd.to_numeric(exposure.loc[non_cash_mask, cur_col], errors="coerce").fillna(0)
            target_vals = pd.to_numeric(exposure.loc[non_cash_mask, target_col], errors="coerce").fillna(0)
            exposure.loc[non_cash_mask, delta_col] = cur_vals - target_vals

        if balance_col in exposure.columns and target_col in exposure.columns:
            values = pd.to_numeric(exposure.loc[non_cash_mask, value_col], errors="coerce").fillna(0)
            targets = pd.to_numeric(exposure.loc[non_cash_mask, target_col], errors="coerce").fillna(0)
            target_values = (targets / 100.0) * core_total if core_total > 0 else 0.0
            exposure.loc[non_cash_mask, balance_col] = target_values - values

    exposure_total_source = exposure.copy()
    cash_rows = exposure[exposure["AssetClass"] == "Cash"].copy()
    non_cash_rows = exposure[exposure["AssetClass"] != "Cash"].copy()
    
    display_rows = [non_cash_rows]
    
    # 1. Generate Core Total Row and override Target Pct columns with actual sums
    core_total_row = add_core_total_row(exposure, "AssetClass", "Core Total (Stocks + Bonds)")
    for suffix in ("1", "2", "3"):
        target_col = f"TargetPct_{suffix}"
        if target_col in exposure.columns:
            core_target_sum = pd.to_numeric(non_cash_rows[target_col], errors="coerce").fillna(0).sum()
            core_total_row[target_col] = core_target_sum
            
    display_rows.append(core_total_row)

    if not cash_rows.empty:
        separator = pd.DataFrame([{col: "" for col in exposure.columns}])
        separator.iloc[0, 0] = "__BREAK__"
        display_rows.extend([separator, cash_rows])

    exposure = pd.concat(display_rows, ignore_index=True)
    
    # 2. Generate Grand Total Row and override Target Pct columns with actual sums
    totals_df = add_totals_row(exposure_total_source, "AssetClass", "Total Portfolio")
    grand_total_row = totals_df.tail(1).copy()
    
    for suffix in ("1", "2", "3"):
        target_col = f"TargetPct_{suffix}"
        if target_col in exposure.columns:
            total_target_sum = pd.to_numeric(exposure_total_source[target_col], errors="coerce").fillna(0).sum()
            grand_total_row[target_col] = total_target_sum

    exposure = pd.concat([exposure, grand_total_row], ignore_index=True)

    if "AssetClass" in retirement.columns:
        retirement = retirement[~retirement["AssetClass"].isin(["Total", "Total Portfolio"])].copy()
    
    # 3. Handle retirement totals dynamically if it contains Target Pct columns
    retirement_totals = add_totals_row(retirement, "AssetClass", "Total Portfolio")
    retirement_grand_total = retirement_totals.tail(1).copy()
    
    for suffix in ("1", "2", "3"):
        target_col = f"TargetPct_{suffix}"
        if target_col in retirement.columns:
            ret_target_sum = pd.to_numeric(retirement[target_col], errors="coerce").fillna(0).sum()
            retirement_grand_total[target_col] = ret_target_sum
            
    retirement = pd.concat([retirement, retirement_grand_total], ignore_index=True)

    exposure = swap_tax_group_columns(exposure)
    retirement = swap_tax_group_columns(retirement)

    exposure_html = table(exposure)
    retirement_html = table(retirement)

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
        .table th:first-child, .table td:first-child {{ width: 5.5%; text-align: left; }}
        .table th:last-child, .table td:last-child {{ width: 5.2%; text-align: left; }}
        .table th:nth-child(17), .table td:nth-child(17) {{ width: 5.2%; text-align: left; }}
        .table th {{ background:#333; color:white; padding:10px; }}
        .table thead tr.group-header th {{ text-align: center; }}
        .table th:first-child, .table td:first-child {{ border-left: 4px solid #475569; border-right: 4px solid #475569; }}
        .table th:nth-child(6), .table td:nth-child(6) {{ border-right: 4px solid #475569; }}
        .table th:nth-child(11), .table td:nth-child(11) {{ border-right: 4px solid #475569; }}
        .table th:nth-child(16), .table td:nth-child(16) {{ border-right: 4px solid #475569; }}
        .table th:last-child, .table td:last-child {{ border-right: 4px solid #475569; }}
        .table td.delta-red {{ color: #b91c1c; font-weight: 700; }}
        .table td.delta-green {{ color: #15803d; font-weight: 700; }}
        .below-line-row td {{ border-top: 3px solid #111; }}
        .table tr:last-child, .grand-total-row {{ font-weight: bold; background: #cbd5e1 !important; }}
        .subtotal-row {{ font-weight: bold; background: #f1f5f9; border-top: 2px solid #333; }}
        .break-row td {{ border: none !important; height: 8px; padding: 0; background: #fff; }}
    </style>
    </head>
    <body>
    <h1>Portfolio Dashboard</h1>
    <div class="card">
        <h2>Economic Exposure</h2>
        {exposure_html}
    </div>
    <div class="card">
        <h2>Allocation Retirement</h2>
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
