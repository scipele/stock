from pathlib import Path
from datetime import timedelta
import pandas as pd
import yfinance as yf
import io
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import os

# ==============================================================================
# 1. PATHS & CONFIGURATION
# ==============================================================================

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_FILE = OUTPUT_DIR / "crash_history_analysis.xlsx"

PRE_CRASH_WEEKS = 52       # Weeks before Week 0 (e.g., 52 = 1 year)
FALLBACK_POST_WEEKS = 156  # Used if recovery_date is set to None

# Format: "Crash_ID": { metadata... }
# peak_date = Friday close of Week 0
# recovery_date = Friday close when S&P 500 reclaimed peak (or None to use FALLBACK_POST_WEEKS)
CRASH_EVENTS = {
    "1973_STAG": {
        "short_name": "1973-74 Stagflation",
        "peak_date": "1973-01-12",
        "trough_date": "1974-10-04",
        "recovery_date": "1980-07-18",
        "catalysts": "Bretton Woods collapse, Nifty Fifty bubble, OPEC oil embargo, Watergate, double-digit CPI.",
        "fed_action": "Hiked FFR from ~5.7% to 13% into a recession to fight inflation, then cut in late 1974."
    },
    "1980_VOLC": {
        "short_name": "1980 Volcker Shock",
        "peak_date": "1980-02-15",
        "trough_date": "1980-03-28",
        "recovery_date": "1980-07-18",
        "catalysts": "Iranian oil shock, 14.8% CPI, Hunt Brothers silver collapse, sudden credit controls.",
        "fed_action": "Volcker hiked FFR to ~17.6% + credit controls, then briefly slashed to 9% in summer 1980."
    },
    "1981_RECS": {
        "short_name": "1981-82 Double-Dip Bear",
        "peak_date": "1980-11-28",
        "trough_date": "1982-08-13",
        "recovery_date": "1982-11-05",
        "catalysts": "Second leg of double-dip recession, stubborn inflation, energy price slump, LatAm debt crisis.",
        "fed_action": "Pushed FFR back to ~19-20% in mid-1981 and held tight until Aug 1982 pivot."
    },
    "1987_BLKM": {
        "short_name": "1987 Black Monday",
        "peak_date": "1987-08-21",
        "trough_date": "1987-12-04",
        "recovery_date": "1989-07-28",
        "catalysts": "Overvaluation (+44% YTD), widening deficits, rising yields, automated portfolio insurance.",
        "fed_action": "Greenspan pledged immediate liquidity post-crash and cut rates; no recession occurred."
    },
    "2000_DOTC": {
        "short_name": "2000 Dot-Com Bust",
        "peak_date": "2000-03-24",
        "trough_date": "2002-10-11",
        "recovery_date": "2007-05-25",
        "catalysts": "Internet/telecom bubble, Y2K capex overhang, 9/11 attacks, Enron/WorldCom accounting frauds.",
        "fed_action": "Hiked to 6.5% in May 2000; cut aggressively from Jan 2001 down to 1.0% by 2003."
    },
    "2008_GFC": {
        "short_name": "2008 Financial Crisis",
        "peak_date": "2007-10-12",
        "trough_date": "2009-03-06",
        "recovery_date": "2013-03-29",
        "catalysts": "Subprime mortgage defaults, bank over-leverage, Bear Stearns & Lehman failures, credit freeze.",
        "fed_action": "Slashed FFR to 0.00-0.25% (ZIRP), launched QE1, TARP bailouts, and emergency swap lines."
    },
    "2020_COVD": {
        "short_name": "2020 COVID Crash",
        "peak_date": "2020-02-21",
        "trough_date": "2020-03-20",
        "recovery_date": "2020-08-21",
        "catalysts": "Global pandemic lockdowns, sudden economic halt, supply freeze, Russia-Saudi oil price war.",
        "fed_action": "Emergency cuts to 0% in two weeks, unlimited QE, corporate bond buying, massive fiscal aid."
    },
    "2022_INFL": {
        "short_name": "2022 Inflation Bear",
        "peak_date": "2021-12-31",
        "trough_date": "2022-10-14",
        "recovery_date": "2024-01-19",
        "catalysts": "Post-COVID inflation (9.1% CPI), Russia-Ukraine energy shock, simultaneous stock & bond selloff.",
        "fed_action": "Hiked FFR by 525 bps in 16 months + Quantitative Tightening (QT)."
    }
}

# ==============================================================================
# 2. DATA FETCHING FUNCTIONS (FRED & YAHOO FINANCE)
# ==============================================================================

def fetch_fred_series(series_id: str, col_name: str, api_key: str | None = None) -> pd.Series:
    """
    Downloads a series from the official FRED API.
    Falls back to a longer timeout and clearer errors.
    """
    if api_key is None:
        api_key = os.environ.get("FRED_API_KEY")
    if not api_key:
        raise ValueError(
            "FRED_API_KEY is required. "
            "Get a free key at https://fred.stlouisfed.org/docs/api/api_key.html "
            "and either pass it or set the FRED_API_KEY environment variable."
        )

    print(f"Fetching FRED: {series_id} ({col_name})...")

    url = "https://api.stlouisfed.org/fred/series/observations"
    params = {
        "series_id": series_id,
        "api_key": api_key,
        "file_type": "json",
        "observation_start": "1970-01-01",
        "sort_order": "asc",
    }

    session = requests.Session()
    retries = Retry(
        total=4,
        backoff_factor=1.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
    )
    session.mount("https://", HTTPAdapter(max_retries=retries))

    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; crash-history-analysis/1.0)"
    }

    try:
        resp = session.get(url, params=params, headers=headers, timeout=45)
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"FRED request failed for {series_id}: {e}") from e

    data = resp.json()
    observations = data.get("observations", [])
    if not observations:
        raise RuntimeError(f"No observations returned for series {series_id}")

    # Build Series
    dates = []
    values = []
    for obs in observations:
        val = obs["value"]
        if val == ".":          # FRED uses "." for missing
            continue
        dates.append(pd.to_datetime(obs["date"]))
        values.append(float(val))

    s = pd.Series(values, index=dates, name=col_name)
    s.index.name = None
    return s


def fetch_yahoo_series(ticker: str, col_name: str, start: str = "1970-01-01") -> pd.Series:
    """Downloads daily close prices from Yahoo Finance."""
    print(f"Fetching Yahoo: {ticker} ({col_name})...")
    df = yf.download(ticker, start=start, progress=False, auto_adjust=True)
    if isinstance(df.columns, pd.MultiIndex):
        close = df["Close"][ticker]
    else:
        close = df["Close"]
    close.index = pd.to_datetime(close.index).tz_localize(None)
    return close.rename(col_name)

def build_master_weekly_market_data() -> pd.DataFrame:
    """Fetches all macro/market series and resamples cleanly to Friday closes."""
    sp500 = fetch_yahoo_series("^GSPC", "SP500")
    vix = fetch_yahoo_series("^VIX", "VIX", start="1990-01-01")
    gold_spot = fetch_yahoo_series("GC=F", "Gold_Futures", start="2000-08-30")
    reit_etf = fetch_yahoo_series("VNQ", "VNQ_REIT", start="2004-09-29")

    dff = fetch_fred_series("DFF", "Overnight_Rate")
    dgs10 = fetch_fred_series("DGS10", "Treasury_10Y")
    wti_daily = fetch_fred_series("DCOILWTICO", "WTI_Daily")
    wti_mon = fetch_fred_series("MCOILWTICO", "WTI_Monthly")
    baa = fetch_fred_series("BAA", "Moodys_BAA")
    aaa = fetch_fred_series("AAA", "Moodys_AAA")
    case_shiller = fetch_fred_series("CSUSHPINSA", "Case_Shiller")

    all_series = [
        sp500, dff, dgs10, gold_spot,
        wti_daily, wti_mon, baa, aaa, case_shiller, reit_etf, vix
    ]
    daily_df = pd.concat(all_series, axis=1).sort_index()
    daily_df = daily_df.loc["1971-01-01":].ffill()

    daily_df["Gold_Price"] = daily_df["Gold_Futures"]
    daily_df["WTI_Oil"] = daily_df["WTI_Daily"].combine_first(daily_df["WTI_Monthly"])
    daily_df["Credit_Spread"] = daily_df["Moodys_BAA"] - daily_df["Moodys_AAA"]
    daily_df["Real_Estate"] = daily_df["VNQ_REIT"].combine_first(daily_df["Case_Shiller"])

    keep_cols = [
        "SP500", "Overnight_Rate", "Treasury_10Y", "Gold_Price",
        "Real_Estate", "WTI_Oil", "Credit_Spread", "VIX"
    ]
    return daily_df[keep_cols].resample("W-FRI").last()

# ==============================================================================
# 3. NORMALIZATION & WORKBOOK EXPORT
# ==============================================================================

def process_crashes(weekly_df: pd.DataFrame) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    metadata_rows = []
    raw_rows = []

    price_cols = ["SP500", "Gold_Price", "Real_Estate", "WTI_Oil"]
    rate_cols = ["Overnight_Rate", "Treasury_10Y", "Credit_Spread"]

    for crash_id, info in CRASH_EVENTS.items():
        peak_dt = pd.to_datetime(info["peak_date"])
        peak_fri = peak_dt + pd.offsets.Week(weekday=4) if peak_dt.weekday() != 4 else peak_dt

        start_fri = peak_fri - timedelta(weeks=PRE_CRASH_WEEKS)
        if info["recovery_date"]:
            rec_dt = pd.to_datetime(info["recovery_date"])
            end_fri = rec_dt + pd.offsets.Week(weekday=4) if rec_dt.weekday() != 4 else rec_dt
        else:
            end_fri = peak_fri + timedelta(weeks=FALLBACK_POST_WEEKS)

        slice_df = weekly_df.loc[start_fri:end_fri].copy()
        if peak_fri not in slice_df.index:
            print(f"Warning: Week 0 ({peak_fri.date()}) missing for {crash_id}")
            continue

        slice_df["Rel_Week"] = ((slice_df.index - peak_fri).days // 7).astype(int)
        week0_vals = slice_df.loc[peak_fri]

        for col in price_cols:
            if pd.notna(week0_vals[col]) and week0_vals[col] != 0:
                slice_df[f"{col}_Norm100"] = (slice_df[col] / week0_vals[col]) * 100.0
            else:
                slice_df[f"{col}_Norm100"] = pd.NA

        for col in rate_cols:
            if pd.notna(week0_vals[col]):
                slice_df[f"{col}_Diff"] = slice_df[col] - week0_vals[col]
            else:
                slice_df[f"{col}_Diff"] = pd.NA

        slice_df.insert(0, "Crash_ID", crash_id)
        slice_df.insert(1, "Date", slice_df.index.date)
        raw_rows.append(slice_df.reset_index(drop=True))

        post_peak = slice_df[slice_df["Rel_Week"] >= 0]
        min_sp = post_peak["SP500"].min()
        drawdown_pct = ((min_sp / week0_vals["SP500"]) - 1.0) * 100.0
        trough_wk = int(post_peak.loc[post_peak["SP500"].idxmin(), "Rel_Week"])
        rec_wk = int(slice_df["Rel_Week"].max()) if info["recovery_date"] else None

        metadata_rows.append({
            "Crash_ID": crash_id,
            "Short_Name": info["short_name"],
            "Peak_Date_Wk0": peak_fri.date(),
            "Trough_Date": info["trough_date"],
            "Trough_Rel_Week": trough_wk,
            "Recovery_Date": info["recovery_date"] or "Ongoing",
            "Recovery_Rel_Week": rec_wk,
            "SP500_Drawdown_%": round(drawdown_pct, 2),
            "Primary_Catalysts": info["catalysts"],
            "Fed_Monetary_Action": info["fed_action"]
        })

    meta_df = pd.DataFrame(metadata_rows)
    master_raw_df = pd.concat(raw_rows, ignore_index=True)

    pivots = {
        "Chart_SP500_Norm": master_raw_df.pivot(index="Rel_Week", columns="Crash_ID", values="SP500_Norm100"),
        "Chart_FedFunds_Diff": master_raw_df.pivot(index="Rel_Week", columns="Crash_ID", values="Overnight_Rate_Diff"),
        "Chart_10Y_Diff": master_raw_df.pivot(index="Rel_Week", columns="Crash_ID", values="Treasury_10Y_Diff"),
        "Chart_Gold_Norm": master_raw_df.pivot(index="Rel_Week", columns="Crash_ID", values="Gold_Price_Norm100"),
        "Chart_RealEstate_Norm": master_raw_df.pivot(index="Rel_Week", columns="Crash_ID", values="Real_Estate_Norm100"),
        "Chart_Oil_Norm": master_raw_df.pivot(index="Rel_Week", columns="Crash_ID", values="WTI_Oil_Norm100"),
        }
    
    with pd.ExcelWriter(OUTPUT_FILE, engine="openpyxl") as writer:
        meta_df.to_excel(writer, sheet_name="Event_Metadata", index=False)
        master_raw_df.to_excel(writer, sheet_name="Raw_And_Normalized_Data", index=False)
        for sheet_name, p_df in pivots.items():
            p_df.to_excel(writer, sheet_name=sheet_name)
    print(f"\nSuccess! Exported '{OUTPUT_FILE}' with {len(meta_df)} crashes.")

if __name__ == "__main__":
    weekly_market_data = build_master_weekly_market_data()
    process_crashes(weekly_market_data)
