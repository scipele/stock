import yfinance as yf
import csv
import os
import time


INPUT_FILE = "../data/tickers_combined.csv"
OUTPUT_FILE = "../data/fundamentals.csv"


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

    try:

        stock = yf.Ticker(ticker)

        info = stock.info


        return {
            "Ticker": ticker,
            "Forward_PE": info.get("forwardPE", 0),
            "Trailing_PE": info.get("trailingPE", 0),
            "Market_Cap": info.get("marketCap", 0)
        }


    except Exception as e:

        print(f"{ticker}: FAILED {e}")

        return {
            "Ticker": ticker,
            "Forward_PE": 0,
            "Trailing_PE": 0,
            "Market_Cap": 0
        }



def main():

    tickers = load_tickers()
    print(f"Loaded {len(tickers)} tickers")
    rows = []

    for i, ticker in enumerate(tickers, 1):
        print(f"\rFetching {ticker} ({i}/{len(tickers)})",end="")
        data = get_fundamentals(ticker)
        rows.append(data)

        # avoid hammering Yahoo
        time.sleep(0.25)

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
    print("Created:")
    print(OUTPUT_FILE)

if __name__ == "__main__":
    main()