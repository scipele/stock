#!/usr/bin/env python3

from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
INPUT_DIR = BASE_DIR / "input"
OUTPUT_DIR = BASE_DIR / "output"

OUTPUT_FILE = OUTPUT_DIR / "economic_exposure.csv"
ECONOMIC_TARGET_FILE = INPUT_DIR / "economic_target.csv"

INPUT_FILES = [
    OUTPUT_DIR / "schwab_assets.csv",
    OUTPUT_DIR / "manual_assets.csv",
]

def load_assets():
    frames = []
    for file in INPUT_FILES:
        if file.exists():
            print(f"Loading {file}")
            df = pd.read_csv(file)
            frames.append(df)
    if not frames:
        raise Exception("No asset files found")
    return pd.concat(frames, ignore_index=True)

def add_exposure(rows, asset_class, exposure, value):
    if value > 0:
        rows.append({"AssetClass": asset_class, "Exposure": exposure, "Value": value})


def create_exposure(df):
    rows = []
    total_portfolio_value = df["Value"].sum()

    for _, row in df.iterrows():
        value = row["Value"]
        category = row.get("RetirementBucket", row.get("Category", "Unclassified"))

        stock_pct = row.get("StockPct", 0)
        bond_pct = row.get("BondPct", 0)
        cash_pct = row.get("CashPct", 0)
        intl_pct = row.get("InternationalPct", 0)
        
        stock_pct = 0 if pd.isna(stock_pct) else stock_pct
        bond_pct = 0 if pd.isna(bond_pct) else bond_pct
        cash_pct = 0 if pd.isna(cash_pct) else cash_pct
        intl_pct = 0 if pd.isna(intl_pct) else intl_pct

        if stock_pct > 0:
            stock_value = value * stock_pct / 100
            intl_value = (stock_value * intl_pct / 100)
            us_value = stock_value - intl_value
            if us_value > 0:
                rows.append({"AssetClass": "Total Stocks", "Exposure": "US Stocks", "Value": us_value})
            if intl_value > 0:
                rows.append({"AssetClass": "Total Stocks", "Exposure": "International Stocks", "Value": intl_value})

        if bond_pct > 0:
            rows.append({"AssetClass": "Bonds", "Exposure": "Bonds", "Value": value * bond_pct / 100})
        if cash_pct > 0:
            rows.append({"AssetClass": "Cash", "Exposure": "Cash", "Value": value * cash_pct / 100})

    raw_df = pd.DataFrame(rows)
    us_stocks_val = raw_df[raw_df["Exposure"] == "US Stocks"]["Value"].sum()
    intl_stocks_val = raw_df[raw_df["Exposure"] == "International Stocks"]["Value"].sum()
    bonds_val = raw_df[raw_df["AssetClass"] == "Bonds"]["Value"].sum()
    cash_val = raw_df[raw_df["AssetClass"] == "Cash"]["Value"].sum()
    total_stocks_val = us_stocks_val + intl_stocks_val
    
    us_split = (us_stocks_val / total_stocks_val * 100) if total_stocks_val > 0 else 0
    intl_split = (intl_stocks_val / total_stocks_val * 100) if total_stocks_val > 0 else 0
    split_reason = f"Split: {us_split:.1f}% US / {intl_split:.1f}% Int'l"

    target_map = {}
    if ECONOMIC_TARGET_FILE.exists():
        target_df = pd.read_csv(ECONOMIC_TARGET_FILE)
        target_map = dict(zip(target_df["AssetClass"], target_df["TargetPercent"]))

    exposure_rows = [
        {"AssetClass": "Total Stocks", "Value": total_stocks_val, "Current %": (total_stocks_val / total_portfolio_value * 100), "TargetPercent": target_map.get("Total Stocks", 80.0), "Difference %": (total_stocks_val / total_portfolio_value * 100) - target_map.get("Total Stocks", 80.0), "Reason": split_reason},
        {"AssetClass": "Bonds", "Value": bonds_val, "Current %": (bonds_val / total_portfolio_value * 100), "TargetPercent": target_map.get("Bonds", 20.0), "Difference %": (bonds_val / total_portfolio_value * 100) - target_map.get("Bonds", 20.0), "Reason": "Core fixed-income sequence risk shelter"},
        {"AssetClass": "Cash", "Value": cash_val, "Current %": (cash_val / total_portfolio_value * 100), "TargetPercent": target_map.get("Cash", 7.0), "Difference %": (cash_val / total_portfolio_value * 100) - target_map.get("Cash", 7.0), "Reason": "Liquid structural early-retirement runway"}
    ]
    return pd.DataFrame(exposure_rows), total_portfolio_value


def main():
    print("\n" + "="*70 + "\n Economic Exposure (Core Portfolio Mix)\n" + "="*70 + "\n")
    assets = load_assets()
    exposure, portfolio_total = create_exposure(assets)
    exposure.to_csv(OUTPUT_FILE, index=False)

    core_df = exposure[exposure["AssetClass"].isin(["Total Stocks", "Bonds"])]
    cash_row = exposure[exposure["AssetClass"] == "Cash"]

    print(core_df.to_string(index=False, header=["Category", "Value", "Current %", "TargetPercent", "Difference %", "Reason"], formatters={"Value": "${:,.2f}".format, "Current %": "{:.1f}%".format, "TargetPercent": "{:.1f}%".format, "Difference %": lambda x: f"{x:+.1f}%" if abs(x) > 0.01 else "0.0%"}))
    
    current_equity = float(exposure.loc[exposure["AssetClass"] == "Total Stocks", "Current %"].values[0])
    current_bonds = float(exposure.loc[exposure["AssetClass"] == "Bonds", "Current %"].values[0])
    current_cash = float(exposure.loc[exposure["AssetClass"] == "Cash", "Current %"].values[0])

    print("-" * 70)
    print(f"CORE RISK ALLOCATION: {current_equity:.1f}% Equity / {current_bonds:.1f}% Bonds  --> [{current_equity:.0f}/{current_bonds:.0f} Split]")
    print("=" * 70 + "\n BELOW THE LINE: Short-Term Operational Cash Safety Buffer\n" + "=" * 70)
    print(cash_row.to_string(index=False, header=False, formatters={"Value": "${:,.2f}".format, "Current %": "{:.1f}%".format, "TargetPercent": "{:.1f}%".format, "Difference %": lambda x: f"{x:+.1f}%" if abs(x) > 0.01 else "0.0%"}))
    print("-" * 70)
    print(f"OVERALL ASSET RATIO:  {current_equity:.1f}% Equity / {(current_bonds + current_cash):.1f}% Fixed & Cash Buffer\n" + "=" * 70)

if __name__ == "__main__":
    main()

