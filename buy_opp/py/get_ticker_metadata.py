import csv
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import yfinance as yf

BASE_DIR = Path(__file__).resolve().parent.parent
TICKER_FILE = BASE_DIR / "data/tickers_combined.csv"
METADATA_FILE = BASE_DIR / "data/stock_metadata.csv"

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
    "Sector": 10,  # placeholder if encountered
    "Technology": 11,
    "Utilities": 12
}

# Reverse mapping for writing reports later
SECTOR_NAME_MAP = {v: k for k, v in SECTOR_MAP.items()}

# Print lock to avoid terminal output overlapping from multiple threads
print_lock = threading.Lock()

def sector_to_code(sector_str):
    """Convert sector string to numeric code, default to 0 if unknown."""
    cleaned = sector_str.strip()
    return SECTOR_MAP.get(cleaned, 0)

def load_tickers():
    tickers = set()
    with open(TICKER_FILE, "r") as f:
        for row in csv.DictReader(f):
            ticker = row["Ticker"].strip()
            if ticker:
                normalized_ticker = ticker.replace("/", "-")
                tickers.add(normalized_ticker)
    return list(tickers)

def load_metadata():
    metadata = {}
    if not METADATA_FILE.exists():
        return metadata
    with open(METADATA_FILE, "r") as f:
        for row in csv.DictReader(f):
            if "Sector" in row and row["Sector"].isdigit():
                row["Sector"] = int(row["Sector"])
            metadata[row["Ticker"]] = row
    return metadata

def get_metadata(ticker):
    try:
        # yfinance can be noisy or occasionally hit rate limits; brief sleep acts as a jitter
        info = yf.Ticker(ticker).info
        raw_sector = info.get("sector", "")
        sector_code = sector_to_code(raw_sector)
        return {
            "Ticker": ticker,
            "Company": info.get("longName", info.get("shortName", "")),
            "Sector": sector_code
        }
    except Exception:
        with print_lock:
            print(f"\nFAILED {ticker}")
        return {
            "Ticker": ticker,
            "Company": "",
            "Sector": 0
        }

def save_metadata(metadata):
    rows = list(metadata.values())
    rows.sort(key=lambda x: x["Ticker"])
    with open(METADATA_FILE, "w", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=["Ticker", "Company", "Sector"]
        )
        writer.writeheader()
        writer.writerows(rows)

def main():
    print("\n Updating Stock Metadata")
    print(" =======================")
    tickers = load_tickers()
    metadata = load_metadata()
    missing = [t for t in tickers if t not in metadata]
    
    print(f" Loaded unique tickers: {len(tickers)}")
    print(f" Existing metadata: {len(metadata)}")
    print(f" Missing metadata: {len(missing)}")
    
    if not missing:
        print(" Metadata already up to date")
        return

    print(f" Starting download with {NUM_WORKERS} concurrent workers...\n")
    
    completed = 0
    # Use ThreadPoolExecutor for high-performance concurrent I/O requests
    with ThreadPoolExecutor(max_workers=NUM_WORKERS) as executor:
        # Submit all tasks to the queue immediately
        future_to_ticker = {executor.submit(get_metadata, ticker): ticker for ticker in missing}
        
        # Process results exactly as they complete, regardless of submission order
        for future in as_completed(future_to_ticker):
            ticker = future_to_ticker[future]
            try:
                result = future.result()
                metadata[ticker] = result
            except Exception as exc:
                with print_lock:
                    print(f"\n{ticker} generated an unexpected exception: {exc}")
                metadata[ticker] = {"Ticker": ticker, "Company": "", "Sector": 0}
            
            completed += 1
            with print_lock:
                print(f"\r Progress ({completed}/{len(missing)}) - Handled {ticker:<6}", end="", flush=True)
            
            # Subtle delay to prevent hammering Yahoo Finance API too aggressively
            time.sleep(0.05)

    print("\n")
    save_metadata(metadata)
    print(f" Added {len(missing)} records")
    print(f" Saved {METADATA_FILE}")

if __name__ == "__main__":
    main()
