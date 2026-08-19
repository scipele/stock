import csv
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import yfinance as yf

BASE_DIR = Path(__file__).resolve().parent.parent
TICKER_FILE = BASE_DIR / "data/tickers_combined.csv"
METADATA_FILE = BASE_DIR / "data/stock_metadata.csv"
SP500_FILE = BASE_DIR / "data/tickers_sp_500.csv"
RUSSELL2K_FILE = BASE_DIR / "data/tickers_russel_2k.csv"
DOW_FILE = BASE_DIR / "data/tickers_dow.csv"

NUM_WORKERS = 1

# Sector-to-Number mapping dictionary
SECTOR_MAP = {
    "Basic Materials": 1,
    "Communication Services": 2,
    "Consumer Cyclical": 3,
    "Consumer Defensive": 4,
    "Energy": 5,
    "Financial Services": 6,
    "Healthcare": 7,
    "Industrials": 8,
    "Real Estate": 9,
    "Technology": 10,
    "Utilities": 11
}

# Reverse mapping for writing reports later
SECTOR_NAME_MAP = {v: k for k, v in SECTOR_MAP.items()}

# Exchange integer codes for storage.
# 0=NYSE, 1=Nasdaq, 2=NYSE American/AMEX, 3=Cboe, 4=Other.
EXCHANGE_CODE_MAP = {
    "N": 0,
    "Q": 1,
    "A": 2,
    "C": 3,
    "O": 4,
}

# Index bitmask values.
INDEX_BIT_MAP = {
    "SP": 1,   # S&P 500
    "NQ": 2,   # Nasdaq-100
    "DJ": 4,   # Dow Jones Industrial Average
    "R2": 8,   # Russell 2000
    "M4": 16,  # S&P MidCap 400
    "S6": 32,  # S&P SmallCap 600
    "TM": 64,  # CRSP U.S. Total Market
}

INDEX_SOURCE_FILES = {
    "SP": SP500_FILE,
    "R2": RUSSELL2K_FILE,
    "DJ": DOW_FILE,
}

# String hints used to infer index membership when provider metadata includes index labels.
INDEX_HINTS = {
    "s&p 500": INDEX_BIT_MAP["SP"],
    "sp500": INDEX_BIT_MAP["SP"],
    "nasdaq-100": INDEX_BIT_MAP["NQ"],
    "nasdaq 100": INDEX_BIT_MAP["NQ"],
    "ndx": INDEX_BIT_MAP["NQ"],
    "dow jones industrial average": INDEX_BIT_MAP["DJ"],
    "djia": INDEX_BIT_MAP["DJ"],
    "russell 2000": INDEX_BIT_MAP["R2"],
    "s&p midcap 400": INDEX_BIT_MAP["M4"],
    "s&p 400": INDEX_BIT_MAP["M4"],
    "s&p smallcap 600": INDEX_BIT_MAP["S6"],
    "s&p 600": INDEX_BIT_MAP["S6"],
    "crsp u.s. total market": INDEX_BIT_MAP["TM"],
    "crsp us total market": INDEX_BIT_MAP["TM"],
}

# Print lock to avoid terminal output overlapping from multiple threads
print_lock = threading.Lock()

def sector_to_code(sector_str):
    """Convert sector string to numeric code, default to 0 if unknown."""
    cleaned = sector_str.strip()
    return SECTOR_MAP.get(cleaned, 0)


def normalize_ticker(ticker):
    return ticker.strip().replace("/", "-").upper()


def _parse_int(value, default):
    if value is None:
        return default
    cleaned = str(value).strip()
    if cleaned == "":
        return default
    if cleaned.isdigit():
        return int(cleaned)
    return default


def _parse_exchange_value(value):
    if value is None:
        return None
    cleaned = str(value).strip()
    if cleaned == "":
        return None
    if cleaned.isdigit():
        parsed = int(cleaned)
        if parsed in EXCHANGE_CODE_MAP.values():
            return parsed
    letter = cleaned.upper()
    if letter in EXCHANGE_CODE_MAP:
        return EXCHANGE_CODE_MAP[letter]
    return None


def exchange_to_code(exchange_str, full_exchange_name=""):
    """Convert exchange identifiers to integer codes used in CSV storage."""
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


def index_to_bitmask(info):
    """Infer index membership bitmask from provider metadata when available."""
    if not isinstance(info, dict):
        return 0

    candidates = []
    for key in ("index", "indexes", "indexName", "benchmark", "benchmarkName"):
        value = info.get(key)
        if isinstance(value, str):
            candidates.append(value.lower())
        elif isinstance(value, list):
            candidates.extend(str(v).lower() for v in value if v)

    combined = " | ".join(candidates)
    if not combined:
        return 0

    bitmask = 0
    for hint, bit in INDEX_HINTS.items():
        if hint in combined:
            bitmask |= bit
    return bitmask

def load_tickers():
    tickers = set()
    with open(TICKER_FILE, "r") as f:
        for row in csv.DictReader(f):
            ticker = normalize_ticker(row["Ticker"])
            if ticker:
                tickers.add(ticker)
    return list(tickers)


def load_index_membership():
    """Load index memberships as a ticker->bitmask map for fast O(1) lookup."""
    membership = {}

    for short_code, file_path in INDEX_SOURCE_FILES.items():
        bit = INDEX_BIT_MAP[short_code]
        if not file_path.exists():
            continue

        with open(file_path, "r") as f:
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

def load_metadata():
    metadata = {}
    if not METADATA_FILE.exists():
        return metadata
    with open(METADATA_FILE, "r") as f:
        for row in csv.DictReader(f):
            ticker = normalize_ticker(row.get("Ticker", ""))
            if not ticker:
                continue

            metadata[ticker] = {
                "Ticker": ticker,
                "Company": row.get("Company", ""),
                "Sector": _parse_int(row.get("Sector"), 0),
                # Keep None when missing so we can backfill from yfinance.
                "Exch": _parse_exchange_value(row.get("Exch")),
                "Index": _parse_int(row.get("Index"), None),
            }
    return metadata

def get_metadata(ticker, local_index_bitmask=0):
    try:
        # yfinance can be noisy or occasionally hit rate limits; brief sleep acts as a jitter
        info = yf.Ticker(ticker).info
        raw_sector = info.get("sector", "")
        raw_exchange = info.get("exchange", "")
        raw_exchange_name = info.get("fullExchangeName", "")
        sector_code = sector_to_code(raw_sector)
        exchange_code = exchange_to_code(raw_exchange, raw_exchange_name)
        index_bitmask = local_index_bitmask | index_to_bitmask(info)
        return {
            "Ticker": ticker,
            "Company": info.get("longName", info.get("shortName", "")),
            "Sector": sector_code,
            "Exch": exchange_code,
            "Index": index_bitmask,
        }
    except Exception:
        with print_lock:
            print(f"\n    FAILED {ticker}")
        return {
            "Ticker": ticker,
            "Company": "",
            "Sector": 0,
            "Exch": 4,
            "Index": 0,
        }

def save_metadata(metadata):
    rows = list(metadata.values())
    rows.sort(key=lambda x: x["Ticker"])
    with open(METADATA_FILE, "w", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=["Ticker", "Company", "Sector", "Exch", "Index"]
        )
        writer.writeheader()
        writer.writerows(rows)


def needs_metadata_refresh(row):
    # Backfill rows from prior schema that do not have Exch yet.
    return row.get("Exch") is None

def main():
    print("\n       Updating Stock Metadata")
    print("       =======================")
    tickers = load_tickers()
    index_membership = load_index_membership()
    metadata = load_metadata()

    # Fill Index from local membership map without extra network calls.
    for ticker, row in metadata.items():
        row["Index"] = index_membership.get(ticker, 0)

    missing = [
        t for t in tickers
        if t not in metadata or needs_metadata_refresh(metadata[t])
    ]
    
    print(f"       Loaded unique tickers: {len(tickers)}")
    print(f"       Loaded index map entries: {len(index_membership)}")
    print(f"       Existing metadata: {len(metadata)}")
    print(f"       Missing metadata: {len(missing)}")
    
    if not missing:
        print("       Metadata already up to date")
        return

    print(f"       Starting download with {NUM_WORKERS} concurrent workers...\n")
    
    completed = 0
    # Use ThreadPoolExecutor for high-performance concurrent I/O requests
    with ThreadPoolExecutor(max_workers=NUM_WORKERS) as executor:
        # Submit all tasks to the queue immediately
        future_to_ticker = {
            executor.submit(
                get_metadata,
                ticker,
                index_membership.get(ticker, 0),
            ): ticker
            for ticker in missing
        }
        
        # Process results exactly as they complete, regardless of submission order
        for future in as_completed(future_to_ticker):
            ticker = future_to_ticker[future]
            try:
                result = future.result()
                metadata[ticker] = result
            except Exception as exc:
                with print_lock:
                    print(f"\n{ticker} generated an unexpected exception: {exc}")
                metadata[ticker] = {
                    "Ticker": ticker,
                    "Company": "",
                    "Sector": 0,
                    "Exch": 4,
                    "Index": 0,
                }
            
            completed += 1
            with print_lock:
                print(f"\r       Progress ({completed}/{len(missing)}) - Handled {ticker:<6}", end="", flush=True)
            
            # Subtle delay to prevent hammering Yahoo Finance API too aggressively
            time.sleep(0.05)

    print("\n")
    save_metadata(metadata)
    print(f"       Added {len(missing)} records")
    print(f"       Saved {METADATA_FILE}")

if __name__ == "__main__":
    main()
