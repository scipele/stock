import argparse
import pandas as pd
import numpy as np
import yfinance as yf
import mplfinance as mpf
import re
import matplotlib.pyplot as plt
from pathlib import Path

# --- EXCLUSION FILTERS CONFIGURED AT THE TOP ---
EXCLUDE_NAMES_CONTAINING = r"etf|fund|money|adm"

import warnings
warnings.filterwarnings("ignore")

import logging
logging.getLogger('matplotlib.font_manager').setLevel(logging.ERROR)
logging.getLogger('matplotlib').setLevel(logging.ERROR)


INPUT_FOLDER = Path("/home/dev/stock/intraday_charting/output")
CHART_FOLDER = Path("/home/dev/stock/intraday_charting/charts")
# Absolute Schwab download path
SCHWAB_FOLDER = Path("/home/ts/Downloads")



def get_50day_ma_series(ticker: str, target_index: pd.DatetimeIndex) -> pd.Series | None:
    """
    Fetch daily data, compute 50-day SMA, and align it to the
    intraday index (forward-filled so it stays constant within each day).
    """
    try:
        daily = yf.download(
            ticker,
            period="120d",          # safe buffer for 50 trading days
            interval="1d",
            progress=False,
            auto_adjust=True,
            threads=False,
        )
        if daily.empty or len(daily) < 50:
            return None

        # Handle possible MultiIndex columns from yfinance
        if isinstance(daily.columns, pd.MultiIndex):
            close = daily["Close"].iloc[:, 0]
        else:
            close = daily["Close"]

        # True 50-day SMA on daily closes
        sma50 = close.rolling(window=50, min_periods=50).mean()

        # Align to the intraday timestamps (forward-fill so the line
        # stays flat within each trading day and steps on new days)
        aligned = sma50.reindex(target_index, method="ffill")

        # Drop any leading NaNs that couldn't be filled
        if aligned.isna().all():
            return None
        return aligned

    except Exception as e:
        print(f"{ticker}: could not compute 50-day MA series ({e})")
        return None


def add_vwap(df: pd.DataFrame) -> pd.Series:
    """Daily VWAP that resets each trading day."""
    df = df.copy()
    df['date'] = df.index.date
    df['tp'] = (df['High'] + df['Low'] + df['Close']) / 3
    df['tp_vol'] = df['tp'] * df['Volume']
    df['cum_tp_vol'] = df.groupby('date')['tp_vol'].cumsum()
    df['cum_vol'] = df.groupby('date')['Volume'].cumsum()
    return df['cum_tp_vol'] / df['cum_vol']


def add_ema(df: pd.DataFrame, length: int = 9) -> pd.Series:
    """EMA on Close."""
    return df['Close'].ewm(span=length, adjust=False).mean()


def find_schwab_data():
    """
    Finds the absolute latest dated Schwab CSV export file in Downloads,
    parses it, filters out rows matching EXCLUDE_NAMES_CONTAINING, 
    and returns two dictionaries:
    1. Mapping tickers to their Cost/Share (entry_prices).
    2. Mapping tickers to their Full Corporate Name Description (company_names).
    """
    try:
        # Match only files matching your specific Schwab format pattern
        schwab_files = list(SCHWAB_FOLDER.glob("Community Property-Positions-*.csv"))
        
        if not schwab_files:
            print("Warning: No Schwab export files found in Downloads. Proceeding with clean fallbacks.")
            return {}, {}
            
        # Get the latest file automatically by modification timestamp
        latest_file = max(schwab_files, key=lambda f: f.stat().st_mtime)
        print(f"\n   Loading metadata from newest Schwab export: {latest_file.name}\n")

        
        # Schwab files have a text header row before the table structure.
        with open(latest_file, "r") as f:
            lines = f.readlines()
            
        header_row_index = 0
        for idx, line in enumerate(lines):
            if '"Symbol"' in line or 'Symbol' in line:
                header_row_index = idx
                break
                
        # Re-read using Pandas from the verified header starting row
        schwab_df = pd.read_csv(latest_file, skiprows=header_row_index)
        
        # Strip spaces and ensure mandatory columns exist
        schwab_df.columns = [col.strip() for col in schwab_df.columns]
        if 'Symbol' not in schwab_df.columns or 'Cost/Share' not in schwab_df.columns:
            print("Warning: Schwab file columns did not match expectations.")
            return {}, {}
            
        price_map = {}
        name_map = {}
        
        # Compile global pattern ignoring uppercase/lowercase sensitivity
        exclude_regex = re.compile(EXCLUDE_NAMES_CONTAINING, re.IGNORECASE)
        
        # Pull details row by row, tracking descriptions
        for _, row in schwab_df.dropna(subset=['Symbol']).iterrows():
            sym = str(row['Symbol']).strip().upper()
            desc = str(row.get('Description', '')).strip()
            
            # --- EVALUATE FILTER PATTERNS AGAINST DESCRIPTION FIELD ---
            if desc and exclude_regex.search(desc):
                # print(f"Skipping Schwab processing for {sym}: Name matches exclusion filter ('{desc}')")
                continue
            
            # 1. Store the Cost/Share entry price mapping
            if 'Cost/Share' in schwab_df.columns and pd.notna(row['Cost/Share']):
                cost_raw = str(row['Cost/Share']).replace('$', '').replace(',', '').strip()
                try:
                    price_map[sym] = float(cost_raw)
                except ValueError:
                    pass
            
            # 2. Store the Description company name mapping
            if 'Description' in schwab_df.columns and pd.notna(row['Description']):
                name_map[sym] = desc.upper()
                
        return price_map, name_map
    except Exception as e:
        print(f"Error parsing Schwab file: {e}")
        return {}, {}

def find_swing_levels(df, previous_day_high, previous_day_low, lookback=3):
    """
    Find the most recent swing high and swing low that also satisfy:
    - Swing High > Previous Day High
    - Swing Low  ≤ Previous Day Low
    """
    swing_high = None
    swing_low = None

    if previous_day_high is None or previous_day_low is None:
        return None, None

    # Search from newest to oldest, skip the very latest candles
    for i in range(len(df) - lookback - 1, lookback, -1):
        high = df["High"].iloc[i]
        low  = df["Low"].iloc[i]

        left_highs  = df["High"].iloc[i - lookback : i]
        right_highs = df["High"].iloc[i + 1 : i + lookback + 1]
        left_lows   = df["Low"].iloc[i - lookback : i]
        right_lows  = df["Low"].iloc[i + 1 : i + lookback + 1]

        # Swing High: local pivot AND higher than previous day high
        if swing_high is None:
            if (high > left_highs.max() and 
                high > right_highs.max() and 
                high > previous_day_high):
                swing_high = high

        # Swing Low: local pivot AND at or below previous day low
        if swing_low is None:
            if (low < left_lows.min() and 
                low < right_lows.min() and 
                low <= previous_day_low):
                swing_low = low

        if swing_high is not None and swing_low is not None:
            break

    return swing_high, swing_low


def create_chart(indx, file_count, csv_file, days_to_plot, schwab_prices, schwab_names):
    ticker = csv_file.stem.upper()
    # used for debug
    # print(f"Creating chart: {ticker}")
    
    # --- SAFE TITLE LOOKUP WITH ROBUST FALLBACK ---
    common_stock_fallbacks = {
        "GS": "GOLDMAN SACHS GROUP INC",
        "AAPL": "APPLE INC",
        "MSFT": "MICROSOFT CORP",
        "TSLA": "TESLA INC",
        "NVDA": "NVIDIA CORP",
        "QQQ": "INVESCO QQQ TRUST",
        "GD": "GENERAL DYNAMICS CORP"
    }
    
    if ticker in schwab_names:
        company_name = schwab_names[ticker]
    else:
        company_name = common_stock_fallbacks.get(ticker, ticker)
        
    exchange = "NASDAQ" if ticker in ["QQQ", "AAPL", "MSFT", "TSLA", "NVDA"] else "NYSE"
    sub_title_string = f"- {company_name} ({exchange}) | 5 Minute Chart ({days_to_plot} days)"
    
    # Look up the automated entry price using our mapped dictionary
    entry_price = schwab_prices.get(ticker, None)
    if entry_price is not None:
        print(f"\r   Processed {indx} of {file_count}", end="\r")

    # Read CSV
    df = pd.read_csv(
        csv_file, parse_dates=["Datetime"]
    )
    # mplfinance requires datetime index
    df.set_index("Datetime", inplace=True)
    
    # -----------------------------
    # Calculate support/resistance
    # -----------------------------
    if df.empty:
        print(f"{ticker}: No data available, skipping chart")
        return

    # Previous Day High / Low
    # -------------------------------------------------
    # When the market is closed (weekend / after-hours),
    # the most recent day in the data IS the previous trading day.
    # When the market is open, the previous day is the one before it.

    unique_days = sorted(df.index.normalize().unique())

    if len(unique_days) == 0:
        previous_day_high = None
        previous_day_low  = None
    else:
        last_data_day = unique_days[-1].date()
        today = pd.Timestamp.now().normalize().date()

        # Market is considered closed if the latest data is from a previous calendar day
        market_closed = last_data_day < today

        if market_closed or len(unique_days) == 1:
            # Use the most recent day in the data as "previous day"
            prev_day = unique_days[-1]
        else:
            # Market is open → use the day before the most recent day
            prev_day = unique_days[-2]

        prev_day_mask = df.index.normalize() == prev_day
        previous_day_high = df.loc[prev_day_mask, "High"].max()
        previous_day_low  = df.loc[prev_day_mask, "Low"].min()

    # Swing levels with your required constraints
    swing_high, swing_low = find_swing_levels(df, previous_day_high, previous_day_low)
    
    # Rename columns to mplfinance format
    df.rename(
        columns={
            "Open": "Open",
            "High": "High",
            "Low": "Low",
            "Close": "Close",
            "Volume": "Volume"
        },
        inplace=True
    )
    
    # 2. Immediately create your day mask and filter your DataFrame
    unique_days = df.index.normalize().unique()
    last_x_days = unique_days[-days_to_plot:]
    day_mask = df.index.normalize().isin(last_x_days)
    df_filtered = df[day_mask].copy() 

    # --- Key indicators ---
    ma50_series = get_50day_ma_series(ticker, df_filtered.index)
    vwap = add_vwap(df_filtered)
    ema9 = add_ema(df_filtered, length=9)

    # Split EMA into rising / falling for color
    ema_up = ema9.where(ema9 >= ema9.shift(1))
    ema_down = ema9.where(ema9 < ema9.shift(1))
    
    # --- AUTOMATED TICKSCALE WITH PANDAS INT RESOLUTION FIX ---
    df_filtered['date_str'] = df_filtered.index.strftime('%Y-%m-%d')
    tick_positions = []
    tick_labels = []
    
    for day_group, group_data in df_filtered.groupby('date_str'):
        first_candle_ts = group_data.index.min()
        first_candle_idx = df_filtered.index.get_loc(first_candle_ts)
        
        # Resolves range positions safely across long multi-day windows
        if isinstance(first_candle_idx, slice):
            first_candle_idx = first_candle_idx.start
        elif hasattr(first_candle_idx, '__iter__'):
            first_candle_idx = first_candle_idx[0]
            
        tick_positions.append(int(first_candle_idx))
        tick_labels.append(first_candle_ts.strftime('%Y-%m-%d %H:%M'))
        
    df_filtered.drop(columns=['date_str'], inplace=True)

    # 3. Create lines container (Appended in your specific requested layout order)
    levels = []
    
    # [ORDER 1]: swing_high
    if swing_high is not None:
        levels.append(
            mpf.make_addplot(
                pd.Series(swing_high, index=df_filtered.index),
                color="red", linestyle="--", width=1,
                label=f"{swing_high:.2f} swing_high"
            )
        )
        
    # [ORDER 2]: prev_day_high
    if previous_day_high is not None:
        levels.append(
            mpf.make_addplot(
                pd.Series(previous_day_high, index=df_filtered.index),
                color="orange", linestyle=":", width=1,
                label=f"{previous_day_high:.2f} previous_day_high"
            )
        )
    
    # [ORDER 3]: prev_day_low
    if previous_day_low is not None:
        levels.append(
            mpf.make_addplot(
                pd.Series(previous_day_low, index=df_filtered.index),
                color="blue", linestyle=":", width=1,
                label=f"{previous_day_low:.2f} previous_day_low"
            )
        )
    
    # [ORDER 4]: swing_low
    if swing_low is not None:
        levels.append(
            mpf.make_addplot(
                pd.Series(swing_low, index=df_filtered.index),
                color="green", linestyle="--", width=1,
                label=f"{swing_low:.2f} swing_low"
            )
        )
        
    # [ORDER 5]: entry_price
    if entry_price is not None:
        entry_series = pd.Series(np.nan, index=df_filtered.index)
        entry_series.iloc[0] = entry_price 
        
        levels.append(
            mpf.make_addplot(
                entry_series,
                type='scatter',
                markersize=120,
                marker='o',
                color='purple',
                label=f"{entry_price:.2f} entry_price"
            )
        )

    # 50-day MA
    if ma50_series is not None:
        levels.append(
            mpf.make_addplot(
                ma50_series,
                color='magenta',
                width=1.6,
                label='50-day MA'
            )
        )

    # VWAP
    levels.append(
        mpf.make_addplot(
            vwap,
            color='cyan',
            width=1.4,
            label='VWAP'
        )
    )

    # 9 EMA - rising (green)
    levels.append(
        mpf.make_addplot(
            ema_up,
            color='lime',
            width=1.3,
            label='9 EMA ↑'
        )
    )

    # 9 EMA - falling (red)
    levels.append(
        mpf.make_addplot(
            ema_down,
            color='red',
            width=1.3,
            label='9 EMA ↓'
        )
    )
    
    # Extract active numeric values for the Y-Axis price ticks
    active_prices = [p for p in [swing_high, swing_low, previous_day_high, previous_day_low, entry_price] if p is not None]

    if ma50_series is not None:
        active_prices.extend([ma50_series.min(), ma50_series.max()])

    active_prices.extend([vwap.min(), vwap.max(), ema9.min(), ema9.max()])

        
    # 4. Pass cleanly to mpf.plot and use returnfig to render legend
    fig, axlist = mpf.plot(
        df_filtered,
        type="candle",
        volume=True,
        style="yahoo",
        title="",
        ylabel="Price",
        ylabel_lower="Volume",
        mav=(days_to_plot, 50),
        addplot=levels,
        figsize=(18, 14),
        warn_too_much_data=5000,
        hlines=dict(hlines=active_prices, colors='none'),
        returnfig=True
    )
    
    # --- CUSTOM METADATA TEXT BLOCKS FOR THUMBNAIL VISIBILITY ---
    # FIXED: Increased font size to 90 (~3.2x larger) for immediate readability from a distance
    fig.text(
        0.05, 0.94, ticker,
        fontsize=90, weight='bold', color='black', ha='left', va='center'
    )
    
    # FIXED: Pushed X coordinate out to 0.28 to make clean room for the wider text layout
    # Company name + chart info — right aligned
    fig.text(
        0.98, 0.94, sub_title_string,
        fontsize=14, weight='normal', color='#444444',
        ha='right', va='center'
    )
    # -----------------------------------------------------------------

    # Explicitly force our calculated positions and labels to overwrite the bottom volume axis
    axlist[2].set_xticks(tick_positions)
    axlist[2].set_xticklabels(tick_labels, rotation=90, fontsize=9)

    # Remove the legend that mplfinance automatically creates
    if axlist[0].get_legend() is not None:
        axlist[0].get_legend().remove()

    # Now place your custom legend in the left margin
    handles, labels = axlist[0].get_legend_handles_labels()
    fig.legend(
        handles, labels,
        loc='upper left',
        bbox_to_anchor=(0.01, 0.87),
        fontsize=8.5,
        framealpha=0.92,
        borderpad=0.3,
        handlelength=1.3,
        labelspacing=0.3
    )
    
    # --- Make extra room at the bottom for rotated x-labels + notes ---
    fig.subplots_adjust(bottom=0.28)   # increased from 0.20 / 0.22

    notes = (
        "50-day MA     → Longer-term trend. Price above = bullish bias, below = bearish bias.\n"
        "VWAP          → Volume Weighted Average Price (today's fair value). "
        "Above = buyers in control, below = sellers in control.\n"
        "9 EMA         → Short-term trend. Green = rising (bullish), Red = falling (bearish).\n"
        "Swing High/Low→ Recent significant peaks & troughs used as resistance/support.\n"
        "Prev Day H/L  → Previous trading day's high & low – common intraday reaction levels.\n"
        "Entry Price   → Your average cost basis (from Schwab). Purple dot marks your entry."
    )

    fig.text(
        0.02, 0.01,                 # left side, very bottom
        notes,
        ha='left',
        va='bottom',
        fontsize=7,
        family='monospace',
        linespacing=1.35,
        color='#222222',
        bbox=dict(boxstyle='round,pad=0.4', facecolor='#f8f8f8', edgecolor='#cccccc', alpha=0.95)
    )

    # Save chart image canvas safely
    fig.savefig(CHART_FOLDER / f"{ticker.lower()}.png", bbox_inches='tight')
    
    # --- RESET MEMORY ACTIVE BUFFERS TO PREVENT CLOSURE HANGS ---
    plt.cla()       # Clears active axis lines
    plt.clf()       # Clears description canvas frames
    plt.close(fig)  # Safely releases file buffer control handles

def main():
    CHART_FOLDER.mkdir(exist_ok=True)
    parser = argparse.ArgumentParser(description="Plot a candlestick chart for a given ticker.")
    parser.add_argument("-d", "--days", type=int, default=8, help="Number of days to include in the chart (default: 8)")
    parser.add_argument("-e", "--entry", type=str, default="0", help="Deprecated placeholder flag (automated lookup active)")
    args = parser.parse_args()
    
    # Fetch automated entries prices and descriptive company names dictionaries
    schwab_prices, schwab_names = find_schwab_data()
    
    files = INPUT_FOLDER.glob("*.csv")
    indx = 0
    file_count = len(list(INPUT_FOLDER.glob("*.csv")))
    for file in files:
        indx += 1
        create_chart(indx, file_count, file, days_to_plot=args.days, schwab_prices=schwab_prices, schwab_names=schwab_names)

# FIXED: Readded missing underscores to prevent execution failures
if __name__ == "__main__":
    main()
