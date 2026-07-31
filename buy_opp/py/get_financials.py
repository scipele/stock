import yfinance as yf
import csv
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed


INPUT_FILE = "../data/tickers_combined.csv"
OUTPUT_FILE = "../data/fundamentals.csv"

NUM_WORKERS = 4


def load_tickers():

    tickers = []

    with open(INPUT_FILE, "r") as f:

        reader = csv.reader(f)
        next(reader, None)   # Skip header row

        for row in reader:

            if not row:
                continue

            ticker = row[0].strip()

            if ticker.lower() == "ticker":
                continue

            if ticker:
                tickers.append(ticker)

    return tickers


def get_fundamentals(ticker):

    for attempt in range(3):

        try:

            stock = yf.Ticker(ticker)

            # Fast endpoint
            fast = stock.fast_info

            # Required for PE values
            info = stock.info

            return {
                "Ticker": ticker,
                "Forward_PE": info.get("forwardPE", 0),
                "Trailing_PE": info.get("trailingPE", 0),
                "Market_Cap": fast.get("market_cap", 0)
            }

        except Exception as e:

            if attempt < 2:
                time.sleep(2)
            else:
                print(f"\n{ticker}: FAILED {e}")

                return {
                    "Ticker": ticker,
                    "Forward_PE": 0,
                    "Trailing_PE": 0,
                    "Market_Cap": 0
                }


def main():

    tickers = load_tickers()

    print(f"   Loaded {len(tickers)} tickers")

    rows = []

    workers = min(NUM_WORKERS, len(tickers))

    with ThreadPoolExecutor(max_workers=workers) as executor:

        future_map = {
            executor.submit(get_fundamentals, ticker): ticker
            for ticker in tickers
        }

        completed = 0
        total = len(tickers)

        for future in as_completed(future_map):

            completed += 1

            print(
                f"\r   Progress: {completed}/{total}",
                end="",
                flush=True
            )

            rows.append(future.result())

    print()

    with open(
        OUTPUT_FILE,
        "w",
        newline=""
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=[
                "Ticker",
                "Forward_PE",
                "Trailing_PE",
                "Market_Cap"
            ]
        )

        writer.writeheader()
        writer.writerows(rows)

    print()
    print("   Created:")
    print(f"   {os.path.abspath(OUTPUT_FILE)}")


if __name__ == "__main__":
    main()