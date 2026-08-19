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
BUY_OPP_INDEX_DIR = "../../buy_opp/data"

MAX_HISTORY_YEARS = 5
MAX_WORKERS = 8          # adjust 6–12 depending on your connection
# ------------------------------------------------------------------

INDEX_BIT_MAP = {
    "SP": 1,
    "NQ": 2,
    "DJ": 4,
    "R2": 8,
    "M4": 16,
    "S6": 32,
    "TM": 64,
}

INDEX_SOURCE_FILES = {
    "SP": os.path.join(BUY_OPP_INDEX_DIR, "tickers_sp_500.csv"),
    "R2": os.path.join(BUY_OPP_INDEX_DIR, "tickers_russel_2k.csv"),
    "DJ": os.path.join(BUY_OPP_INDEX_DIR, "tickers_dow.csv"),
}


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


def normalize_ticker(ticker):
    return ticker.strip().replace("/", "-").upper()


def load_index_membership():
    membership = {}

    for short_code, path in INDEX_SOURCE_FILES.items():
        bit = INDEX_BIT_MAP[short_code]
        if not os.path.exists(path):
            continue

        with open(path, "r", newline="") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames or []
            ticker_col = None
            for candidate in fieldnames:
                if candidate and candidate.strip().lower() == "ticker":
                    ticker_col = candidate
                    break

            for row in reader:
                if ticker_col:
                    raw_ticker = row.get(ticker_col, "")
                elif fieldnames:
                    raw_ticker = row.get(fieldnames[0], "")
                else:
                    raw_ticker = ""

                ticker = normalize_ticker(raw_ticker)
                if ticker:
                    membership[ticker] = membership.get(ticker, 0) | bit

    return membership


def exchange_to_code(exchange_str, full_exchange_name=""):
    raw = f"{exchange_str} {full_exchange_name}".strip().lower()
    if not raw:
        return 4

    if any(token in raw for token in ("nasdaq", "nms", "ngm", "ncm", "nas")):
        return 1
    if any(token in raw for token in ("nyse american", "amex", "ase", "xase")):
        return 2
    if any(token in raw for token in ("cboe", "bats", "edgx")):
        return 3
    if any(token in raw for token in ("nyse", "nyq", "xnys")):
        return 0

    return 4


def load_tickers(path):
    tickers = []
    with open(path, "r", newline="") as f:
        reader = csv.reader(f)
        next(reader, None)
        for row in reader:
            if not row:
                continue
            t = normalize_ticker(row[0])
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


def get_data(ticker, index_membership):
    result = {
        "Ticker": ticker,
        "Company": "",
        "Sector": "",
        "Exch": 4,
        "Index": index_membership.get(ticker, 0),
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
        result["Exch"]              = exchange_to_code(info.get("exchange", ""), info.get("fullExchangeName", ""))
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
    index_membership = load_index_membership()
    print(f"      Loaded {len(tickers)} tickers")
    print(f"      Loaded index map entries: {len(index_membership)}")
    print(f"      Using {MAX_WORKERS} parallel workers\n")

    rows = []
    completed = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_ticker = {executor.submit(get_data, t, index_membership): t for t in tickers}

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
        "Ticker", "Company", "Sector", "Exch", "Index",
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