#!/usr/bin/env python3

from pathlib import Path
import csv
import pandas as pd


DOWNLOAD_DIR = Path("/home/ts/Downloads")


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

    latest = max(
        files,
        key=lambda x: x.stat().st_mtime
    )

    return latest


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

    filename = find_latest_schwab_file()

    print()
    print("Schwab File:")
    print(filename)

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

        for data in data_rows:

            if not data:
                continue

            symbol = data[0].strip()

            # Ignore blank rows.
            if not symbol:
                continue

            # Ignore Schwab account header rows.
            if symbol in [
                "Roth_Tony ...497",
                "Indiv_Tony ...729",
                "Indiv_Mary ...873",
                "Rollover_IRA_Tony ...871",
                "Roth_Mary ...180",
                "Joint_Tony_Mary ...456"
            ]:
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

        # Keep account information.
        df["Account"] = account

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


# --------------------------------------------------
# Test
# --------------------------------------------------

if __name__ == "__main__":

    data = load_schwab()

    print()
    print(data)