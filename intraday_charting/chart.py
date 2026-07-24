import logging
import argparse
import pandas as pd
import numpy as np
import mplfinance as mpf
import re
import matplotlib.pyplot as plt
from pathlib import Path

# --- EXCLUSION FILTERS CONFIGURED AT THE TOP ---
EXCLUDE_NAMES_CONTAINING = r"etf|fund|money|adm"

# Silence the matplotlib font manager warnings specifically
logging.getLogger('matplotlib.font_manager').setLevel(logging.ERROR)

INPUT_FOLDER = Path("/home/dev/cpp/stock_intraday/output")
CHART_FOLDER = Path("/home/dev/py/stock_intraday/charts")
# Absolute Schwab download path
SCHWAB_FOLDER = Path("/home/ts/Downloads")

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
        print(f"Loading metadata from newest Schwab export: {latest_file.name}")
        
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
                print(f"Skipping Schwab processing for {sym}: Name matches exclusion filter ('{desc}')")
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

def find_swing_levels(df, previous_day_high, previous_day_low):
    swing_high = None
    swing_low = None
    lookback = 3 # candles on each side
    
    # Search backward, skipping newest candles
    for i in range(len(df)-lookback-1, lookback, -1):
        high = df["High"].iloc[i]
        low = df["Low"].iloc[i]
        
        # Swing high:
        # higher than 3 candles before and after
        if swing_high is None:
            left_highs = df["High"].iloc[i-lookback:i]
            right_highs = df["High"].iloc[i+1:i+lookback+1]
            if (
                high > left_highs.max() and 
                high > right_highs.max() and 
                high > previous_day_high
            ):
                swing_high = high
                
        # Swing low:
        if swing_low is None:
            left_lows = df["Low"].iloc[i-lookback:i]
            right_lows = df["Low"].iloc[i+1:i+lookback+1]
            if (
                low < left_lows.min() and 
                low < right_lows.min() and 
                low < previous_day_low
            ):
                swing_low = low
                
        if swing_high and swing_low:
            break
            
    return swing_high, swing_low

def create_chart(csv_file, days_to_plot, schwab_prices, schwab_names):
    ticker = csv_file.stem.upper()
    print(f"Creating chart: {ticker}")
    
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
        print(f"{ticker}: Automated Entry Price loaded = ${entry_price:.2f}")

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

    # Most recent trading day
    last_day = df.index[-1].date()
    recent_day = df[ df.index.date == last_day ]
    previous_day_high = recent_day["High"].max()
    previous_day_low = recent_day["Low"].min()
    swing_high, swing_low = find_swing_levels(
        df, previous_day_high, previous_day_low
    )
    print(
        f"{ticker}: "
        f"Swing High={swing_high}, "
        f"Swing Low={swing_low}"
    )
    print(
        f"{ticker}: "
        f"Day High={previous_day_high:.2f}, "
        f"Day Low={previous_day_low:.2f} "
    )
    
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

    # Extract active numeric values for the Y-Axis price ticks
    active_prices = [p for p in [swing_high, swing_low, previous_day_high, previous_day_low, entry_price] if p is not None]
    
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
        figsize=(14, 8),
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
    fig.text(
        0.28, 0.94, sub_title_string,
        fontsize=14, weight='normal', color='#444444', ha='left', va='center'
    )
    # -----------------------------------------------------------------

    # Explicitly force our calculated positions and labels to overwrite the bottom volume axis
    axlist[2].set_xticks(tick_positions)
    axlist[2].set_xticklabels(tick_labels, rotation=90, fontsize=9)
    
    # Clean up and draw legend on the main candle axis container safely
    axlist[0].legend(loc="upper left", fontsize=10)
    
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
    for file in files:
        create_chart(file, days_to_plot=args.days, schwab_prices=schwab_prices, schwab_names=schwab_names)

# FIXED: Readded missing underscores to prevent execution failures
if __name__ == "__main__":
    main()
