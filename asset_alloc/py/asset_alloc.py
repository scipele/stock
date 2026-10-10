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
RETIREMENT_REPORT_FILE = OUTPUT_DIR / "allocation_retirement.csv"
ECONOMIC_FILE = OUTPUT_DIR / "economic_exposure.csv"
ECONOMIC_TARGET_FILE = INPUT_DIR / "economic_target.csv"

NON_TAXABLE_ACCOUNTS = {
    "Roth_Tony ...497",
    "Rollover_IRA_Tony ...871",
    "Roth_Mary ...180",
}
TAXABLE_ACCOUNTS = {
    "Joint_Tony_Mary ...456",
    "Indiv_Tony ...729",
    "Indiv_Mary ...873",
}


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


def get_tax_group(account_value):
    if pd.isna(account_value):
        return 0
    account = str(account_value).strip()
    if account in NON_TAXABLE_ACCOUNTS:
        return 1
    if account in TAXABLE_ACCOUNTS:
        return 2
    return 0


def safe_pct(value, total):
    return (value / total * 100.0) if total else 0.0

# --------------------------------------------------
# Allocation report Processing
# --------------------------------------------------
def create_report():
    assets = load_csv(ASSET_FILE)
    assets["Value"] = pd.to_numeric(assets["Value"], errors="coerce").fillna(0)
    total = assets["Value"].sum()
    assets["Category"] = assets["Category"].map(normalize_bucket_name)
    assets["RetirementBucket"] = assets["RetirementBucket"].map(normalize_bucket_name)
    assets["TaxGroup"] = assets["Account"].map(get_tax_group) if "Account" in assets.columns else 0

    # 1. Backward-compatible detailed report
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

    retirement = create_retirement_report(assets, targets)
    economic = create_economic_report(assets)
    return detail, retirement, economic, total, assets


def create_retirement_report(assets, targets):
    category_bucket = (
        assets[["Category", "RetirementBucket", "Value"]]
        .dropna(subset=["Category", "RetirementBucket"])
        .assign(Value=lambda df: pd.to_numeric(df["Value"], errors="coerce").fillna(0))
        .groupby(["Category", "RetirementBucket"], as_index=False, sort=False)["Value"].sum()
        .sort_values(["Category", "Value"], ascending=[True, False])
        .drop_duplicates(subset=["Category"], keep="first")
    )
    category_to_bucket = dict(zip(category_bucket["Category"], category_bucket["RetirementBucket"]))

    target_df = targets.copy()
    target_df["Bucket"] = target_df["Category"].map(category_to_bucket).fillna(target_df["Category"])
    target_df["TargetPercent"] = pd.to_numeric(target_df["TargetPercent"], errors="coerce").fillna(0)
    target_df["Reason"] = target_df["Reason"].fillna("").astype(str).str.strip()

    target_bucket = target_df.groupby("Bucket", as_index=False, sort=False)["TargetPercent"].sum()
    reason_bucket = (
        target_df.groupby("Bucket")["Reason"]
        .apply(lambda s: "; ".join([v for v in s if v]))
        .to_dict()
    )

    grouped = assets.groupby(["RetirementBucket", "TaxGroup"], as_index=False)["Value"].sum()
    grouped = grouped.rename(columns={"RetirementBucket": "AssetClass"})

    bucket_totals = grouped.groupby("AssetClass", as_index=False)["Value"].sum().rename(columns={"Value": "Value_3"})
    group_totals = grouped.groupby("TaxGroup")["Value"].sum().to_dict()
    total_all = grouped["Value"].sum()

    rows = []
    ordered_buckets = target_df["Bucket"].dropna().drop_duplicates().tolist()
    observed_buckets = grouped["AssetClass"].dropna().drop_duplicates().tolist()
    for bucket in observed_buckets:
        if bucket not in ordered_buckets:
            ordered_buckets.append(bucket)

    target_map = dict(zip(target_bucket["Bucket"], target_bucket["TargetPercent"]))
    values_by_group = grouped.pivot_table(index="AssetClass", columns="TaxGroup", values="Value", aggfunc="sum", fill_value=0)

    for bucket in ordered_buckets:
        v1 = float(values_by_group.at[bucket, 1]) if bucket in values_by_group.index and 1 in values_by_group.columns else 0.0
        v2 = float(values_by_group.at[bucket, 2]) if bucket in values_by_group.index and 2 in values_by_group.columns else 0.0
        v3 = float(bucket_totals.loc[bucket_totals["AssetClass"] == bucket, "Value_3"].sum())
        t = float(target_map.get(bucket, 0.0))
        c1 = safe_pct(v1, group_totals.get(1, 0.0))
        c2 = safe_pct(v2, group_totals.get(2, 0.0))
        c3 = safe_pct(v3, total_all)
        d1 = c1 - t
        d2 = c2 - t
        d3 = c3 - t
        rows.append(
            {
                "AssetClass": bucket,
                "Value_1": v1,
                "CurPct_1": c1,
                "TargetPct_1": t,
                "Delta_1": d1,
                "Value_2": v2,
                "CurPct_2": c2,
                "TargetPct_2": t,
                "Delta_2": d2,
                "Value_3": v3,
                "CurPct_3": c3,
                "TargetPct_3": t,
                "Delta_3": d3,
                "Reason": reason_bucket.get(bucket, ""),
            }
        )

    result = pd.DataFrame(rows)
    result.to_csv(RETIREMENT_REPORT_FILE, index=False)
    return result


def create_economic_report(df):
    rows = []

    for _, row in df.iterrows():
        value = row["Value"]
        category = row["RetirementBucket"]
        tax_group = row.get("TaxGroup", 0)

        stock_pct = row.get("StockPct", 0)
        bond_pct = row.get("BondPct", 0)
        cash_pct = row.get("CashPct", 0)
        intl_pct = row.get("InternationalPct", 0)

        stock_pct = 0 if pd.isna(stock_pct) else stock_pct
        bond_pct = 0 if pd.isna(bond_pct) else bond_pct
        cash_pct = 0 if pd.isna(cash_pct) else cash_pct
        intl_pct = 0 if pd.isna(intl_pct) else intl_pct

        if category in ["Private Equity", "Company Equity"]:
            rows.append({"AssetClass": "Private Equity", "Value": value, "TaxGroup": tax_group})
            continue

        if stock_pct > 0:
            stock_value = value * stock_pct / 100
            intl_value = (stock_value * intl_pct / 100)

            if intl_value > 0:
                rows.append({"AssetClass": "International Stocks", "Value": intl_value, "TaxGroup": tax_group})

            us_value = stock_value - intl_value
            if us_value > 0:
                rows.append({"AssetClass": "US Stocks", "Value": us_value, "TaxGroup": tax_group})

        if bond_pct > 0:
            rows.append({"AssetClass": "Bonds", "Value": value * bond_pct / 100, "TaxGroup": tax_group})

        if cash_pct > 0:
            rows.append({"AssetClass": "Cash", "Value": value * cash_pct / 100, "TaxGroup": tax_group})

    raw_df = pd.DataFrame(rows)
    if raw_df.empty:
        result = pd.DataFrame(
            columns=[
                "AssetClass",
                "Value_1", "CurPct_1", "TargetPct_1", "Delta_1",
                "Value_2", "CurPct_2", "TargetPct_2", "Delta_2",
                "Value_3", "CurPct_3", "TargetPct_3", "Delta_3",
                "Reason",
            ]
        )
        result.to_csv(ECONOMIC_FILE, index=False)
        return result

    grouped = raw_df.groupby(["AssetClass", "TaxGroup"], as_index=False)["Value"].sum()
    totals_by_group = grouped.groupby("TaxGroup")["Value"].sum().to_dict()
    totals_by_group[3] = grouped["Value"].sum()
    combined_totals = grouped.groupby("AssetClass", as_index=False)["Value"].sum().rename(columns={"Value": "Value_3"})

    target_map = {}
    target_reason_map = {}
    if ECONOMIC_TARGET_FILE.exists():
        economic_targets = load_csv(ECONOMIC_TARGET_FILE)
        target_map = dict(zip(economic_targets["AssetClass"], economic_targets["TargetPercent"]))
        target_reason_map = dict(zip(economic_targets["AssetClass"], economic_targets["Reason"].fillna("")))

    wide_values = grouped.pivot_table(index="AssetClass", columns="TaxGroup", values="Value", aggfunc="sum", fill_value=0)

    def split_reason_for_group(group_id):
        if group_id == 3:
            us_val = float(grouped.loc[grouped["AssetClass"] == "US Stocks", "Value"].sum())
            intl_val = float(grouped.loc[grouped["AssetClass"] == "International Stocks", "Value"].sum())
        else:
            us_val = float(
                grouped.loc[(grouped["AssetClass"] == "US Stocks") & (grouped["TaxGroup"] == group_id), "Value"].sum()
            )
            intl_val = float(
                grouped.loc[(grouped["AssetClass"] == "International Stocks") & (grouped["TaxGroup"] == group_id), "Value"].sum()
            )
        total_stocks = us_val + intl_val
        us_pct = safe_pct(us_val, total_stocks)
        intl_pct = safe_pct(intl_val, total_stocks)
        return f"{us_pct:.1f}% US / {intl_pct:.1f}% Int'l"

    classes = ["Total Stocks", "Bonds", "Cash"]
    rows_out = []
    for asset_class in classes:
        if asset_class == "Total Stocks":
            v1 = float(
                grouped.loc[
                    (grouped["AssetClass"].isin(["US Stocks", "International Stocks"]))
                    & (grouped["TaxGroup"] == 1),
                    "Value",
                ].sum()
            )
            v2 = float(
                grouped.loc[
                    (grouped["AssetClass"].isin(["US Stocks", "International Stocks"]))
                    & (grouped["TaxGroup"] == 2),
                    "Value",
                ].sum()
            )
            v3 = float(
                grouped.loc[grouped["AssetClass"].isin(["US Stocks", "International Stocks"]), "Value"].sum()
            )
            reason = (
                f"Split _1: {split_reason_for_group(1)} | "
                f"Split _2: {split_reason_for_group(2)} | "
                f"Split _3: {split_reason_for_group(3)}"
            )
        else:
            v1 = float(wide_values.at[asset_class, 1]) if asset_class in wide_values.index and 1 in wide_values.columns else 0.0
            v2 = float(wide_values.at[asset_class, 2]) if asset_class in wide_values.index and 2 in wide_values.columns else 0.0
            v3 = float(combined_totals.loc[combined_totals["AssetClass"] == asset_class, "Value_3"].sum())
            reason = target_reason_map.get(asset_class, "")

        target_pct = float(target_map.get(asset_class, {"Total Stocks": 80.0, "Bonds": 20.0, "Cash": 7.0}.get(asset_class, 0.0)))
        cur1 = safe_pct(v1, totals_by_group.get(1, 0.0))
        cur2 = safe_pct(v2, totals_by_group.get(2, 0.0))
        cur3 = safe_pct(v3, totals_by_group.get(3, 0.0))
        rows_out.append(
            {
                "AssetClass": asset_class,
                "Value_1": v1,
                "CurPct_1": cur1,
                "TargetPct_1": target_pct,
                "Delta_1": cur1 - target_pct,
                "Value_2": v2,
                "CurPct_2": cur2,
                "TargetPct_2": target_pct,
                "Delta_2": cur2 - target_pct,
                "Value_3": v3,
                "CurPct_3": cur3,
                "TargetPct_3": target_pct,
                "Delta_3": cur3 - target_pct,
                "Reason": reason,
            }
        )

    result = pd.DataFrame(rows_out)
    result.to_csv(ECONOMIC_FILE, index=False)
    return result


# --------------------------------------------------
# Main Execution Entry Point
# --------------------------------------------------
if __name__ == "__main__":

    detail, retirement, economic, total, assets = create_report()
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

    core_val_subtotal = core_df["Value_3"].sum()

    target_map = {}
    if ECONOMIC_TARGET_FILE.exists():
        economic_targets = load_csv(ECONOMIC_TARGET_FILE)
        target_map = dict(zip(economic_targets["AssetClass"], economic_targets["TargetPercent"]))

    # Keep the displayed core split aligned to the canonical target file values instead of re-scaling them.
    core_df["Current %"] = (core_df["Value_3"] / core_val_subtotal) * 100
    core_df["TargetPercent"] = core_df["AssetClass"].map({"Total Stocks": target_map.get("Total Stocks", 80.0), "Bonds": target_map.get("Bonds", 13.0)})
    core_df["Difference %"] = core_df["Current %"] - core_df["TargetPercent"]
    core_print = core_df[["AssetClass", "Value_3", "Current %", "TargetPercent", "Difference %", "Reason"]]

    current_equity_pct = float(core_df.loc[core_df["AssetClass"] == "Total Stocks", "Current %"].iloc[0]) if not core_df[core_df["AssetClass"] == "Total Stocks"].empty else 0.0
    current_bonds_pct = float(core_df.loc[core_df["AssetClass"] == "Bonds", "Current %"].iloc[0]) if not core_df[core_df["AssetClass"] == "Bonds"].empty else 0.0

    print(
        core_print.to_string(
            index=False,
            header=["Category", "Value", "Current % (of Core)", "TargetPercent", "Difference %", "Reason"],
            formatters={
                "Value_3": "${:,.2f}".format, "Current %": "{:.1f}%".format,
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
    cash_val = cash_row["Value_3"].sum()
    cash_total_pct = (cash_val / total) * 100
    
    print(f"Cash Equivalent ${cash_val:,.2f}   {cash_total_pct:.1f}% (of Total)  7.0%      {cash_total_pct - 7.0:+.1f}%   Liquid structural runway")
    print("-" * 70)
    print(f"Total Portfolio${total:,.2f}   100.0%     100.0%     0.0%")
    print("-" * 70)
    print()

    print("Created:")
    print(DETAIL_REPORT_FILE)
    print(RETIREMENT_REPORT_FILE)
    print(ECONOMIC_FILE)
