#!/usr/bin/python3

import os
import subprocess
import time
import uno

from com.sun.star.beans import PropertyValue


BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CSV_FILE = os.path.join(BASE_DIR, "../output/summary_intrinsic.csv")
ODS_FILE = os.path.join(BASE_DIR, "../output/summary_intrinsic.ods")


# Numeric code → human-readable name
SECTOR_NAME_MAP = {
    1: "Basic Materials",
    2: "Communication Services",
    3: "Consumer Cyclical",
    4: "Consumer Defensive",
    5: "Energy",
    6: "Financial Services",
    7: "Healthcare",
    8: "Industrials",
    9: "Real Estate",
    10: "Technology",
    11: "Utilities"
}

EXCH_CODE_MAP = {
    0: "N",  # NYSE
    1: "Q",  # Nasdaq
    2: "A",  # NYSE American/AMEX
    3: "C",  # Cboe
    4: "O",  # Other
}

INDEX_BIT_MAP = {
    1: "SP",  # S&P 500
    2: "NQ",  # Nasdaq-100
    4: "DJ",  # Dow Jones Industrial Average
    8: "R2",  # Russell 2000
    16: "M4",  # S&P MidCap 400
    32: "S6",  # S&P SmallCap 600
    64: "TM",  # CRSP U.S. Total Market
}


def prop(name, value):
    p = PropertyValue()
    p.Name = name
    p.Value = value
    return p


def find_column_index(sheet, end_col, header_name):
    for col in range(end_col + 1):
        header_value = sheet.getCellByPosition(col, 0).getString().strip()
        if header_value == header_name:
            return col
    return None


def get_cell_int_value(cell):
    raw_str = cell.getString().strip()
    if raw_str:
        try:
            return int(raw_str)
        except ValueError:
            return None

    try:
        return int(cell.getValue())
    except Exception:
        return None


def format_index_labels(bitmask):
    if bitmask is None:
        return ""

    labels = []
    for bit in sorted(INDEX_BIT_MAP.keys()):
        if bitmask & bit:
            labels.append(INDEX_BIT_MAP[bit])
    return " | ".join(labels)


def main():
    # Start LibreOffice listener
    subprocess.Popen(
        [
            "libreoffice",
            "--headless",
            "--accept=socket,host=localhost,port=2002;urp;",
            "--norestore",
            "--nofirststartwizard"
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    time.sleep(2)

    local_ctx = uno.getComponentContext()
    resolver = local_ctx.ServiceManager.createInstanceWithContext(
        "com.sun.star.bridge.UnoUrlResolver", local_ctx
    )
    ctx = resolver.resolve(
        "uno:socket,host=localhost,port=2002;urp;StarOffice.ComponentContext"
    )
    smgr = ctx.ServiceManager
    desktop = smgr.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)

    # Open CSV – fully automatic, no confirmation dialog
    doc = desktop.loadComponentFromURL(
        uno.systemPathToFileUrl(os.path.abspath(CSV_FILE)),
        "_blank",
        0,
        (
            prop("FilterName", "Text - txt - csv (StarCalc)"),
            prop("FilterOptions", "44,34,0,1"),
            prop("Hidden", True),
            prop("ReadOnly", True),
        )
    )

    sheet = doc.Sheets.getByIndex(0)

    # Determine used range
    cursor = sheet.createCursor()
    cursor.gotoEndOfUsedArea(True)
    end_row = cursor.RangeAddress.EndRow
    end_col = cursor.RangeAddress.EndColumn

    # -------------------------------------------------
    # Convert metadata code columns for report readability
    # -------------------------------------------------
    sector_col = find_column_index(sheet, end_col, "Sector")
    exch_col = find_column_index(sheet, end_col, "Exch")
    index_col = find_column_index(sheet, end_col, "Index")

    if sector_col is not None:
        for row in range(1, end_row + 1):
            cell = sheet.getCellByPosition(sector_col, row)
            code = get_cell_int_value(cell)
            if code in SECTOR_NAME_MAP:
                cell.setString(SECTOR_NAME_MAP[code])

    if exch_col is not None:
        for row in range(1, end_row + 1):
            cell = sheet.getCellByPosition(exch_col, row)
            code = get_cell_int_value(cell)
            if code in EXCH_CODE_MAP:
                cell.setString(EXCH_CODE_MAP[code])

    if index_col is not None:
        for row in range(1, end_row + 1):
            cell = sheet.getCellByPosition(index_col, row)
            code = get_cell_int_value(cell)
            label = format_index_labels(code)
            if label:
                cell.setString(label)
    # -------------------------------------------------

    # Freeze first row
    controller = doc.getCurrentController()
    controller.freezeAtPosition(0, 1)

    # Auto filter
    database_ranges = doc.DatabaseRanges
    if not database_ranges.hasByName("ReportRange"):
        database_ranges.addNewByName("ReportRange", cursor.RangeAddress)

    db_range = database_ranges.getByName("ReportRange")
    db_range.AutoFilter = True

    # Auto size columns
    columns = sheet.Columns
    for col in range(end_col + 1):
        columns.getByIndex(col).OptimalWidth = True

    # Bold header
    header = sheet.getCellRangeByPosition(0, 0, end_col, 0)
    header.CharWeight = 150

    # Save as ODS
    doc.storeAsURL(
        uno.systemPathToFileUrl(os.path.abspath(ODS_FILE)),
        (prop("FilterName", "calc8"),)
    )

    doc.close(True)
    subprocess.run(["pkill", "-f", "soffice.bin"])

    print(f"   Created: {os.path.abspath(ODS_FILE)}")


if __name__ == "__main__":
    main()