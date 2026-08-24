import os
import re
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
import yfinance as yf
import requests
from io import StringIO

# Resolve target destination strictly relative to the script location
OUTPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "buy_opp", "data"))


def ensure_output_dir():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        print(f"[+] Directory initialized: {OUTPUT_DIR}")


def save_csv(df, filename):
    ensure_output_dir()
    target_path = os.path.join(OUTPUT_DIR, filename)
    df.to_csv(target_path, index=False)
    print(f"[✓] Exported {len(df)} tickers successfully to: {target_path}\n")


def fetch_html_with_headers(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.9'
    }
    response = requests.get(url, headers=headers, timeout=15)
    response.raise_for_status()
    return response.text


def read_wikipedia_tables(url, match=None):
    """Try multiple read strategies because Wikipedia can return different HTML variants."""
    errors = []
    loaders = [
        lambda: pd.read_html(StringIO(fetch_html_with_headers(url)), match=match),
        lambda: pd.read_html(url, match=match),
        lambda: pd.read_html(StringIO(fetch_html_with_headers(f"{url}?printable=yes")), match=match),
    ]

    for loader in loaders:
        try:
            tables = loader()
            if tables:
                return tables
        except Exception as exc:
            errors.append(str(exc))

    raise ValueError(f"No tables found after fallback attempts. Details: {' | '.join(errors)}")


def find_ticker_column(df):
    normalized = []
    for col in df.columns:
        if isinstance(col, tuple):
            normalized.append(" ".join(str(part) for part in col if part is not None).strip())
        else:
            normalized.append(str(col).strip())

    for i, name in enumerate(normalized):
        low = name.lower()
        if "symbol" in low or "ticker" in low:
            return df.columns[i]
    return None


def extract_tickers_from_tables(tables, dot_to_dash=False):
    best_tickers = []
    for table in tables:
        col = find_ticker_column(table)
        if col is None:
            continue

        series = (
            table[col]
            .dropna()
            .astype(str)
            .str.replace(r"\[.*?\]", "", regex=True)
            .str.strip()
            .replace("", pd.NA)
            .dropna()
        )
        if dot_to_dash:
            series = series.str.replace('.', '-', regex=False)

        tickers = series.unique().tolist()
        if len(tickers) > len(best_tickers):
            best_tickers = tickers

    if not best_tickers:
        raise ValueError("Unable to locate a Symbol/Ticker column in parsed tables.")

    return best_tickers


def extract_dow_tickers_from_raw():
    # This list page is where Wikipedia now keeps the full DJIA constituents.
    raw_urls = [
        "https://en.wikipedia.org/wiki/List_of_Dow_Jones_Industrial_Average_companies?action=raw",
        "https://en.wikipedia.org/wiki/Dow_Jones_Industrial_Average?action=raw",
    ]
    pattern = re.compile(r"\{\{(?:NYSE|NASDAQ) link\|([A-Z.\-]+)\}\}")

    for raw_url in raw_urls:
        try:
            raw_text = fetch_html_with_headers(raw_url)
            tickers = pattern.findall(raw_text)
            if len(tickers) >= 25:
                return pd.Series(tickers).dropna().astype(str).str.strip().unique()
        except Exception:
            continue

    raise ValueError("Unable to extract Dow tickers from Wikipedia raw content.")


def update_dow():
    print("\n[1/4] Scraping Dow Jones Components...")
    url = "https://en.wikipedia.org/wiki/Dow_Jones_Industrial_Average"
    
    try:
        tables = read_wikipedia_tables(url, match="Company|Symbol|Ticker")

        target_df = None
        ticker_col = None
        for table in tables:
            col = find_ticker_column(table)
            if col is not None:
                target_df = table
                ticker_col = col
                break

        if target_df is None or ticker_col is None:
            tickers = extract_dow_tickers_from_raw()
        else:
            tickers = extract_tickers_from_tables([target_df])
        df_clean = pd.DataFrame({'Ticker': tickers})
        save_csv(df_clean, "tickers_dow.csv")
    except Exception as e:
        print(f"[-] Dow Update Failed: {e}")


def update_sp500():
    print("\n[2/4] Scraping S&P 500 Components...")
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    try:
        tables = read_wikipedia_tables(url, match="Symbol|Ticker|Security")
        tickers = extract_tickers_from_tables(tables)
        df_clean = pd.DataFrame({'Ticker': tickers})
        save_csv(df_clean, "tickers_sp_500.csv")
    except Exception as e:
        print(f"[-] S&P 500 Update Failed: {e}")


def fetch_russell_2000_raw():
    source_urls = [
        "https://bullishbears.com/russell-2000-stocks-list/",
        "https://en.wikipedia.org/wiki/Russell_2000_Index",
    ]

    errors = []
    for url in source_urls:
        try:
            html_content = fetch_html_with_headers(url)
            tables = pd.read_html(StringIO(html_content), match="Symbol|Ticker")
            tickers = extract_tickers_from_tables(tables, dot_to_dash=True)
            if len(tickers) >= 100:
                return tickers
        except Exception as exc:
            errors.append(f"{url}: {exc}")

    raise ValueError(f"Russell 2000 source parsing failed. Details: {' | '.join(errors)}")


def fetch_market_cap_from_yfinance(ticker):
    ticker_obj = yf.Ticker(ticker)

    cap = None
    try:
        fast_info = ticker_obj.fast_info
        cap = fast_info.get("market_cap") if fast_info else None
    except Exception:
        cap = None

    if not cap:
        try:
            info = ticker_obj.info
            cap = info.get("marketCap")
        except Exception:
            cap = None

    if not cap:
        raise ValueError("Market cap not found")

    return ticker, int(cap)


def update_russell_2000_all():
    print("\n[3/4] Indexing All Russell 2000 Tickers...")
    try:
        tickers = fetch_russell_2000_raw()
        df_clean = pd.DataFrame({'Ticker': tickers})
        save_csv(df_clean, "tickers_russel_2k.csv")
    except Exception as e:
        print(f"[-] Russell 2000 Processing Failed: {e}")


def update_russell_2000_top100():
    print("\n[4/4] Filtering Top 100 Russell 2000 Tickers by Market Cap...")
    try:
        tickers = fetch_russell_2000_raw()
        tickers = list(dict.fromkeys(t.strip().upper() for t in tickers if str(t).strip()))
        print(f"Polling {len(tickers)} tickers for market cap calculations. Please wait...")
        # Keep logs clean when Yahoo replies with quote-level errors for a symbol.
        logging.getLogger("yfinance").setLevel(logging.CRITICAL)

        market_caps = {}
        skipped = 0
        processed = 0

        max_workers = min(24, max(4, len(tickers)))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(fetch_market_cap_from_yfinance, ticker): ticker for ticker in tickers}

            for future in as_completed(futures):
                ticker = futures[future]
                try:
                    _, cap = future.result()
                    market_caps[ticker] = cap
                except Exception:
                    skipped += 1
                finally:
                    processed += 1

                if processed % 100 == 0 or processed == len(tickers):
                    print(
                        f"[i] Progress: {processed}/{len(tickers)} processed, {len(market_caps)} caps found, {skipped} skipped",
                        flush=True,
                    )

        sorted_tickers = sorted(market_caps.items(), key=lambda x: x[1], reverse=True)[:100]
        top_100 = [item[0] for item in sorted_tickers]

        if not top_100:
            raise ValueError("No market caps could be resolved from the Russell 2000 symbol set.")
        
        df_clean = pd.DataFrame({'Ticker': top_100})
        save_csv(df_clean, "tickers_russel_2k.csv")
        print(f"[i] Market cap resolved for {len(market_caps)} tickers; skipped {skipped} symbols.")
    except Exception as e:
        print(f"[-] Top 100 Selection Failed: {e}")


def main_menu():
    while True:
        print("=" * 55)
        print("             EQUITY INDEX COMPONENT TOOL")
        print("=" * 55)
        print(f"Target: {OUTPUT_DIR}")
        print("-" * 55)
        print("1.1. Update Dow Tickers          -> tickers_dow.csv")
        print("1.2. Update S&P 500              -> tickers_sp_500.csv")
        print("1.3. Update all Russell 2000     -> tickers_russel_2k.csv")
        print("1.4. Update top_100 Russell 2000  -> tickers_russel_2k.csv")
        print("2.   Run Comprehensive Upgrades  (All indices)")
        print("3.   Exit")
        print("=" * 55)
        
        choice = input("Action selection: ").strip()
        
        if choice == "1.1":
            update_dow()
        elif choice == "1.2":
            update_sp500()
        elif choice == "1.3":
            update_russell_2000_all()
        elif choice == "1.4":
            update_russell_2000_top100()
        elif choice == "2":
            update_dow()
            update_sp500()
            update_russell_2000_all()
            update_russell_2000_top100()
        elif choice == "3":
            print("System offline.")
            break
        else:
            print("[-] Standard menu input violation. Try again.\n")

if __name__ == "__main__":
    main_menu()
