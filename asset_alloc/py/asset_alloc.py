#!/usr/bin/env python3

from pathlib import Path
import pandas as pd

from schwab import load_schwab


# --------------------------------------------------
# Paths
# --------------------------------------------------

PY_DIR = Path(__file__).resolve().parent
BASE_DIR = PY_DIR.parent

INPUT_DIR = BASE_DIR / "input"
OUTPUT_DIR = BASE_DIR / "output"


ASSET_MAP_FILE = INPUT_DIR / "asset_map.csv"

SCHWAB_OUTPUT = OUTPUT_DIR / "schwab_assets.csv"


# --------------------------------------------------
# Load CSV
# --------------------------------------------------

def load_csv(filename):

    if not filename.exists():
        print(f"ERROR: Missing file:")
        print(filename)
        return None

    return pd.read_csv(filename)



# --------------------------------------------------
# Categorize assets
# --------------------------------------------------

def apply_asset_map(df, asset_map):

    mapped = asset_map[
        [
            "Symbol",
            "Category",
            "SubCategory",
            "SourceType",
            "RetirementBucket",
            "StockPct",
            "BondPct",
            "CashPct",
            "InternationalPct"
        ]
    ]


    df = df.merge(
        mapped,
        on="Symbol",
        how="left"
    )


    #
    # Default Schwab equities to individual stocks
    #
    equity_mask = (
        df["Asset Type"]
        .str.strip()
        .eq("Equity")
    )


    df.loc[
        equity_mask &
        df["Category"].isna(),
        "Category"
    ] = "Individual Stock"


    df.loc[
        equity_mask &
        df["SubCategory"].isna(),
        "SubCategory"
    ] = "Stock"


    #
    # Add source
    #
    df["Source"] = "Schwab"


    #
    # Fill missing look-through values
    #
    df["RetirementBucket"] = (
        df["RetirementBucket"]
        .fillna(df["Category"])
    )


    df["StockPct"] = (
        df["StockPct"]
        .fillna(100 if equity_mask.any() else 0)
    )


    df["BondPct"] = (
        df["BondPct"]
        .fillna(0)
    )


    df["CashPct"] = (
        df["CashPct"]
        .fillna(0)
    )

    df["InternationalPct"] = (
        df["InternationalPct"]
        .fillna(0)
    )


    return df


# --------------------------------------------------
# Main
# --------------------------------------------------

def main():

    print("=" * 60)
    print(" Asset Allocation Analyzer")
    print("=" * 60)


    OUTPUT_DIR.mkdir(
        exist_ok=True
    )


    #
    # Load asset mapping
    #
    asset_map = load_csv(
        ASSET_MAP_FILE
    )


    #
    # Schwab
    #
    print()
    print("Processing Schwab...")
    
    schwab = load_schwab()
    print("\nBefore merge:")
    print(schwab.head())
    print(schwab["Source"].unique())

    print(
        f"Schwab positions loaded: {len(schwab)}"
    )


    #
    # Add categories
    #
    schwab = apply_asset_map(
        schwab,
        asset_map
    )


    #
    # Save
    #
    schwab.to_csv(
        SCHWAB_OUTPUT,
        index=False
    )


    print()
    print("Created:")
    print(SCHWAB_OUTPUT)


    print()
    print(schwab)


if __name__ == "__main__":
    main()