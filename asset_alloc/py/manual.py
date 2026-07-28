#!/usr/bin/env python3

from pathlib import Path
import pandas as pd


BASE_DIR = Path(__file__).resolve().parent.parent

INPUT_FILE = BASE_DIR / "input" / "manual.csv"
OUTPUT_FILE = BASE_DIR / "output" / "manual_assets.csv"


def main():

    df = pd.read_csv(
        INPUT_FILE
    )


    # Add fields used by lookthrough
    df["SubCategory"] = df["Category"]


    df.to_csv(
        OUTPUT_FILE,
        index=False
    )


    print()
    print(df)

    print()
    print("Created:")
    print(OUTPUT_FILE)



if __name__ == "__main__":
    main()