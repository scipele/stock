#!/usr/bin/env python3

from pathlib import Path
from matplotlib import category
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


# --------------------------------------------------
# Load CSV
# --------------------------------------------------

def load_csv(filename):

    if not filename.exists():
        raise FileNotFoundError(filename)

    return pd.read_csv(filename)


# --------------------------------------------------
# Allocation report
# --------------------------------------------------

def create_report():

    assets = load_csv(
        ASSET_FILE
    )

    total = assets["Value"].sum()


    # --------------------------------------------------
    # Detailed report
    # --------------------------------------------------

    detail = (
        assets
        .groupby(
            "Category",
            as_index=False
        )["Value"]
        .sum()
    )


    detail["Current %"] = (
        detail["Value"]
        / total
        * 100
    )

        #
    # Add target allocation
    #

    targets = load_csv(
        TARGET_FILE
    )

    detail = detail.merge(
        targets,
        on="Category",
        how="left"
    )

    detail["TargetPercent"] = (
        detail["TargetPercent"]
        .fillna(0)
    )

    detail["Reason"] = (
        detail["Reason"]
        .fillna("")
    )

    detail["Difference %"] = (
        detail["Current %"]
        -
        detail["TargetPercent"]
    )

    detail = detail.sort_values(
        "Value",
        ascending=False
    )


    detail = detail[
        [
            "Category",
            "Value",
            "Current %",
            "TargetPercent",
            "Difference %",
            "Reason"
        ]
    ]


    detail.to_csv(
        DETAIL_REPORT_FILE,
        index=False
    )


    #
    # Organize report columns
    #

    detail = detail[
        [
            "Category",
            "Value",
            "Current %",
            "TargetPercent",
            "Difference %",
            "Reason"
        ]
    ]


    detail.to_csv(
        DETAIL_REPORT_FILE,
        index=False
    )


    # --------------------------------------------------
    # Retirement bucket report
    # --------------------------------------------------

    retirement = (
        assets
        .groupby(
            "RetirementBucket",
            as_index=False
        )["Value"]
        .sum()
    )


    retirement["Current %"] = (
        retirement["Value"]
        / total
        * 100
    )

    retirement = retirement.sort_values(
        "Value",
        ascending=False
    )


    retirement.to_csv(
        RETIREMENT_REPORT_FILE,
        index=False
    )

    # --------------------------------------------------
    # Look-through exposure report
    # --------------------------------------------------

    economic = create_economic_report(
        assets
    )

    return detail, retirement, economic, total


# --------------------------------------------------
# Display
# --------------------------------------------------

def print_report(report, total):

    print()
    print("=" * 70)
    print(" Portfolio Allocation Report")
    print("=" * 70)

    print()

    print(
        f"Portfolio Total: ${total:,.2f}"
    )

    print()

    print(

        report[
            report["TargetPercent"] > 0
        ][
            [
                "Category",
                "Value",
                "Current %",
                "TargetPercent",
                "Reason",
                "Difference %"
            ]
        ]
        .to_string(
            index=False,
            formatters={
                "Value": "${:,.0f}".format,
                "Current %": "{:.1f}%".format,
                "TargetPercent": "{:.1f}%".format,
                "Difference %": "{:+.1f}%".format,
            }
        )
    )

    print()

    print("Created:")
    print(REPORT_FILE)


def create_economic_report(df):
    rows = []

    for _, row in df.iterrows():

        value = row["Value"]


        category = row["RetirementBucket"]

        stock_pct = row.get("StockPct",0)
        bond_pct = row.get("BondPct",0)
        cash_pct = row.get("CashPct",0)
        intl_pct = row.get("InternationalPct",0)


        #
        # Private Equity / Individual assets
        #

        if category in ["Private Equity", "Company Equity"]:

            rows.append(
                {
                    "AssetClass": "Private Equity",
                    "Exposure": "Private Equity",
                    "Value": value
                }
            )

            continue


        #
        # Stock exposure
        #

         #
        # Stock exposure
        #

        if stock_pct > 0:

            stock_value = value * stock_pct / 100
            intl_value = (stock_value * intl_pct / 100)

            if intl_value > 0:
                rows.append(
                    {
                        "AssetClass": "International Stocks",
                        "Exposure": "International",
                        "Value": intl_value
                    }
                )

            us_value = (
                stock_value -
                intl_value
            )

            if us_value > 0:
                rows.append(
                    {
                        "AssetClass": "US Stocks",
                        "Exposure": "Domestic",
                        "Value": us_value
                    }
                )

        #
        # Bonds
        #

        if bond_pct > 0:

            rows.append(
                {
                    "AssetClass": "Bonds",
                    "Exposure": "Bonds",
                    "Value":
                        value * bond_pct / 100
                }
            )

        #
        # Cash
        #

        if cash_pct > 0:
            value = value * cash_pct / 100

            rows.append(
                {
                    "AssetClass": "Cash",
                    "Exposure": "Cash",
                    "Value": value
                }
            )

    result = (
        pd.DataFrame(rows)
        .groupby(
            [
                "AssetClass",
                "Exposure"
            ],
            as_index=False
        )
        ["Value"]
        .sum()
        .sort_values(
            "Value",
            ascending=False
        )
    )


    result.to_csv(
        ECONOMIC_FILE,
        index=False
    )


    return result


# --------------------------------------------------
# Main
# --------------------------------------------------

if __name__ == "__main__":

    detail, retirement, economic, total = create_report()
    
    print()
    print("=" * 70)
    print(" Retirement Allocation")
    print("=" * 70)

    print()
    print(
        f"Portfolio Total: ${total:,.2f}"
    )

    print()

    print(
        retirement.to_string(
            index=False,
            formatters={
                "Value": "${:,.0f}".format,
                "Current %": "{:.1f}%".format
            }
        )
    )

    print()
    print("Created:")
    print(DETAIL_REPORT_FILE)
    print(RETIREMENT_REPORT_FILE)
    print(ECONOMIC_FILE)