import csv
import time
from pathlib import Path
import yfinance as yf

BASE_DIR = Path(__file__).resolve().parent.parent
TICKER_FILE = BASE_DIR / "data/tickers_combined.csv"
METADATA_FILE = BASE_DIR / "data/stock_metadata.csv"

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
            # Ensure Sector is parsed back as an integer if it exists
            if "Sector" in row and row["Sector"].isdigit():
                row["Sector"] = int(row["Sector"])
            metadata[row["Ticker"]] = row
    return metadata

def get_metadata(ticker):
    try:
        info = yf.Ticker(ticker).info
        raw_sector = info.get("sector", "")
        sector_code = sector_to_code(raw_sector)
        return {
            "Ticker": ticker,
            "Company": info.get("longName", info.get("shortName", "")),
            "Sector": sector_code
        }
    except Exception:
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
    for i, ticker in enumerate(missing, 1):
        print(f"\r Fetching {ticker} ({i}/{len(missing)})", end="")
        metadata[ticker] = get_metadata(ticker)
        time.sleep(0.25)
    print()
    save_metadata(metadata)
    print(f" Added {len(missing)} records")
    print(f" Saved {METADATA_FILE}")

if __name__ == "__main__":
    main()
