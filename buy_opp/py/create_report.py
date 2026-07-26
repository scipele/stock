#!/usr/bin/python3

import os
import subprocess
import time
import uno

from com.sun.star.beans import PropertyValue


BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CSV_FILE = os.path.join(
    BASE_DIR,
    "../output/summary_all.csv"
)

ODS_FILE = os.path.join(
    BASE_DIR,
    "../output/summary_all.ods"
)


def prop(name,value):
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

    desktop = smgr.createInstanceWithContext(
        "com.sun.star.frame.Desktop",
        ctx
    )


    # Open CSV
    doc = desktop.loadComponentFromURL(
        uno.systemPathToFileUrl(
            os.path.abspath(CSV_FILE)
        ),
        "_blank",
        0,
        (
            prop("FilterName","Text - txt - csv (StarCalc)"),
            prop("Hidden",False),
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

    controller.freezeAtPosition(
        0,
        1
    )


    # Auto filter
    database_ranges = doc.DatabaseRanges

    if not database_ranges.hasByName("ReportRange"):

        database_ranges.addNewByName(
            "ReportRange",
            cursor.RangeAddress
        )

    db_range = database_ranges.getByName(
        "ReportRange"
    )

    db_range.AutoFilter = True


    # Auto size columns
    columns = sheet.Columns

    for col in range(end_col + 1):
        columns.getByIndex(col).OptimalWidth = True


    # Bold header
    header = sheet.getCellRangeByPosition(
        0,
        0,
        end_col,
        0
    )

    header.CharWeight = 150

    # Save as ODS
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
    subprocess.run(["pkill", "-f", "soffice.bin"])

    print(f"   Created: {os.path.abspath(ODS_FILE)}")
    

if __name__ == "__main__":
    main()