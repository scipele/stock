#!/usr/bin/env python3

from pathlib import Path
import pandas as pd
import glob


DOWNLOAD_DIR = Path("/home/ts/Downloads")


def find_latest_schwab_file():

    files = list(
        DOWNLOAD_DIR.glob("Community Property-Positions-*.csv")
    )

    if not files:
        raise FileNotFoundError(
            "No Schwab export found"
        )

    latest = max(files, key=lambda x: x.stat().st_mtime)

    return latest



def clean_money(value):

    if pd.isna(value):
        return 0.0

    value = str(value)

    value = (
        value.replace("$", "")
             .replace(",", "")
             .strip()
    )

    if value in ("", "--"):
        return 0.0

    return float(value)



def load_schwab():

    filename = find_latest_schwab_file()

    print()
    print("Schwab File:")
    print(filename)


    # Schwab has title rows before the header
    df = pd.read_csv(
        filename,
        skiprows=1
    )


    # Remove empty rows
    df = df.dropna(
        how="all"
    )


    # Keep only real positions
    df = df[
        df["Symbol"].notna()
    ]


    # Remove totals
    df = df[
        ~df["Symbol"].isin(
            [
                "Positions Total",
                "Cash & Cash Investments"
            ]
        )
    ]

    result = pd.DataFrame(
        {
            "Source": "Schwab",
            "Symbol": df["Symbol"].values,
            "Description": df["Description"].values,
            "Value": df["Mkt Val (Market Value)"].apply(clean_money).values,
            "Asset Type": df["Asset Type"].values,
        }
    )

    return result



if __name__ == "__main__":

    data = load_schwab()

    print()
    print(data)
