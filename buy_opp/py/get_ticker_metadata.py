import csv
import time
from pathlib import Path
import yfinance as yf


BASE_DIR=Path(__file__).resolve().parent.parent
TICKER_FILE=BASE_DIR/"data/tickers_combined.csv"
METADATA_FILE=BASE_DIR/"data/stock_metadata.csv"


def load_tickers():
    tickers=[]
    with open(TICKER_FILE,"r") as f:
        for row in csv.DictReader(f):
            ticker=row["Ticker"].strip()
            if ticker:
                tickers.append(ticker)
    return tickers


def load_metadata():
    metadata={}
    if not METADATA_FILE.exists():
        return metadata

    with open(METADATA_FILE,"r") as f:
        for row in csv.DictReader(f):
            metadata[row["Ticker"]]=row

    return metadata


def get_metadata(ticker):
    try:
        info=yf.Ticker(ticker).info
        return {
            "Ticker":ticker,
            "Company":info.get("longName",info.get("shortName","")),
            "Sector":info.get("sector","")
        }
    except Exception:
        print(f"\nFAILED {ticker}")
        return {
            "Ticker":ticker,
            "Company":"",
            "Sector":""
        }


def save_metadata(metadata):
    rows=list(metadata.values())
    rows.sort(key=lambda x:x["Ticker"])

    with open(METADATA_FILE,"w",newline="") as f:
        writer=csv.DictWriter(
            f,
            fieldnames=["Ticker","Company","Sector"]
        )
        writer.writeheader()
        writer.writerows(rows)


def main():
    print("\n   Updating Stock Metadata")
    print("   =======================")

    tickers=load_tickers()
    metadata=load_metadata()

    missing=[t for t in tickers if t not in metadata]

    print(f"   Loaded tickers: {len(tickers)}")
    print(f"   Existing metadata: {len(metadata)}")
    print(f"   Missing metadata: {len(missing)}")

    if not missing:
        print("   Metadata already up to date")
        return

    for i,ticker in enumerate(missing,1):
        print(f"\r   Fetching {ticker} ({i}/{len(missing)})",end="")
        metadata[ticker]=get_metadata(ticker)
        time.sleep(0.25)

    print()

    save_metadata(metadata)

    print(f"   Added {len(missing)} records")
    print(f"   Saved {METADATA_FILE}")


if __name__=="__main__":
    main()