#!/usr/bin/env python3

from pathlib import Path
import pandas as pd


BASE_DIR = Path(__file__).resolve().parent.parent

OUTPUT_DIR = BASE_DIR / "output"

OUTPUT_FILE = OUTPUT_DIR / "economic_exposure.csv"


INPUT_FILES = [
    OUTPUT_DIR / "schwab_assets.csv",
    OUTPUT_DIR / "jh_assets.csv",
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
        raise Exception(
            "No asset files found"
        )


    return pd.concat(
        frames,
        ignore_index=True
    )



def add_exposure(rows, asset_class, exposure, value):

    if value > 0:

        rows.append(
            {
                "AssetClass": asset_class,
                "Exposure": exposure,
                "Value": value
            }
        )



def create_exposure(df):

    rows = []

    for _, row in df.iterrows():

        value = row["Value"]

        category = row.get(
            "RetirementBucket",
            row.get(
                "Category",
                "Unclassified"
            )
        )

        stock_pct = row.get("StockPct",0)
        bond_pct = row.get("BondPct",0)
        cash_pct = row.get("CashPct",0)

        stock_label = category

        if "Balanced" in str(category):
            stock_label = "US Equity"
        

        add_exposure(
            rows,
            "Stocks",
            stock_label,
            value * stock_pct / 100
        )

        add_exposure(
            rows,
            "Bonds",
            "Bonds",
            value * bond_pct / 100
        )

        add_exposure(
            rows,
            "Cash",
            "Cash",
            value * cash_pct / 100
        )


    result = (
        pd.DataFrame(rows)
        .groupby(
            [
                "AssetClass",
                "Exposure"
            ]
        )
        ["Value"]
        .sum()
        .reset_index()
        .sort_values(
            "Value",
            ascending=False
        )
    )

    return result


def main():

    print()
    print("=" * 50)
    print(" Creating Detailed Economic Exposure")
    print("=" * 50)


    assets = load_assets()


    print()
    print(
        f"Assets loaded: {len(assets)}"
    )


    exposure = create_exposure(
        assets
    )


    OUTPUT_DIR.mkdir(
        exist_ok=True
    )


    exposure.to_csv(
        OUTPUT_FILE,
        index=False
    )


    print()
    print(exposure)

    print()
    print("Created:")
    print(OUTPUT_FILE)



if __name__ == "__main__":
    main()