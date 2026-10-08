#!/usr/bin/env python3

from pathlib import Path
from datetime import datetime
import csv
import re
import pandas as pd


BASE_DIR = Path(__file__).resolve().parent.parent
INPUT_DIR = BASE_DIR / "input"
OUTPUT_DIR = BASE_DIR / "output"

DOWNLOAD_DIR = Path("/home/ts/Downloads")
ASSET_MAP_FILE = INPUT_DIR / "asset_map.csv"
OUTPUT_FILE = OUTPUT_DIR / "schwab_assets.csv"
SCHWAB_EXPORT_PATTERN = re.compile(
    r"^All-Accounts-Positions-(\d{4}-\d{2}-\d{2})-(\d{6})\.csv$"
)
ACCOUNT_LABEL_PATTERN = re.compile(r"\.\.\.\d{3}$")
EXCLUDED_ACCOUNTS = {
    "Indiv_Hailey ...647",
    "Indiv_Josh ...792",
}


# --------------------------------------------------
# Find latest Schwab file
# --------------------------------------------------

def find_latest_schwab_file():

    files = list(
        DOWNLOAD_DIR.glob("All-Accounts-Positions-*.csv")
    )

    if not files:
        raise FileNotFoundError(
            "No Schwab export found"
        )

    dated_files = []
    for file_path in files:
        match = SCHWAB_EXPORT_PATTERN.match(file_path.name)
        if not match:
            continue
        file_timestamp = datetime.strptime(
            f"{match.group(1)}-{match.group(2)}",
            "%Y-%m-%d-%H%M%S",
        )
        dated_files.append((file_path, file_timestamp))

    if not dated_files:
        raise FileNotFoundError(
            "No Schwab export found matching naming convention "
            "All-Accounts-Positions-YYYY-MM-DD-HHMMSS.csv"
        )

    latest_file, latest_timestamp = max(
        dated_files,
        key=lambda item: (item[1], item[0].stat().st_mtime),
    )

    return latest_file, latest_timestamp


# --------------------------------------------------
# Convert Schwab money values
# --------------------------------------------------

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


# --------------------------------------------------
# Load Schwab positions
# --------------------------------------------------

def load_schwab():

    filename, export_timestamp = find_latest_schwab_file()

    print()
    print("Schwab File Selected:")
    print(filename)
    print(f"Export Timestamp: {export_timestamp.strftime('%Y-%m-%d %H:%M:%S')}")

    # Read the file one CSV row at a time.
    # This is necessary because Schwab places
    # multiple account sections in the same file.
    with open(
        filename,
        "r",
        newline="",
        encoding="utf-8-sig"
    ) as file:

        rows = list(
            csv.reader(file)
        )

    frames = []

    for row_number, row in enumerate(rows):

        # Find each position header.
        if not row:
            continue

        if row[0].strip() != "Symbol":
            continue

        header_row = row_number

        # Account name is immediately before the header.
        account = ""

        if header_row > 0:
            account = rows[
                header_row - 1
            ][0].strip()

        header = row

        # Find the next Symbol header.
        end_row = len(rows)

        for next_row in range(
            header_row + 1,
            len(rows)
        ):

            if (
                rows[next_row]
                and rows[next_row][0].strip() == "Symbol"
            ):
                end_row = next_row
                break

        # Get the rows belonging to this account.
        data_rows = rows[
            header_row + 1:end_row
        ]

        # Convert rows to dictionaries using
        # the Schwab header.
        records = []
        active_account = account
        skip_active_account = active_account in EXCLUDED_ACCOUNTS

        for data in data_rows:

            if not data:
                continue

            symbol = data[0].strip()

            # Ignore blank rows.
            if not symbol:
                continue

            # Track account delimiters so we can skip selected accounts
            # while continuing when the file returns to another account.
            if ACCOUNT_LABEL_PATTERN.search(symbol):
                active_account = symbol
                skip_active_account = active_account in EXCLUDED_ACCOUNTS
                continue

            if skip_active_account:
                continue


            # Make the row the same length as the header.
            if len(data) < len(header):
                data = data + (
                    [""] * (len(header) - len(data))
                )

            elif len(data) > len(header):
                data = data[:len(header)]

            record = dict(
                zip(header, data)
            )
            record["Account"] = active_account

            records.append(record)

        if not records:
            continue

        df = pd.DataFrame(records)

        # Remove totals and cash rows.
        df = df[
            ~df["Symbol"].isin(
                [
                    "Positions Total",
                    "Cash & Cash Investments"
                ]
            )
        ]

        frames.append(df)

    if not frames:
        raise ValueError(
            "No Schwab position headers found"
        )

    # Combine all Schwab account sections.
    df = pd.concat(
        frames,
        ignore_index=True
    )

    # Return only the fields needed by the
    # asset allocation program.
    result = pd.DataFrame(
        {
            "Source": "Schwab",
            "Account": df["Account"].values,
            "Symbol": df["Symbol"].values,
            "Description": df["Description"].values,
            "Value": df[
                "Mkt Val (Market Value)"
            ].apply(clean_money).values,
            "Asset Type": df["Asset Type"].values,
        }
    )

    return result


def load_asset_map():

    if not ASSET_MAP_FILE.exists():
        raise FileNotFoundError(
            ASSET_MAP_FILE
        )

    asset_map = pd.read_csv(
        ASSET_MAP_FILE,
        dtype={"Symbol": str}
    )

    asset_map["Symbol"] = (
        asset_map["Symbol"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    map_columns = [
        "Symbol",
        "Category",
        "SubCategory",
        "SourceType",
        "RetirementBucket",
        "StockPct",
        "BondPct",
        "CashPct",
        "InternationalPct",
    ]

    return asset_map[map_columns]


def apply_asset_map(schwab_df, asset_map):

    result = schwab_df.copy()
    result["Symbol"] = (
        result["Symbol"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    result = result.merge(
        asset_map,
        on="Symbol",
        how="left"
    )

    equity_unmapped = (
        result["Category"].isna()
        & (
            result["Asset Type"]
            .fillna("")
            .str.strip() == "Equity"
        )
    )

    result.loc[equity_unmapped, "Category"] = "Individual Stock"
    result.loc[equity_unmapped, "SubCategory"] = "Stock"
    result.loc[equity_unmapped, "SourceType"] = ""
    result.loc[equity_unmapped, "RetirementBucket"] = "Individual Stock"
    result.loc[equity_unmapped, "StockPct"] = 100
    result.loc[equity_unmapped, "BondPct"] = 0
    result.loc[equity_unmapped, "CashPct"] = 0
    result.loc[equity_unmapped, "InternationalPct"] = 0

    pct_columns = [
        "StockPct",
        "BondPct",
        "CashPct",
        "InternationalPct",
    ]
    for col in pct_columns:
        result[col] = (
            pd.to_numeric(
                result[col],
                errors="coerce"
            )
            .fillna(0)
        )

    ordered_columns = [
        "Source",
        "Account",
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
        "InternationalPct",
    ]

    return result[ordered_columns]


# --------------------------------------------------
# Test
# --------------------------------------------------

if __name__ == "__main__":

    OUTPUT_DIR.mkdir(
        exist_ok=True
    )

    data = load_schwab()
    asset_map = load_asset_map()
    data = apply_asset_map(
        data,
        asset_map
    )

    data.to_csv(
        OUTPUT_FILE,
        index=False
    )

    print()
    print(
        f"Created: {OUTPUT_FILE}"
    )
    print(data)