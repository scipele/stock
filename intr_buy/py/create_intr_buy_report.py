#!/usr/bin/python3

import os
import shutil
import subprocess
import tempfile
import time
import uuid
import uno

from com.sun.star.beans import PropertyValue


BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CSV_FILE = os.path.join(BASE_DIR, "../output/combined_report.csv")
ODS_FILE = os.path.join(BASE_DIR, "../output/combined_report.ods")
UNO_CONNECT_RETRIES = 30
UNO_RETRY_DELAY_SEC = 1


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
        header = sheet.getCellByPosition(col, 0).getString().strip()
        if header == header_name:
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

    print("       Starting LibreOffice report creation...")

    pipe_name = f"intr_buy_report_pipe_{uuid.uuid4().hex[:8]}"
    profile_dir = tempfile.mkdtemp(prefix="intr_buy_lo_")
    user_install_url = uno.systemPathToFileUrl(profile_dir)

    office_cmd = [
        "libreoffice",
        "--headless",
        "--invisible",
        "--nologo",
        "--nodefault",
        "--nolockcheck",
        "--norestore",
        "--nofirststartwizard",
        f"-env:UserInstallation={user_install_url}",
        f"--accept=pipe,name={pipe_name};urp;",
    ]

    office_proc = subprocess.Popen(
        office_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    doc = None
    desktop = None

    try:
        local_ctx = uno.getComponentContext()

        resolver = local_ctx.ServiceManager.createInstanceWithContext(
            "com.sun.star.bridge.UnoUrlResolver",
            local_ctx
        )

        ctx = None

        for _ in range(UNO_CONNECT_RETRIES):
            if office_proc.poll() is not None:
                _, err = office_proc.communicate(timeout=1)
                raise RuntimeError(
                    "LibreOffice exited before UNO listener became ready. "
                    f"stderr: {err.strip() or 'n/a'}"
                )

            try:
                ctx = resolver.resolve(
                    f"uno:pipe,name={pipe_name};urp;StarOffice.ComponentContext"
                )
                break
            except Exception:
                time.sleep(UNO_RETRY_DELAY_SEC)

        if ctx is None:
            raise RuntimeError(
                "Unable to connect to LibreOffice listener via UNO pipe "
                f"'{pipe_name}'"
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

        sector_col = find_column_index(sheet, end_col, "Sector")
        exch_col = find_column_index(sheet, end_col, "Exch")
        index_col = find_column_index(sheet, end_col, "Index")


        if sector_col is not None:

            for row in range(1, end_row + 1):

                cell = sheet.getCellByPosition(
                    sector_col,
                    row
                )

                code = get_cell_int_value(cell)

                if code in SECTOR_NAME_MAP:
                    cell.setString(SECTOR_NAME_MAP[code])


        if exch_col is not None:

            for row in range(1, end_row + 1):

                cell = sheet.getCellByPosition(
                    exch_col,
                    row
                )

                code = get_cell_int_value(cell)
                if code in EXCH_CODE_MAP:
                    cell.setString(EXCH_CODE_MAP[code])


        if index_col is not None:

            for row in range(1, end_row + 1):

                cell = sheet.getCellByPosition(
                    index_col,
                    row
                )

                code = get_cell_int_value(cell)
                label = format_index_labels(code)

                if label:
                    cell.setString(label)


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

        print(
            f"       Created: {ODS_FILE}"
        )
    finally:
        if doc is not None:
            try:
                doc.close(True)
            except Exception:
                pass

        if desktop is not None:
            try:
                desktop.terminate()
            except Exception:
                pass

        if office_proc.poll() is None:
            office_proc.terminate()
            try:
                office_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                office_proc.kill()

        shutil.rmtree(profile_dir, ignore_errors=True)



if __name__ == "__main__":
    main()