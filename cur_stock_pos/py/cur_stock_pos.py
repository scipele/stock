# read all current posistions

from pathlib import Path
import csv
from datetime import datetime
import re
import pandas as pd

# Define Folder and filename patterns
BASE_DIR = Path(__file__).resolve().parent.parent
DOWNLOAD_DIR = Path("/home/ts/Downloads")
OUTPUT_DIR = BASE_DIR / "output"

SCHWAB_EXPORT_PATTERN = re.compile(
    r"^All-Accounts-Positions-(\d{4}-\d{2}-\d{2})-(\d{6})\.csv$"
)
ACCOUNT_LABEL_PATTERN = re.compile(r"\.\.\.\d{3}$")
EXCLUDED_ACCOUNTS = {
    "Indiv_Hailey ...647",
    "Indiv_Josh ...792",
}

class ClearPrintDataFrame(pd.DataFrame):
    """Custom DataFrame that automatically left-aligns headers and data columns when printed."""
    @property
    def _constructor(self):
        return ClearPrintDataFrame

    def __str__(self):
        text_cols = ["Account", "Symbol", "Description", "Sector"]
        
        # 1. Dynamically left-justify text column values based on max length
        formatters = {
            col: lambda x, c=col: f"{str(x):<{max(self[c].astype(str).str.len())}}"
            for col in text_cols if col in self.columns
        }
        
        # 2. Add justify="left" to align the header row text to the left edge
        return self.to_string(formatters=formatters, justify="left")

    def __repr__(self):
        return self.__str__()
    
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


def clean_money(value):
    if pd.isna(value):
        return 0.0

    value = str(value)

    value = value.replace("$", "").replace(",", "").strip()

    # Check if the string is empty, a standard placeholder, or consists only of dashes
    if value in ("", "--") or all(char == "-" for char in value):
        return 0.0

    try:
        return float(value)
    except ValueError:
        # Fallback to 0.0 if any other unexpected text format slips through
        return 0.0


def read_csv():

    filename, export_timestamp = find_latest_schwab_file()

    print()
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

            # only append the record for Equities only
            if record["Asset Type"] == "Equity":
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
    result = pd.DataFrame(
        {
            "Symbol": df["Symbol"].values,
            "Description" :df["Description"].values,
            "Qty": df["Qty (Quantity)"].values,
            "Mk_Value": df["Mkt Val (Market Value)"].apply(clean_money).values,
            "Cost_Basis": df["Cost Basis"].apply(clean_money).values,
            "delta": (df["Mkt Val (Market Value)"].apply(clean_money).values) - (df["Cost Basis"].apply(clean_money).values),
            "pct": ((((df["Mkt Val (Market Value)"].apply(clean_money) / df["Cost Basis"].apply(clean_money)) - 1) * 100).round(2).astype(str) + "%").values,
            "Sector": df["Sector"].values,
            "Account": df["Account"].values
        }
    )

    # 1. Sort by Symbol, then Account, before calculating totals
    result = result.sort_values(by=["Symbol", "Account"], ascending=[True, True]).reset_index(drop=True)

    # 2. Calculate the numeric totals FIRST while the columns are still numbers
    total_row = result.sum(numeric_only=True)

    # 3. Add your text fields to that total row template
    total_row["Account"] = ""
    total_row["Symbol"] = ""
    total_row["Description"] = ""
    total_row["Qty"] = ""
    total_row["pct"] = ""
    total_row["Sector"] = ""

    # 4. Safely append the divider line row
    result.loc["------"] = "------"

    # 5. Safely append your pre-calculated total row
    result.loc["Totals"] = total_row

     # 6. Pre-pad the text columns to force structural left-alignment when printed later
    text_cols = ["Account", "Symbol", "Description", "Sector"]
    for col in text_cols:
        # Find the max string length currently in the column
        max_len = max(result[col].astype(str).str.len())
        # Left-justify every string in that column to match the max length
        result[col] = result[col].apply(lambda x: f"{str(x):<{max_len}}")

        # ... Your existing code up through step 6 ...
    for col in text_cols:
        max_len = max(result[col].astype(str).str.len())
        result[col] = result[col].apply(lambda x: f"{str(x):<{max_len}}")
 
    # 7. Wrap inside the custom left-justified printing class
    return ClearPrintDataFrame(result)


def sector_values(data):
    # Create a local copy to avoid a SettingWithCopyWarning
    df = data.copy()
    # ignore line "-----"
    df = df[df["Account"].str.strip() != "------"]

    # Apply your clean_money function to each value in the financial columns
    for col in ["Mk_Value", "Cost_Basis", "delta"]:
        if col in df.columns:
            df[col] = df[col].map(clean_money)

    # Now that the columns are proper floats, the sum will work numerically
    sector_sums = df.groupby("Sector").agg(
        Mk_Value_sum=("Mk_Value", "sum"),
        Cost_Basis_sum=("Cost_Basis", "sum"),
        delta_sum=("delta", "sum"),
    )

    # Calculate percent change safely
    sector_sums["pct_change"] = (
        (sector_sums["Mk_Value_sum"] / sector_sums["Cost_Basis_sum"] - 1) * 100
    ).round(2)

    return sector_sums


def aggregate_tickers_accross_accounts(data):


    # Create a local copy to avoid a SettingWithCopyWarning
    df = data.copy()
    
    # ignore line "-----"
    df = df[df["Account"].str.strip() != "------"]

    # Apply your clean_money function to each value in the financial columns
    for col in ["Mk_Value", "Cost_Basis", "delta"]:
        if col in df.columns:
            df[col] = df[col].map(clean_money)

    # Now that the columns are proper floats, the sum will work numerically
    ticker_agg = df.groupby("Symbol").agg(
        Mk_Value_sum=("Mk_Value", "sum"),
        Cost_Basis_sum=("Cost_Basis", "sum"),
        delta_sum=("delta", "sum"),
    )

    # Calculate percent change safely
    ticker_agg["pct_change"] = (
        (ticker_agg["Mk_Value_sum"] / ticker_agg["Cost_Basis_sum"] - 1) * 100
    ).round(2)

    return ticker_agg


if __name__ == "__main__":

    OUTPUT_DIR.mkdir(
        exist_ok=True
    )

    data = read_csv()
    print(f"1. All Data:\n{data}\n\n")
    print(f"2. Sector Values Aggregated:\n{sector_values(data)}\n\n")
    print(
        f"3. Aggregate_tickers_accross_accounts sorted by delta_sum:\n"
        f"{aggregate_tickers_accross_accounts(data).sort_values(by='delta_sum', ascending=False)}"
    )
