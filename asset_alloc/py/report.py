#!/usr/bin/env python3

from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
INPUT_DIR = BASE_DIR / "input"
OUTPUT_DIR = BASE_DIR / "output"

ECONOMIC_FILE = OUTPUT_DIR / "economic_exposure.csv"
RETIREMENT_REPORT_FILE = OUTPUT_DIR / "allocation_retirement.csv"
DETAIL_REPORT_FILE = OUTPUT_DIR / "allocation_detail.csv"

def format_economic_exposure(economic_df):
    # Consolidate raw categories safely into your clean 80/20 structural metrics
    us_val = economic_df[economic_df["AssetClass"] == "US Stocks"]["Value"].sum()
    intl_val = economic_df[economic_df["AssetClass"] == "International Stocks"]["Value"].sum()
    bonds_val = economic_df[economic_df["AssetClass"] == "Bonds"]["Value"].sum()
    cash_val = economic_df[economic_df["AssetClass"] == "Cash"]["Value"].sum()

    total_stocks = us_val + intl_val
    portfolio_total = total_stocks + bonds_val + cash_val

    us_pct = (us_val / total_stocks * 100) if total_stocks > 0 else 0
    intl_pct = (intl_val / total_stocks * 100) if total_stocks > 0 else 0
    split_reason = f"Split: {us_pct:.1f}% US / {intl_pct:.1f}% Int'l"

    exposure_rows = [
        {
            "Category": "Total Stocks", "Value": total_stocks,
            "Current %": (total_stocks / portfolio_total * 100),
            "TargetPercent": 80.0, "Difference %": (total_stocks / portfolio_total * 100) - 80.0,
            "Reason": split_reason
        },
        {
            "Category": "Bonds", "Value": bonds_val,
            "Current %": (bonds_val / portfolio_total * 100),
            "TargetPercent": 13.0, "Difference %": (bonds_val / portfolio_total * 100) - 13.0,
            "Reason": "Core fixed-income sequence risk shelter"
        },
        {
            "Category": "Cash", "Value": cash_val,
            "Current %": (cash_val / portfolio_total * 100),
            "TargetPercent": 7.0, "Difference %": (cash_val / portfolio_total * 100) - 7.0,
            "Reason": "Liquid structural early-retirement runway"
        }
    ]
    return pd.DataFrame(exposure_rows), portfolio_total
def print_final_terminal_report(economic_df):
    print("\n" + "="*70)
    print(" Economic Exposure (Core Portfolio Mix)")
    print("="*70 + "\n")

    print_df, portfolio_total = format_economic_exposure(economic_df)
    
    core_df = print_df[print_df["Category"].isin(["Total Stocks", "Bonds"])]
    cash_row = print_df[print_df["Category"] == "Cash"]

    # Print clean core portfolio metrics 
    print(
        core_df.to_string(
            index=False,
            header=["Category", "Value", "Current %", "TargetPercent", "Difference %", "Reason"],
            formatters={
                "Value": "${:,.2f}".format, "Current %": "{:.1f}%".format,
                "TargetPercent": "{:.1f}%".format,
                "Difference %": lambda x: f"{x:+.1f}%" if abs(x) > 0.01 else "0.0%"
            }
        )
    )

    current_equity = float(print_df.loc[print_df["Category"] == "Total Stocks", "Current %"].values)
    current_bonds = float(print_df.loc[print_df["Category"] == "Bonds", "Current %"].values)
    current_cash = float(print_df.loc[print_df["Category"] == "Cash", "Current %"].values)

    print("-" * 70)
    print(f"CORE RISK ALLOCATION: {current_equity:.1f}% Equity / {current_bonds:.1f}% Bonds  --> [{current_equity:.0f}/{current_bonds:.0f} Split]")
    print("=" * 70)
    print(" BELOW THE LINE: Short-Term Operational Cash Safety Buffer")
    print("=" * 70)

    # Print safe buffer cash metrics cleanly below the cut lines
    print(
        cash_row.to_string(
            index=False, header=False,
            formatters={
                "Value": "${:,.2f}".format, "Current %": "{:.1f}%".format,
                "TargetPercent": "{:.1f}%".format,
                "Difference %": lambda x: f"{x:+.1f}%" if abs(x) > 0.01 else "0.0%"
            }
        )
    )
    print("-" * 70)
    print(f"OVERALL ASSET RATIO:  {current_equity:.1f}% Equity / {(current_bonds + current_cash):.1f}% Fixed & Cash Buffer")
    print("=" * 70 + "\n")
