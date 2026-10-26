#!/usr/bin/env python3

import csv
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path

from odf.opendocument import OpenDocumentSpreadsheet
from odf.style import Style, TableCellProperties
from odf.table import (
    Table,
    TableRow,
    TableCell,
    TableColumn,
    DatabaseRanges,
    DatabaseRange,
)
from odf.text import P

ROOT_DIR = Path("/home/dev/stock/alpha")
INPUT_FILE = ROOT_DIR / "input" / "data.csv"
OUTPUT_DIR = ROOT_DIR / "output"
CSV_FILE = OUTPUT_DIR / "parsed_data.csv"
ODS_FILE = OUTPUT_DIR / "parsed_data.ods"

# Overall score weights: must total 1.00.
WEIGHTS = {
    "mispricing": Decimal("0.40"),
    "debt": Decimal("0.20"),
    "profitability": Decimal("0.20"),
    "solvency": Decimal("0.20"),
}

HEADERS = [
    "Company",
    "Ticker",
    "Last Price",
    "Price Change",
    "Market Cap",
    "Mispricing",
    "Debt to Equity",
    "Profitability Score",
    "Solvency Score",
    "Mispricing Score",
    "Debt Score",
    "Overall Score",
]

CURRENCY_RE = r"(?:NT\$|[$€£¥₹₩﷼])?"


def clean_lines():
    """Read pasted text, removing blank lines and pasted headings."""
    lines = []

    with INPUT_FILE.open("r", encoding="utf-8-sig") as file:
        for raw_line in file:
            line = raw_line.strip()

            if not line or line.lower() == "text":
                continue

            if line.startswith("```"):
                continue

            if line in {
                "Company\tLast Price\tPrice Change\tMispricing",
                "Intrinsic Value (Base Case)",
                "Debt to Equity\tProfitability Score\tSolvency Score",
            }:
                continue

            lines.append(line)

    return lines


def is_ticker(value):
    return bool(
        re.fullmatch(r"[A-Za-z0-9.^=-]{1,15}", value.strip())
    )


def is_price(value):
    value = value.strip()
    pattern = (
        rf"^{CURRENCY_RE}\s*"
        r"\d[\d\s,]*(?:\.\d+)?$"
    )
    return bool(re.fullmatch(pattern, value))


def is_change(value):
    return bool(
        re.fullmatch(r"[+-]?\s*\d+(?:\.\d+)?\s*%", value.strip())
    )


def parse_number(value):
    """Convert a number containing currency symbols or separators."""
    value = value.strip()
    value = re.sub(rf"^{CURRENCY_RE}\s*", "", value)
    value = value.replace(",", "").replace(" ", "")
    return Decimal(value)


def parse_price(value):
    return parse_number(value)


def parse_change(value):
    """Return percentage points, e.g. '-0.3%' becomes Decimal('-0.3')."""
    return Decimal(value.strip().replace("%", "").replace(" ", ""))


def parse_market_cap(value):
    """Convert T, B, or M suffixes into full numeric values."""
    match = re.fullmatch(
        rf"\s*{CURRENCY_RE}\s*([\d,.]+)\s*([TtBbMm])\s*",
        value.strip(),
    )

    if not match:
        raise ValueError(f"Invalid market cap: {value}")

    number = Decimal(match.group(1).replace(",", ""))

    multipliers = {
        "T": Decimal("1000000000000"),
        "B": Decimal("1000000000"),
        "M": Decimal("1000000"),
    }

    return number * multipliers[match.group(2).upper()]


def parse_metrics(line):
    """
    Parse a metrics line such as:
    $5.1T    +18% undervalued    0.1    98    79

    Tab-separated input is preferred. A regex fallback supports
    pasted lines where tabs have been replaced by spaces.
    """
    fields = [field.strip() for field in line.split("\t") if field.strip()]

    if len(fields) >= 5:
        market_cap = fields[0]
        mispricing_text = fields[1]
        debt_text = fields[2]
        profitability_text = fields[3]
        solvency_text = fields[4]
    else:
        match = re.fullmatch(
            rf"\s*({CURRENCY_RE}\s*[\d,.]+\s*[TtBbMm])\s+"
            r"(N/A|[+-]?\d+(?:\.\d+)?%\s+"
            r"(?:under|over)valued)\s+"
            r"(\d+(?:\.\d+)?)\s+(\d+)\s+(\d+)\s*",
            line,
            re.IGNORECASE,
        )

        if not match:
            return None

        (
            market_cap,
            mispricing_text,
            debt_text,
            profitability_text,
            solvency_text,
        ) = match.groups()

    try:
        market_cap_value = parse_market_cap(market_cap)
        debt_value = Decimal(debt_text)
        profitability_value = Decimal(profitability_text)
        solvency_value = Decimal(solvency_text)

        # Remove descriptive words. Store the percentage as a number.
        mispricing_match = re.search(
            r"([+-]?\d+(?:\.\d+)?)\s*%",
            mispricing_text,
        )

        if mispricing_match:
            mispricing_value = Decimal(mispricing_match.group(1))
        elif mispricing_text.strip().upper() == "N/A":
            mispricing_value = None
        else:
            return None

        if debt_value < 0:
            return None

        if not (0 <= profitability_value <= 100):
            return None

        if not (0 <= solvency_value <= 100):
            return None

        return (
            market_cap_value,
            mispricing_value,
            debt_value,
            profitability_value,
            solvency_value,
        )

    except (ValueError, InvalidOperation):
        return None


def calculate_scores(mispricing, debt, profitability, solvency):
    """
    Return the Mispricing Score, Debt Score, and Overall Score.

    Mispricing is mapped from -100..+100 percentage points to 0..100.
    Debt score is 100 / (1 + debt-to-equity).
    N/A mispricing receives a neutral score of 50.
    """
    if mispricing is None:
        mispricing_score = Decimal("50")
    else:
        mispricing_score = max(
            Decimal("0"),
            min(Decimal("100"), Decimal("50") + mispricing / 2),
        )

    debt_score = Decimal("100") / (Decimal("1") + debt)

    overall = (
        mispricing_score * WEIGHTS["mispricing"]
        + debt_score * WEIGHTS["debt"]
        + profitability * WEIGHTS["profitability"]
        + solvency * WEIGHTS["solvency"]
    )

    return (
        mispricing_score,
        debt_score,
        overall.quantize(Decimal("0.01")),
    )


def format_number(value):
    """Write clean numeric strings without unnecessary trailing zeros."""
    if value is None:
        return ""

    return format(value, "f")


def parse_data():
    lines = clean_lines()
    rows = []
    skipped = 0
    i = 0

    while i + 4 < len(lines):
        company = lines[i]
        ticker = lines[i + 1]
        price_text = lines[i + 2]
        change_text = lines[i + 3]
        metrics_line = lines[i + 4]

        if (
            is_ticker(ticker)
            and is_price(price_text)
            and is_change(change_text)
        ):
            metrics = parse_metrics(metrics_line)

            if metrics is None:
                skipped += 1
                i += 5
                continue

            try:
                market_cap, mispricing, debt, profitability, solvency = metrics
                price = parse_price(price_text)
                change = parse_change(change_text)

                mispricing_score, debt_score, overall_score = calculate_scores(
                    mispricing,
                    debt,
                    profitability,
                    solvency,
                )

                rows.append([
                    company,
                    ticker,
                    format_number(price),
                    format_number(change),
                    format_number(market_cap),
                    format_number(mispricing),
                    format_number(debt),
                    format_number(profitability),
                    format_number(solvency),
                    format_number(mispricing_score),
                    format_number(debt_score),
                    format_number(overall_score),
                ])

            except (ValueError, InvalidOperation):
                skipped += 1

            i += 5
        else:
            i += 1

    return rows, skipped


def write_csv(rows):
    with CSV_FILE.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as file:
        writer = csv.writer(file)
        writer.writerow(HEADERS)
        writer.writerows(rows)


def write_ods(rows):
    """Create an ODS spreadsheet with numeric cells and filter buttons."""
    document = OpenDocumentSpreadsheet()

    # Header style.
    header_style = Style(
        name="Header",
        family="table-cell",
    )
    header_style.addElement(
        TableCellProperties(
            backgroundcolor="#D9EAF7",
            border="0.5pt solid #808080",
        )
    )
    document.automaticstyles.addElement(header_style)

    sheet = Table(name="Stocks")

    # Define columns.
    for _ in HEADERS:
        sheet.addElement(TableColumn())

    # Header row.
    header_row = TableRow()
    for heading in HEADERS:
        cell = TableCell(valuetype="string", stylename=header_style)
        cell.addElement(P(text=heading))
        header_row.addElement(cell)

    sheet.addElement(header_row)

    # Data rows. Numeric fields are stored as numeric ODS cells.
    numeric_columns = set(range(2, len(HEADERS)))

    for row in rows:
        table_row = TableRow()

        for column_index, value in enumerate(row):
            if column_index in numeric_columns and value != "":
                cell = TableCell(
                    valuetype="float",
                    value=str(value),
                )
                cell.addElement(P(text=str(value)))
            else:
                cell = TableCell(valuetype="string")
                cell.addElement(P(text=str(value)))

            table_row.addElement(cell)

        sheet.addElement(table_row)

    document.spreadsheet.addElement(sheet)

    # Enable filter buttons for the complete header + data range.
    database_ranges = DatabaseRanges()
    database_range = DatabaseRange(
        name="StocksFilter",
        targetrangeaddress=f"$Stocks.$A$1:$L${len(rows) + 1}",
        displayfilterbuttons="true",
        containsheader="true",
    )
    database_ranges.addElement(database_range)
    document.spreadsheet.addElement(database_ranges)

    document.save(str(ODS_FILE))


def main():
    if not INPUT_FILE.is_file():
        raise FileNotFoundError(f"Input file not found: {INPUT_FILE}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    rows, skipped = parse_data()

    if not rows:
        raise RuntimeError(
            "No complete records were parsed. Check the format of input/data.csv."
        )

    write_csv(rows)
    write_ods(rows)

    print(f"Input file:       {INPUT_FILE}")
    print(f"CSV output:       {CSV_FILE}")
    print(f"ODS output:       {ODS_FILE}")
    print(f"Records written:  {len(rows)}")
    print(f"Records skipped:  {skipped}")
    print("Overall score:    0-100, higher is better")
    print("Weights:          Mispricing 40%, Debt 20%, Profitability 20%, Solvency 20%")


if __name__ == "__main__":
    main()
