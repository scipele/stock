#!/usr/bin/env python3
"""
get_intrinsic_data.py
--------------------
Gathers the data needed for intrinsic-value calculations.
Python only does the downloading & light cleaning.
All heavy number-crunching (CAGR, DCF, ranking) will be done in C++.
"""

import yfinance as yf
import csv
import os
import time
import math
from datetime import datetime

# ------------------------------------------------------------------
# Configuration
# ------------------------------------------------------------------
INPUT_FILE  = "../data/tickers_combined.csv"
OUTPUT_FILE = "../data/fundamentals_intrinsic.csv"

# How many years of annual FCF / Revenue we try to capture
MAX_HISTORY_YEARS = 5

# Polite delay between Yahoo requests
SLEEP_SECONDS = 0.30


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------
def safe_float(value, default=0.0):
    """Convert to float, treating None / NaN / empty as default."""
    try:
        if value is None:
            return default
        f = float(value)
        if math.isnan(f) or math.isinf(f):
            return default
        return f
    except (TypeError, ValueError):
        return default


def load_tickers(path):
    tickers = []
    with open(path, "r", newline="") as f:
        reader = csv.reader(f)
        next(reader, None)  # skip header
        for row in reader:
            if not row:
                continue
            t = row[0].strip()
            if t and t.lower() != "ticker":
                tickers.append(t)
    return tickers


def extract_history(df, item_name, max_years=MAX_HISTORY_YEARS):
    """
    From a yfinance financial statement DataFrame, pull the last
    `max_years` values for a given row label (e.g. 'Free Cash Flow').
    Returns a list newest → oldest, padded with 0.0 if missing.
    """
    values = [0.0] * max_years
    if df is None or df.empty:
        return values

    # yfinance uses slightly different labels over time
    possible_names = [
        item_name,
        item_name.replace(" ", ""),
        item_name.title(),
    ]

    row = None
    for name in possible_names:
        if name in df.index:
            row = df.loc[name]
            break

    if row is None:
        return values

    # Columns are timestamps; sort newest first
    row = row.sort_index(ascending=False)

    for i, val in enumerate(row.values):
        if i >= max_years:
            break
        values[i] = safe_float(val)

    return values


# ------------------------------------------------------------------
# Main data pull for one ticker
# ------------------------------------------------------------------
def get_data(ticker):
    result = {
        "Ticker": ticker,
        "Company": "",
        "Sector": "",
        "Price": 0.0,
        "SharesOutstanding": 0.0,
        "MarketCap": 0.0,
        "TotalDebt": 0.0,
        "TotalCash": 0.0,
        "Beta": 0.0,
        "ForwardPE": 0.0,
        "TrailingPE": 0.0,
        "FCF_TTM": 0.0,          # trailing twelve months if available
        # Historical Free Cash Flow (newest → oldest)
        "FCF_Y1": 0.0,
        "FCF_Y2": 0.0,
        "FCF_Y3": 0.0,
        "FCF_Y4": 0.0,
        "FCF_Y5": 0.0,
        # Historical Revenue (newest → oldest) – useful fallback
        "Rev_Y1": 0.0,
        "Rev_Y2": 0.0,
        "Rev_Y3": 0.0,
        "Rev_Y4": 0.0,
        "Rev_Y5": 0.0,
        "DataQuality": "ok",     # simple flag for C++ later
        "FetchedAt": datetime.now().isoformat(timespec="seconds"),
    }

    try:
        stock = yf.Ticker(ticker)
        info  = stock.info or {}

        # --- Basic info ---
        result["Company"]          = info.get("longName") or info.get("shortName") or ""
        result["Sector"]           = info.get("sector") or ""
        result["Price"]            = safe_float(info.get("currentPrice") or info.get("regularMarketPrice"))
        result["SharesOutstanding"]= safe_float(info.get("sharesOutstanding"))
        result["MarketCap"]        = safe_float(info.get("marketCap"))
        result["TotalDebt"]        = safe_float(info.get("totalDebt"))
        result["TotalCash"]        = safe_float(info.get("totalCash"))
        result["Beta"]             = safe_float(info.get("beta"))
        result["ForwardPE"]        = safe_float(info.get("forwardPE"))
        result["TrailingPE"]       = safe_float(info.get("trailingPE"))
        result["FCF_TTM"]          = safe_float(info.get("freeCashflow"))

        # --- Annual cash-flow statement (FCF) ---
        try:
            cashflow = stock.cashflow          # annual
            fcf_hist = extract_history(cashflow, "Free Cash Flow")
            result["FCF_Y1"] = fcf_hist[0]
            result["FCF_Y2"] = fcf_hist[1]
            result["FCF_Y3"] = fcf_hist[2]
            result["FCF_Y4"] = fcf_hist[3]
            result["FCF_Y5"] = fcf_hist[4]
        except Exception:
            result["DataQuality"] = "no_cashflow"

        # --- Annual income statement (Revenue) as fallback ---
        try:
            financials = stock.financials
            rev_hist = extract_history(financials, "Total Revenue")
            result["Rev_Y1"] = rev_hist[0]
            result["Rev_Y2"] = rev_hist[1]
            result["Rev_Y3"] = rev_hist[2]
            result["Rev_Y4"] = rev_hist[3]
            result["Rev_Y5"] = rev_hist[4]
        except Exception:
            if result["DataQuality"] == "ok":
                result["DataQuality"] = "no_revenue"

        # Very basic quality flag
        if result["Price"] <= 0 or result["SharesOutstanding"] <= 0:
            result["DataQuality"] = "missing_price_or_shares"

    except Exception as e:
        print(f"\n   {ticker}: FAILED – {e}")
        result["DataQuality"] = "fetch_failed"

    return result


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------
def main():
    print("=== Intrinsic Value – Data Gatherer ===")
    tickers = load_tickers(INPUT_FILE)
    print(f"Loaded {len(tickers)} tickers from {INPUT_FILE}")

    rows = []
    for i, ticker in enumerate(tickers, 1):
        print(f"\r   [{i:3d}/{len(tickers)}] {ticker:<8}", end="", flush=True)
        rows.append(get_data(ticker))
        time.sleep(SLEEP_SECONDS)

    print("\n")

    # Column order – keep it stable so C++ can rely on positions if desired
    fieldnames = [
        "Ticker", "Company", "Sector",
        "Price", "SharesOutstanding", "MarketCap",
        "TotalDebt", "TotalCash", "Beta",
        "ForwardPE", "TrailingPE",
        "FCF_TTM",
        "FCF_Y1", "FCF_Y2", "FCF_Y3", "FCF_Y4", "FCF_Y5",
        "Rev_Y1", "Rev_Y2", "Rev_Y3", "Rev_Y4", "Rev_Y5",
        "DataQuality", "FetchedAt",
    ]

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

    with open(OUTPUT_FILE, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Created: {os.path.abspath(OUTPUT_FILE)}")
    print(f"Rows written: {len(rows)}")


if __name__ == "__main__":
    main()