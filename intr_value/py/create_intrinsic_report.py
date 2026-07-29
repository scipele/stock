#!/usr/bin/python3

import os
import subprocess
import time
import uno

from com.sun.star.beans import PropertyValue


BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CSV_FILE = os.path.join(BASE_DIR, "../output/summary_intrinsic.csv")
ODS_FILE = os.path.join(BASE_DIR, "../output/summary_intrinsic.ods")


def prop(name, value):
    p = PropertyValue()
    p.Name = name
    p.Value = value
    return p


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
        "com.sun.star.bridge.UnoUrlResolver",
        local_ctx
    )

    ctx = resolver.resolve(
        "uno:socket,host=localhost,port=2002;urp;StarOffice.ComponentContext"
    )

    smgr = ctx.ServiceManager
    desktop = smgr.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)

    # Open CSV
    doc = desktop.loadComponentFromURL(
        uno.systemPathToFileUrl(os.path.abspath(CSV_FILE)),
        "_blank",
        0,
        (
            prop("FilterName", "Text - txt - csv (StarCalc)"),
            prop("Hidden", False),
        )
    )

    sheet = doc.Sheets.getByIndex(0)

    # Determine used range
    cursor = sheet.createCursor()
    cursor.gotoEndOfUsedArea(True)
    end_row = cursor.RangeAddress.EndRow
    end_col = cursor.RangeAddress.EndColumn

    # Freeze first row
    controller = doc.getCurrentController()
    controller.freezeAtPosition(0, 1)

    # Auto filter
    database_ranges = doc.DatabaseRanges
    if not database_ranges.hasByName("ReportRange"):
        database_ranges.addNewByName("ReportRange", cursor.RangeAddress)
    db_range = database_ranges.getByName("ReportRange")
    db_range.AutoFilter = True

    # ---------- Number formatting (commas, no $) ----------
    # Column index mapping (0-based) after the new Upside_pct column:
    # 0 Rank
    # 1 Ticker
    # 2 Company
    # 3 Sector
    # 4 Price
    # 5 IntrinsicValue
    # 6 MarginOfSafety_pct
    # 7 Upside_pct
    # 8 GrowthRate
    # 9 WACC
    # 10 FCF_TTM
    # 11 NetDebt
    # 12 Shares
    # 13 MarketCap
    # 14 ForwardPE
    # 15 TrailingPE
    # 16 DataQuality

    # Format: #,##0.00  for price-style columns
    # Format: #,##0     for large whole-number columns

    def format_column(col_idx, fmt):
        cell_range = sheet.getCellRangeByPosition(col_idx, 1, col_idx, end_row)
        cell_range.NumberFormat = doc.NumberFormats.getStandardFormat(
            # We set a custom format string via the format key
            0  # placeholder – we override below
        )
        # Better way: apply a format string directly
        number_formats = doc.NumberFormats
        locale = doc.CharLocale
        format_key = number_formats.queryKey(fmt, locale, True)
        if format_key == -1:
            format_key = number_formats.addNew(fmt, locale)
        cell_range.NumberFormat = format_key

    # Price & IntrinsicValue → 2 decimal places with commas
    format_column(4, "#,##0.00")   # Price
    format_column(5, "#,##0.00")   # IntrinsicValue

    # Large money / count columns → whole numbers with commas
    format_column(10, "#,##0")     # FCF_TTM
    format_column(11, "#,##0")     # NetDebt
    format_column(12, "#,##0")     # Shares
    format_column(13, "#,##0")     # MarketCap

    # Percentage-style columns (optional nice formatting)
    format_column(6, "0.0")        # MarginOfSafety_pct
    format_column(7, "0.0")        # Upside_pct
    format_column(8, "0.00%")      # GrowthRate (will show as percent)
    format_column(9, "0.00%")      # WACC

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