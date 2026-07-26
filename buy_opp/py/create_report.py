#!/usr/bin/env python3

from pathlib import Path
import pandas as pd


BASE_DIR = Path(__file__).resolve().parent.parent

INPUT_FILE = BASE_DIR / "output/summary_all.csv"
OUTPUT_FILE = BASE_DIR / "output/summary_all.ods"


def main():

    print("Creating LibreOffice report...")

    df = pd.read_csv(INPUT_FILE)

    df.to_excel(
        OUTPUT_FILE,
        engine="odf",
        index=False
    )

    print(f"Created {OUTPUT_FILE}")


if __name__ == "__main__":
    main()