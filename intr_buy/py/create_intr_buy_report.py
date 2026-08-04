#!/usr/bin/python3

import os
import subprocess
import time
import uno

from com.sun.star.beans import PropertyValue


BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CSV_FILE = os.path.join(BASE_DIR, "../output/combined_report.csv")
ODS_FILE = os.path.join(BASE_DIR, "../output/combined_report.ods")


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
    10: "Sector",
    11: "Technology",
    12: "Utilities"
}


def prop(name, value):
    p = PropertyValue()
    p.Name = name
    p.Value = value
    return p



def main():

    print("       Starting LibreOffice report creation...")


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

    desktop = smgr.createInstanceWithContext(
        "com.sun.star.frame.Desktop",
        ctx
    )


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


    cursor = sheet.createCursor()
    cursor.gotoEndOfUsedArea(True)

    end_row = cursor.RangeAddress.EndRow
    end_col = cursor.RangeAddress.EndColumn


    # -------------------------------------------------
    # Convert Sector integer to text
    # -------------------------------------------------

    sector_col = None

    for col in range(end_col + 1):

        header = (
            sheet
            .getCellByPosition(col,0)
            .getString()
            .strip()
        )

        if header == "Sector":
            sector_col = col
            break


    if sector_col is not None:

        for row in range(1, end_row + 1):

            cell = sheet.getCellByPosition(
                sector_col,
                row
            )

            try:

                code = int(
                    float(
                        cell.getString()
                        or cell.getValue()
                    )
                )

                cell.setString(
                    SECTOR_NAME_MAP.get(
                        code,
                        "Unknown"
                    )
                )

            except:
                pass


    # -------------------------------------------------
    # Freeze header
    # -------------------------------------------------

    controller = doc.getCurrentController()

    controller.freezeAtPosition(
        0,
        1
    )


    # -------------------------------------------------
    # Auto filter
    # -------------------------------------------------

    database_ranges = doc.DatabaseRanges

    if not database_ranges.hasByName("ReportRange"):

        database_ranges.addNewByName(
            "ReportRange",
            cursor.RangeAddress
        )


    database_ranges.getByName(
        "ReportRange"
    ).AutoFilter = True



    # -------------------------------------------------
    # Format
    # -------------------------------------------------

    for col in range(end_col + 1):

        sheet.Columns.getByIndex(
            col
        ).OptimalWidth = True



    header = sheet.getCellRangeByPosition(
        0,
        0,
        end_col,
        0
    )

    header.CharWeight = 150



    # -------------------------------------------------
    # Save ODS
    # -------------------------------------------------

    doc.storeAsURL(
        uno.systemPathToFileUrl(
            os.path.abspath(ODS_FILE)
        ),
        (
            prop(
                "FilterName",
                "calc8"
            ),
        )
    )


    doc.close(True)


    subprocess.run(
        ["pkill", "-f", "soffice.bin"]
    )


    print(
        f"       Created: {ODS_FILE}"
    )



if __name__ == "__main__":
    main()