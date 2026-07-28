#!/usr/bin/env python3

from pathlib import Path
import pandas as pd
import re


# --------------------------------------------------
# Paths
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent
INPUT_DIR = BASE_DIR / "input"
JH_FILE = INPUT_DIR / "john_hancock.txt"
ASSET_MAP_FILE = INPUT_DIR / "asset_map.csv"
JH_OUTPUT = BASE_DIR / "output" / "jh_assets.csv"


# --------------------------------------------------
# Money conversion
# --------------------------------------------------

def clean_money(value):

    value = (
        value.replace("$", "")
             .replace(",", "")
             .strip()
    )

    if value in ("-", ""):
        return 0.0

    return float(value)



# --------------------------------------------------
# Parse John Hancock
# --------------------------------------------------

def load_john_hancock():

    print()
    print("John Hancock File:")
    print(JH_FILE)


    holdings = []

    current_fund = None


    with open(
        JH_FILE,
        "r",
        encoding="utf-8"
    ) as file:


        for line in file:

            line = line.strip()


            if not line:
                continue


            #
            # Detect subtotal
            #
            if line.startswith("Sub-Total"):

                numbers = re.findall(
                    r"[\d,]+\.\d+",
                    line
                )


                if len(numbers) >= 3:

                    value = clean_money(
                        numbers[2]
                    )


                    holdings.append(
                        {
                            "Source": "John Hancock",
                            "Description": current_fund,
                            "Value": value
                        }
                    )


                continue



            #
            # Detect fund names
            #
            ignore = [
                "Account Value",
                "Units",
                "Contributions",
                "Mine ($)",
                "Asset Allocation",
                "Target Date",
                "Aggressive Growth",
                "Growth & Income",
                "Total"
            ]


            if (
                not line.startswith(
                    (
                        "EE ",
                        "ER "
                    )
                )
                and not any(
                    x in line
                    for x in ignore
                )
            ):

                current_fund = line



    return pd.DataFrame(
        holdings
    )


def apply_jh_map(df):

    asset_map = pd.read_csv(
        ASSET_MAP_FILE
    )


    df = df.merge(
        asset_map,
        left_on="Description",
        right_on="Symbol",
        how="left"
    )


    # Remove duplicate lookup column
    df = df.drop(
        columns=[
            "Symbol"
        ]
    )


    df["Category"] = (
        df["Category"]
        .fillna("Unclassified")
    )


    df["RetirementBucket"] = (
        df["RetirementBucket"]
        .fillna(df["Category"])
    )


    df["StockPct"] = (
        df["StockPct"]
        .fillna(0)
    )


    df["BondPct"] = (
        df["BondPct"]
        .fillna(0)
    )


    df["CashPct"] = (
        df["CashPct"]
        .fillna(0)
    )


    return df


if __name__ == "__main__":

    df = load_john_hancock()

    df = apply_jh_map(
        df
    )

    output_dir = BASE_DIR / "output"

    output_dir.mkdir(
        exist_ok=True
    )


    df.to_csv(
        JH_OUTPUT,
        index=False
    )


    print()
    print(df)

    print()
    print("Created:")
    print(JH_OUTPUT)