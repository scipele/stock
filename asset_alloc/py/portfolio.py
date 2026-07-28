#!/usr/bin/env python3

from pathlib import Path
import pandas as pd


# --------------------------------------------------
# Paths
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent

INPUT_DIR = BASE_DIR / "input"
OUTPUT_DIR = BASE_DIR / "output"


SCHWAB_FILE = OUTPUT_DIR / "schwab_assets.csv"
JH_FILE = OUTPUT_DIR / "jh_assets.csv"
MANUAL_FILE = INPUT_DIR / "manual.csv"

OUTPUT_FILE = OUTPUT_DIR / "all_assets.csv"



# --------------------------------------------------
# Load file helper
# --------------------------------------------------

def load_file(filename):

    if not filename.exists():
        print(f"Missing:")
        print(filename)
        return pd.DataFrame()

    return pd.read_csv(filename)



# --------------------------------------------------
# Normalize columns
# --------------------------------------------------

def normalize_columns(df):

    expected = [
        "Source",
        "Symbol",
        "Description",
        "Value",
        "Asset Type",
        "Category",
        "SubCategory",
        "SourceType",
        "RetirementBucket",
        "StockPct",
        "BondPct",
        "CashPct",
        "InternationalPct"
    ]

    for col in expected:
        if col not in df.columns:
            df[col] = None

    return df[expected]


# --------------------------------------------------
# Main
# --------------------------------------------------

def main():

    print("=" * 60)
    print(" Building Combined Portfolio")
    print("=" * 60)


    OUTPUT_DIR.mkdir(
        exist_ok=True
    )


    #
    # Load sources
    #

    schwab = load_file(
        SCHWAB_FILE
    )

    jh = load_file(
        JH_FILE
    )

    manual = load_file(
        MANUAL_FILE
    )


    print()
    print("Loaded:")
    print(f" Schwab       : {len(schwab)}")
    print(f" John Hancock : {len(jh)}")
    print(f" Manual       : {len(manual)}")


    #
    # Normalize
    #

    schwab = normalize_columns(
        schwab
    )

    print()
    print("After normalize:")
    print(schwab.columns.tolist())

    portfolio = pd.concat(
        [
            schwab,
            jh,
            manual
        ],
        ignore_index=True
    )

    print()
    print("After concat:")
    print(portfolio.columns.tolist())

    jh = normalize_columns(
        jh
    )

    manual = normalize_columns(
        manual
    )


    #
    # Combine
    #

    portfolio = pd.concat(
        [
            schwab,
            jh,
            manual
        ],
        ignore_index=True
    )


    #
    # Clean values
    #

    portfolio["Value"] = (
        pd.to_numeric(
            portfolio["Value"],
            errors="coerce"
        )
        .fillna(0)
    )


    portfolio["Category"] = (
        portfolio["Category"]
        .fillna("Unclassified")
    )

    portfolio["RetirementBucket"] = (
    portfolio["RetirementBucket"]
    .fillna(portfolio["Category"])
)

    portfolio["StockPct"] = (
        pd.to_numeric(
            portfolio["StockPct"],
            errors="coerce"
        )
        .fillna(0)
    )

    portfolio["BondPct"] = (
        pd.to_numeric(
            portfolio["BondPct"],
            errors="coerce"
        )
        .fillna(0)
    )

    portfolio["CashPct"] = (
        pd.to_numeric(
            portfolio["CashPct"],
            errors="coerce"
        )
        .fillna(0)
    )


    #
    # Save
    #

    portfolio.to_csv(
        OUTPUT_FILE,
        index=False
    )


    print()
    print("Created:")
    print(OUTPUT_FILE)


    print()
    print(
        portfolio.head(10)
    )


if __name__ == "__main__":
    main()