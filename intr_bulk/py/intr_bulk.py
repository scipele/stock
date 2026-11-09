#!/usr/bin/env python3
"""
Alpha Spread Intrinsic Value Bulk Calculator
Persistent Playwright browser session with anti-bot bypass.
"""

import csv
import re
import time
import random
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

BASE = Path("/home/dev/stock/intr_bulk")
INPUT_CSV = BASE / "input" / "inp_data.csv"
UPW_CSV = BASE / "input" / "upw.csv"
OUTPUT_CSV = BASE / "output" / "intr_bulk_out.csv"
FAILED_CSV = BASE / "output" / "intr_bulk_failed.csv"

PROFILE_DIR = BASE / "browser_profile"
SLEEP = 5
HEADLESS = False
EXCHANGES = ("nasdaq", "nyse")

def parse_pct(s):
    return float(s.strip().replace("%", "")) / 100.0

def load_credentials():
    if not UPW_CSV.exists():
        raise FileNotFoundError(f"Credential file not found at {UPW_CSV}")
    with open(UPW_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        row = next(reader, None)
        if row and "username" in row and "password" in row:
            return row["username"].strip(), row["password"].strip()
    raise ValueError(f"Could not parse valid credentials from {UPW_CSV}.")

def login_alpha_spread(page, username, password):
    print("Checking authentication status...")
    page.goto("https://alphaspread.com", wait_until="domcontentloaded")
    page.wait_for_timeout(2000)
    
    login_link = page.locator("a[href*='/sign-in'], a[href*='/login']").first
    if login_link.is_visible():
        print("Not logged in. Redirecting to sign-in page...")
        page.goto("https://alphaspread.comsign-in", wait_until="domcontentloaded")
        page.wait_for_timeout(2000)
        
        email_input = page.locator("input[type='email'], input[name='email'], #email").first
        password_input = page.locator("input[type='password'], input[name='password'], #password").first
        submit_btn = page.locator("button[type='submit']").first
        
        if email_input.is_visible() and password_input.is_visible():
            email_input.fill(username)
            page.wait_for_timeout(random.randint(400, 800))
            password_input.fill(password)
            page.wait_for_timeout(random.randint(500, 1000))
            submit_btn.click()
            print("Login credentials submitted.")
            page.wait_for_timeout(4000)
    else:
        print("Session already authenticated.")

def extract_from_text(text):
    text = text.replace("\n", " ").replace("\r", " ")
    patterns_iv = [
        r"intrinsic value.*?is\s+([\d,]+\.?\d*)\s*USD",
        r"Intrinsic Value[^$0-9]*\$?\s*([\d,]+\.?\d*)",
        r"Base Case[^$0-9]*\$?\s*([\d,]+\.?\d*)",
        r"\$\s*([\d,]+\.?\d*)\s*(?:USD)?\s*(?:Undervaluation|Overvaluation)",
    ]
    patterns_px = [
        r"current market price of\s+([\d,]+\.?\d*)\s*USD",
        r"Price\s*:\s*\$?\s*([\d,]+\.?\d*)",
        r"Last Price[^$0-9]*\$?\s*([\d,]+\.?\d*)",
        r"market price of\s+([\d,]+\.?\d*)",
    ]

    def extract(patterns):
        for pat in patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                try:
                    value = float(m.group(1).replace(",", ""))
                    if value > 1:
                        return value
                except ValueError:
                    pass
        return None

    return extract(patterns_iv), extract(patterns_px)

def is_cloudflare(text):
    markers = [
        "Performing security verification",
        "Checking your browser",
        "Verify you are human",
        "Attention Required",
        "Cloudflare",
    ]
    return any(marker.lower() in text.lower() for marker in markers)

def load_completed():
    completed = set()
    if OUTPUT_CSV.exists():
        with open(OUTPUT_CSV, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                completed.add(row["ticker"].upper())
    return completed

def save_result(result):
    fields = ["ticker", "pct_wt", "intrinsic_value", "current_price", "wt_intr", "wt_price"]
    write_header = not OUTPUT_CSV.exists() or OUTPUT_CSV.stat().st_size == 0
    with open(OUTPUT_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        if write_header:
            writer.writeheader()
        writer.writerow(result)
        f.flush()

def main():
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    completed = load_completed()
    
    try:
        username, password = load_credentials()
        print(f"Loaded credentials for user: {username}")
    except Exception as e:
        print(f"Failed to load credentials: {e}")
        return

    print("=" * 65)
    print("Intrinsic Value Bulk Calculator")
    print("=" * 65)
    print(f"\nPreviously completed tickers: {len(completed)}")

    failed = []

    with sync_playwright() as p:
        print("\nLaunching persistent Chrome instance...")
        
        # Anti-Bot Configuration flags
        context = p.chromium.launch_persistent_context(
            user_data_dir=PROFILE_DIR,
            headless=HEADLESS,
            channel="chrome",
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            args=[
                "--disable-blink-features=AutomationControlled",
                "--start-maximized"
            ]
        )
        
        page = context.pages[0] if context.pages else context.new_page()
        
        # Inject JavaScript script to completely remove the webdriver variable footprint
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        try:
            login_alpha_spread(page, username, password)
        except Exception as e:
            print(f"Warning during login phase: {e}")

        with open(INPUT_CSV, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                ticker = row["symbol"].strip().upper()
                if ticker in completed:
                    print(f"Skipping {ticker} - already completed")
                    continue

                pct_wt = parse_pct(row["pct_assets"])
                print(f"\nProcessing {ticker} ...")
                success = False

                # Handle multi-class symbols (e.g., BRK/B or BRK.B -> brk-b)
                clean_ticker_url = ticker.lower().replace("/", "-").replace(".", "-")

                for exch in EXCHANGES:
                    url = f"https://alphaspread.comsecurity/{exch}/{clean_ticker_url}/summary"
                    try:
                        # Emulate organic pacing
                        page.wait_for_timeout(random.randint(1000, 2500))
                        page.goto(url, wait_until="domcontentloaded", timeout=60000)
                        page.wait_for_timeout(4000)
                        text = page.locator("body").inner_text()

                        if is_cloudflare(text):
                            print(f"\n[{ticker}] Cloudflare verification detected.")
                            print("Complete any verification in the browser manually.")
                            input("Press ENTER to retry this page...")
                            page.reload(wait_until="domcontentloaded", timeout=60000)
                            page.wait_for_timeout(5000)
                            text = page.locator("body").inner_text()

                            if is_cloudflare(text):
                                print(f"[{ticker}] Still blocked. Moving on.")
                                break

                        iv, px = extract_from_text(text)
                        if iv is not None and px is not None:
                            print(f"[{ticker}] IV={iv:.2f} PX={px:.2f}")
                            result = {
                                "ticker": ticker,
                                "pct_wt": round(pct_wt, 6),
                                "intrinsic_value": round(iv, 2),
                                "current_price": round(px, 2),
                                "wt_intr": round(pct_wt * iv, 4),
                                "wt_price": round(pct_wt * px, 4),
                            }
                            save_result(result)
                            completed.add(ticker)
                            success = True
                            break
                        else:
                            print(f"[{ticker}] Bad parse on {exch} (IV={iv}, PX={px})")

                    except PlaywrightTimeout:
                        print(f"[{ticker}] Timeout on {exch}")
                    except Exception as e:
                        print(f"[{ticker}] Error: {e}")

                if not success:
                    print(f"[{ticker}] FAILED")
                    failed.append(ticker)

                # Add extra dynamic delays between distinct tickers
                time.sleep(SLEEP + random.uniform(1.0, 3.5))

        with open(FAILED_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["ticker"])
            writer.writerows([[t] for t in failed])

        print("\n" + "=" * 65)
        print("PROCESSING COMPLETE")
        print("=" * 65)

if __name__ == "__main__":
    main()
