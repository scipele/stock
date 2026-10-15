import csv
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import yfinance as yf
import requests

# 1. FILE PATH CONSTRAINTS (Keep exactly as your system expects)
INPUT_FILE = "../data/tickers_combined.csv"
OUTPUT_FILE = "../data/fundamentals.csv"
NUM_WORKERS = 1  # Crucial on Ubuntu: Keep at 1 to prevent immediate IP-bans

# 2. SESSION SETUP (Placing this globally ensures all requests use the custom browser mask)
session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
})

def load_tickers():
    tickers = []
    with open(INPUT_FILE, 'r') as f:
        reader = csv.reader(f)
        next(reader, None)  # Skip header row
        for row in reader:
            if not row: continue
            ticker = row[0].strip()
            if ticker.lower() == ticker: continue  # Skip lowercase flags
            if ticker: tickers.append(ticker)
    return tickers

def get_fundamentals(ticker):
    # This loop manages retry attempts if Yahoo gives us a 429 error
    for attempt in range(3):
        try:
            # ---> PLACED HERE: Passing the browser session into the Ticker object
            stock = yf.Ticker(ticker, session=session)
            
            fast = stock.fast_info
            info = stock.info  # Heavy scraping action happens here
            
            # ---> PLACED HERE: A defensive 2-second sleep so Ubuntu doesn't rush Yahoo's API
            time.sleep(2.0) 
            
            return {
                "Ticker": ticker,
                "Forward_PE": info.get("forwardPE", 0),
                "Trailing_PE": info.get("trailingPE", 0),
                "Market_Cap": fast.get("market_cap", 0)
            }
        except Exception as e:
            # Detect rate-limiting dynamically and cool down aggressively
            if "429" in str(e) or "Too Many Requests" in str(e):
                wait_time = (attempt + 1) * 15
                print(f"\n[Rate Limited] Cooling down for {wait_time}s on {ticker}...")
                time.sleep(wait_time)
            elif attempt < 2:
                time.sleep(2)
            else:
                print(f"\n{ticker}: FAILED {e}")
                
    return {"Ticker": ticker, "Forward_PE": 0, "Trailing_PE": 0, "Market_Cap": 0}

def main():
    tickers = load_tickers()
    print(f"Loaded {len(tickers)} tickers")
    rows = []
    
    workers = min(NUM_WORKERS, len(tickers))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_map = {executor.submit(get_fundamentals, ticker): ticker for ticker in tickers}
        completed = 0
        total = len(tickers)
        
        for future in as_completed(future_map):
            completed += 1
            print(f"\rProgress: {completed}/{total}", end="", flush=True)
            rows.append(future.result())
    print()

    # Save to your output CSV path
    with open(OUTPUT_FILE, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=["Ticker", "Forward_PE", "Trailing_PE", "Market_Cap"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nCreated:\n{os.path.abspath(OUTPUT_FILE)}")

if __name__ == "__main__":
    main()
