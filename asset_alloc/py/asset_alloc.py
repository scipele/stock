#!/usr/bin/env python3

from pathlib import Path
import pandas as pd

# --------------------------------------------------
# Paths
# --------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent

INPUT_DIR = BASE_DIR / "input"
OUTPUT_DIR = BASE_DIR / "output"
ASSET_FILE = OUTPUT_DIR / "all_assets.csv"
TARGET_FILE = INPUT_DIR / "alloc_target.csv"

REPORT_FILE = OUTPUT_DIR / "allocation_report.csv"
DETAIL_REPORT_FILE = OUTPUT_DIR / "allocation_detail.csv"
ECONOMIC_FILE = OUTPUT_DIR / "economic_exposure.csv"
ECONOMIC_TARGET_FILE = INPUT_DIR / "economic_target.csv"


# --------------------------------------------------
# Load CSV
# --------------------------------------------------
def load_csv(filename):
    if not filename.exists():
        raise FileNotFoundError(filename)
    return pd.read_csv(filename)


def normalize_bucket_name(value):
    if pd.isna(value):
        return value
    label = str(value).strip()
    if label in {"Bonds", "Fixed Income"}:
        return "Bonds / Fixed Income"
    if label == "Balanced":
        return "Balanced (includes bonds)"
    if label == "Balanced Funds":
        return "Balanced Funds (includes bonds)"
    if label in {"Short Treasury", "Cash"}:
        return "Cash Equiv (SWVXX, Short Treasury SGOV)"
    return label


def print_unclassified_positions_warning(assets):
    category_labels = assets["Category"].fillna("").astype(str).str.strip()
    unclassified_mask = category_labels.isin(["", "Unclassified"])

    if not unclassified_mask.any():
        return pd.DataFrame()

    warning_df = assets.loc[unclassified_mask].copy()
    warning_df["Symbol"] = warning_df["Symbol"].fillna("").astype(str).str.strip().replace("", "-")
    warning_df["Description"] = warning_df["Description"].fillna("").astype(str).str.strip().replace("", "-")
    warning_df["Category"] = warning_df["Category"].fillna("Unclassified")
    warning_df["Value"] = pd.to_numeric(warning_df["Value"], errors="coerce").fillna(0)
    warning_df = warning_df.sort_values(["Value", "Symbol"], ascending=[False, True])

    return warning_df


def print_warning_section(assets):
    warning_df = print_unclassified_positions_warning(assets)

    columns = ["Symbol", "Description", "Category", "Value"]
    if "Account" in warning_df.columns:
        columns.insert(0, "Account")

    print()
    print("=" * 70)
    print(" WARNINGS:")
    print("=" * 70)
    print()

    if warning_df.empty:
        print("None")
        return

    print("Unclassified positions detected:")
    print(
        warning_df[columns].to_string(
            index=False,
            formatters={"Value": "${:,.2f}".format},
        )
    )

# --------------------------------------------------
# Allocation report Processing
# --------------------------------------------------
def create_report():
    assets = load_csv(ASSET_FILE)
    total = assets["Value"].sum()
    assets["Category"] = assets["Category"].map(normalize_bucket_name)
    assets["RetirementBucket"] = assets["RetirementBucket"].map(normalize_bucket_name)

    # 1. Detailed report
    detail = assets.groupby("Category", as_index=False)["Value"].sum()
    targets = load_csv(TARGET_FILE)
    targets["Category"] = targets["Category"].map(normalize_bucket_name)
    target_categories_in_order = targets["Category"].dropna().drop_duplicates().tolist()
    category_order_map = {category: idx for idx, category in enumerate(target_categories_in_order)}
    detail = detail.merge(targets[["Category", "TargetPercent", "Reason"]], on="Category", how="outer")
    detail["Value"] = pd.to_numeric(detail["Value"], errors="coerce").fillna(0)
    detail["TargetPercent"] = pd.to_numeric(detail["TargetPercent"], errors="coerce").fillna(0)
    detail["Reason"] = detail["Reason"].fillna("")
    detail["Current %"] = (detail["Value"] / total * 100) if total else 0
    detail["Difference %"] = detail["Current %"] - detail["TargetPercent"]
    detail["__category_order"] = detail["Category"].map(category_order_map)
    detail = detail.sort_values(["__category_order", "Category"], ascending=[True, True], na_position="last")
    detail = detail.drop(columns=["__category_order"])

    detail = detail[["Category", "Value", "Current %", "TargetPercent", "Difference %", "Reason"]]
    detail.to_csv(DETAIL_REPORT_FILE, index=False)

    economic = create_economic_report(assets)
    return detail, economic, total, assets


def create_economic_report(df):
    rows = []

    for _, row in df.iterrows():
        value = row["Value"]
        category = row["RetirementBucket"]

        stock_pct = row.get("StockPct", 0)
        bond_pct = row.get("BondPct", 0)
        cash_pct = row.get("CashPct", 0)
        intl_pct = row.get("InternationalPct", 0)

        stock_pct = 0 if pd.isna(stock_pct) else stock_pct
        bond_pct = 0 if pd.isna(bond_pct) else bond_pct
        cash_pct = 0 if pd.isna(cash_pct) else cash_pct
        intl_pct = 0 if pd.isna(intl_pct) else intl_pct

        if category in ["Private Equity", "Company Equity"]:
            rows.append({"AssetClass": "Private Equity", "Value": value})
            continue

        if stock_pct > 0:
            stock_value = value * stock_pct / 100
            intl_value = (stock_value * intl_pct / 100)

            if intl_value > 0:
                rows.append({"AssetClass": "International Stocks", "Value": intl_value})

            us_value = stock_value - intl_value
            if us_value > 0:
                rows.append({"AssetClass": "US Stocks", "Value": us_value})

        if bond_pct > 0:
            rows.append({"AssetClass": "Bonds", "Value": value * bond_pct / 100})

        if cash_pct > 0:
            rows.append({"AssetClass": "Cash", "Value": value * cash_pct / 100})

    if not rows:
        return pd.DataFrame()

    raw_df = pd.DataFrame(rows)
    portfolio_total = raw_df["Value"].sum()

    us_stocks_val = raw_df[raw_df["AssetClass"] == "US Stocks"]["Value"].sum()
    intl_stocks_val = raw_df[raw_df["AssetClass"] == "International Stocks"]["Value"].sum()
    bonds_val = raw_df[raw_df["AssetClass"] == "Bonds"]["Value"].sum()
    cash_val = raw_df[raw_df["AssetClass"] == "Cash"]["Value"].sum()
    total_stocks_val = us_stocks_val + intl_stocks_val

    us_split = (us_stocks_val / total_stocks_val * 100) if total_stocks_val > 0 else 0
    intl_split = (intl_stocks_val / total_stocks_val * 100) if total_stocks_val > 0 else 0
    split_reason = f"Split: {us_split:.1f}% US / {intl_split:.1f}% Int'l"

    target_map = {}
    if ECONOMIC_TARGET_FILE.exists():
        economic_targets = load_csv(ECONOMIC_TARGET_FILE)
        target_map = dict(zip(economic_targets["AssetClass"], economic_targets["TargetPercent"]))
        target_reason_map = dict(zip(economic_targets["AssetClass"], economic_targets["Reason"].fillna("")))
    else:
        target_reason_map = {}

    exposure_rows = [
        {
            "AssetClass": "Total Stocks", "Value": total_stocks_val,
            "Current %": (total_stocks_val / portfolio_total * 100),
            "TargetPercent": target_map.get("Total Stocks", 80.0),
            "Difference %": (total_stocks_val / portfolio_total * 100) - target_map.get("Total Stocks", 80.0),
            "Reason": split_reason
        },
        {
            "AssetClass": "Bonds", "Value": bonds_val,
            "Current %": (bonds_val / portfolio_total * 100),
            "TargetPercent": target_map.get("Bonds", 20.0),
            "Difference %": (bonds_val / portfolio_total * 100) - target_map.get("Bonds", 20.0),
            "Reason": target_reason_map.get("Bonds", "Core fixed-income sequence risk shelter")
        },
        {
            "AssetClass": "Cash", "Value": cash_val,
            "Current %": (cash_val / portfolio_total * 100),
            "TargetPercent": target_map.get("Cash", 7.0),
            "Difference %": (cash_val / portfolio_total * 100) - target_map.get("Cash", 7.0),
            "Reason": target_reason_map.get("Cash", "Liquid structural early-retirement runway")
        }
    ]

    result = pd.DataFrame(exposure_rows)
    result.to_csv(ECONOMIC_FILE, index=False)
    return result


# --------------------------------------------------
# Main Execution Entry Point
# --------------------------------------------------
if __name__ == "__main__":

    detail, economic, total, assets = create_report()
    print_warning_section(assets)

    print()
    print("=" * 70)
    print(" Detailed Allocation")
    print("=" * 70)
    print()

    print(
        detail.to_string(
            index=False,
            formatters={
                "Value": "${:,.2f}".format,
                "Current %": "{:.1f}%".format,
                "TargetPercent": "{:.1f}%".format,
                "Difference %": lambda x: f"{x:+.1f}%" if pd.notna(x) else "",
            },
        )
    )

    print()
    print("=" * 70)
    print(" Bond Holdings Check")
    print("=" * 70)
    print()

    bond_check = assets.copy()
    bond_check["BondPct"] = pd.to_numeric(bond_check["BondPct"], errors="coerce").fillna(0)
    bond_check = bond_check[bond_check["BondPct"] > 0].copy()
    bond_check["Bond Exposure"] = bond_check["Value"] * bond_check["BondPct"] / 100.0
    bond_check["Symbol"] = bond_check["Symbol"].fillna("").replace("", "-")

    if bond_check.empty:
        print("No holdings with BondPct > 0 found.")
    else:
        bond_check = bond_check.sort_values("Bond Exposure", ascending=False)
        print(
            bond_check[
                ["Symbol", "Description", "Category", "Value", "BondPct", "Bond Exposure"]
            ].to_string(
                index=False,
                formatters={
                    "Value": "${:,.2f}".format,
                    "BondPct": "{:.1f}%".format,
                    "Bond Exposure": "${:,.2f}".format,
                },
            )
        )
        print("-" * 70)
        print(f"Total Bond Exposure Check: ${bond_check['Bond Exposure'].sum():,.2f}")

    # --------------------------------------------------
    # Custom Carved Out 80/20 Plan Matrix Visualization
    # --------------------------------------------------
    print()
    print("=" * 70)
    print(" Economic Exposure (Core Portfolio Mix)")
    print("=" * 70)
    print()

    core_df = economic[economic["AssetClass"].isin(["Total Stocks", "Bonds"])].copy()
    cash_row = economic[economic["AssetClass"] == "Cash"].copy()

    core_val_subtotal = core_df["Value"].sum()

    target_map = {}
    if ECONOMIC_TARGET_FILE.exists():
        economic_targets = load_csv(ECONOMIC_TARGET_FILE)
        target_map = dict(zip(economic_targets["AssetClass"], economic_targets["TargetPercent"]))

    # Keep the displayed core split aligned to the canonical target file values instead of re-scaling them.
    core_df["Current %"] = (core_df["Value"] / core_val_subtotal) * 100
    core_df["TargetPercent"] = core_df["AssetClass"].map({"Total Stocks": target_map.get("Total Stocks", 80.0), "Bonds": target_map.get("Bonds", 13.0)})
    core_df["Difference %"] = core_df["Current %"] - core_df["TargetPercent"]

    current_equity_pct = float(core_df.loc[core_df["AssetClass"] == "Total Stocks", "Current %"].iloc[0]) if not core_df[core_df["AssetClass"] == "Total Stocks"].empty else 0.0
    current_bonds_pct = float(core_df.loc[core_df["AssetClass"] == "Bonds", "Current %"].iloc[0]) if not core_df[core_df["AssetClass"] == "Bonds"].empty else 0.0

    print(
        core_df.to_string(
            index=False,
            header=["Category", "Value", "Current % (of Core)", "TargetPercent", "Difference %", "Reason"],
            formatters={
                "Value": "${:,.2f}".format, "Current %": "{:.1f}%".format,
                "TargetPercent": "{:.1f}%".format,
                "Difference %": lambda x: f"{x:+.1f}%" if abs(x) > 0.01 else "0.0%"
            }
        )
    )

    print("-" * 70)
    print(f"Core Subtotal  ${core_val_subtotal:,.2f}   100.0%     100.0%     0.0%")
    print("-" * 70)
    print(f"CORE RISK STRATEGY: {current_equity_pct:.1f}% Equity / {current_bonds_pct:.1f}% Bonds  --> [{current_equity_pct:.0f}/{current_bonds_pct:.0f} Allocation]")
    
    print("=" * 70)
    print(" BELOW THE LINE: Short-Term Operational Cash Safety Buffer")
    print("=" * 70)

    # Cash percentage relative to overall portfolio total
    cash_val = cash_row["Value"].sum()
    cash_total_pct = (cash_val / total) * 100
    
    print(f"Cash Equivalent ${cash_val:,.2f}   {cash_total_pct:.1f}% (of Total)  7.0%      {cash_total_pct - 7.0:+.1f}%   Liquid structural runway")
    print("-" * 70)
    print(f"Total Portfolio${total:,.2f}   100.0%     100.0%     0.0%")
    print("-" * 70)
    print()

    print("Created:")
    print(DETAIL_REPORT_FILE)
    print(ECONOMIC_FILE)
