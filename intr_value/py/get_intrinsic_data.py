#!/usr/bin/env python3
"""
get_intrinsic_data.py  –  concurrent version
"""

import yfinance as yf
import csv
import os
import time
import math
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# ------------------------------------------------------------------
# Configuration
# ------------------------------------------------------------------
INPUT_FILE  = "../data/tickers_combined.csv"
OUTPUT_FILE = "../data/fundamentals_intrinsic.csv"

MAX_HISTORY_YEARS = 5
MAX_WORKERS = 8          # adjust 6–12 depending on your connection
# ------------------------------------------------------------------


def safe_float(value, default=0.0):
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
        next(reader, None)
        for row in reader:
            if not row:
                continue
            t = row[0].strip()
            if t and t.lower() != "ticker":
                tickers.append(t)
    return tickers


def extract_history(df, item_name, max_years=MAX_HISTORY_YEARS):
    values = [0.0] * max_years
    if df is None or df.empty:
        return values

    possible_names = [item_name, item_name.replace(" ", ""), item_name.title()]
    row = None
    for name in possible_names:
        if name in df.index:
            row = df.loc[name]
            break
    if row is None:
        return values

    row = row.sort_index(ascending=False)
    for i, val in enumerate(row.values):
        if i >= max_years:
            break
        values[i] = safe_float(val)
    return values


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
        "FCF_TTM": 0.0,
        "FCF_Y1": 0.0, "FCF_Y2": 0.0, "FCF_Y3": 0.0, "FCF_Y4": 0.0, "FCF_Y5": 0.0,
        "Rev_Y1": 0.0, "Rev_Y2": 0.0, "Rev_Y3": 0.0, "Rev_Y4": 0.0, "Rev_Y5": 0.0,
        "DataQuality": "ok",
        "FetchedAt": datetime.now().isoformat(timespec="seconds"),
    }

    try:
        stock = yf.Ticker(ticker)
        info  = stock.info or {}

        result["Company"]           = info.get("longName") or info.get("shortName") or ""
        result["Sector"]            = info.get("sector") or ""
        result["Price"]             = safe_float(info.get("currentPrice") or info.get("regularMarketPrice"))
        result["SharesOutstanding"] = safe_float(info.get("sharesOutstanding"))
        result["MarketCap"]         = safe_float(info.get("marketCap"))
        result["TotalDebt"]         = safe_float(info.get("totalDebt"))
        result["TotalCash"]         = safe_float(info.get("totalCash"))
        result["Beta"]              = safe_float(info.get("beta"))
        result["ForwardPE"]         = safe_float(info.get("forwardPE"))
        result["TrailingPE"]        = safe_float(info.get("trailingPE"))
        result["FCF_TTM"]           = safe_float(info.get("freeCashflow"))

        try:
            cashflow = stock.cashflow
            fcf_hist = extract_history(cashflow, "Free Cash Flow")
            result["FCF_Y1"] = fcf_hist[0]
            result["FCF_Y2"] = fcf_hist[1]
            result["FCF_Y3"] = fcf_hist[2]
            result["FCF_Y4"] = fcf_hist[3]
            result["FCF_Y5"] = fcf_hist[4]
        except Exception:
            result["DataQuality"] = "no_cashflow"

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

        if result["Price"] <= 0 or result["SharesOutstanding"] <= 0:
            result["DataQuality"] = "missing_price_or_shares"

    except Exception as e:
        result["DataQuality"] = "fetch_failed"

    return result


def main():
    print("      === Intrinsic Value – Data Gatherer (concurrent) ===")
    tickers = load_tickers(INPUT_FILE)
    print(f"      Loaded {len(tickers)} tickers")
    print(f"      Using {MAX_WORKERS} parallel workers\n")

    rows = []
    completed = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_ticker = {executor.submit(get_data, t): t for t in tickers}

        for future in as_completed(future_to_ticker):
            ticker = future_to_ticker[future]
            completed += 1
            try:
                data = future.result()
                rows.append(data)
            except Exception as e:
                print(f"\n      {ticker}: exception {e}")
                rows.append({
                    "Ticker": ticker,
                    "DataQuality": "fetch_failed",
                    "FetchedAt": datetime.now().isoformat(timespec="seconds"),
                })

            print(f"\r      [{completed:3d}/{len(tickers)}] last: {ticker:<8}", end="", flush=True)

    print("\n")

    # Keep original ticker order roughly (optional)
    ticker_order = {t: i for i, t in enumerate(tickers)}
    rows.sort(key=lambda r: ticker_order.get(r["Ticker"], 9999))

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
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    print(f"      Created: {os.path.abspath(OUTPUT_FILE)}")
    print(f"      Rows written: {len(rows)}")


if __name__ == "__main__":
    main()