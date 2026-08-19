import argparse
import os
import time
import warnings
from pathlib import Path

import matplotlib
# Matplotlib can report DISPLAY but still run headless depending on session type.
# Probe GUI backends and fall back to Agg so live mode never hard-fails.
warnings.filterwarnings("ignore", message="Unable to import Axes3D.*")


def select_backend():
    if not os.environ.get("DISPLAY"):
        matplotlib.use("Agg", force=True)
        return False

    for candidate in ("QtAgg", "TkAgg", "GTK3Agg", "WXAgg"):
        try:
            matplotlib.use(candidate, force=True)
            import matplotlib.pyplot as _plt

            fig = _plt.figure()
            _plt.close(fig)
            return True
        except Exception:
            continue

    matplotlib.use("Agg", force=True)
    return False


GUI_AVAILABLE = select_backend()

import matplotlib.pyplot as plt
import mplfinance as mpf
import numpy as np
import pandas as pd
import yfinance as yf

# --- EXCLUSION FILTERS CONFIGURED AT THE TOP ---
EXCLUDE_NAMES_CONTAINING = r"etf|fund|money|adm"

import logging
import re

warnings.filterwarnings("ignore")
logging.getLogger("matplotlib.font_manager").setLevel(logging.ERROR)
logging.getLogger("matplotlib").setLevel(logging.ERROR)

INPUT_FOLDER = Path("/home/dev/stock/intraday_chart_live/input")
OUTPUT_FOLDER = Path("/home/dev/stock/intraday_chart_live/output")
CHART_FOLDER = Path("/home/dev/stock/intraday_chart_live/charts")
SCHWAB_FOLDER = Path("/home/ts/Downloads")


def read_tickers(path: Path):
    if not path.exists():
        return []

    tickers = []
    try:
        df = pd.read_csv(path)
        if "ticker" in df.columns:
            series = df["ticker"]
        elif "Ticker" in df.columns:
            series = df["Ticker"]
        else:
            series = df.iloc[:, 0]

        for value in series:
            cleaned = str(value).strip().upper()
            if cleaned:
                tickers.append(cleaned)
    except Exception:
        pass

    return tickers


def get_50day_ma_series(ticker: str, target_index: pd.DatetimeIndex):
    """Return a 50-day moving average aligned to the intraday index."""
    try:
        daily = yf.download(
            ticker,
            period="120d",
            interval="1d",
            progress=False,
            auto_adjust=True,
            threads=False,
        )
        if daily.empty or len(daily) < 50:
            return None

        close = daily["Close"] if "Close" in daily.columns else daily.iloc[:, 3]
        sma50 = close.rolling(window=50, min_periods=50).mean()
        aligned = sma50.reindex(target_index, method="ffill")
        if aligned.isna().all():
            return None
        return aligned
    except Exception as exc:
        print(f"{ticker}: warning - could not compute 50-day MA ({exc})")
        return None


def add_vwap(df: pd.DataFrame) -> pd.Series:
    df = df.copy()
    df["date"] = df.index.date
    df["tp"] = (df["High"] + df["Low"] + df["Close"]) / 3
    df["tp_vol"] = df["tp"] * df["Volume"]
    df["cum_tp_vol"] = df.groupby("date")["tp_vol"].cumsum()
    df["cum_vol"] = df.groupby("date")["Volume"].cumsum()
    return df["cum_tp_vol"] / df["cum_vol"]


def add_ema(df: pd.DataFrame, length: int = 9) -> pd.Series:
    return df["Close"].ewm(span=length, adjust=False).mean()


def find_schwab_data():
    try:
        files = list(SCHWAB_FOLDER.glob("Community Property-Positions-*.csv"))
        if not files:
            return {}, {}

        latest_file = max(files, key=lambda p: p.stat().st_mtime)
        with open(latest_file, "r", encoding="utf-8", errors="ignore") as handle:
            lines = handle.readlines()

        header_index = 0
        for idx, line in enumerate(lines):
            if '"Symbol"' in line or 'Symbol' in line:
                header_index = idx
                break

        schwab_df = pd.read_csv(latest_file, skiprows=header_index)
        schwab_df.columns = [str(col).strip() for col in schwab_df.columns]

        if "Symbol" not in schwab_df.columns or "Cost/Share" not in schwab_df.columns:
            return {}, {}

        price_map = {}
        name_map = {}
        exclude_regex = re.compile(EXCLUDE_NAMES_CONTAINING, re.IGNORECASE)

        for _, row in schwab_df.dropna(subset=["Symbol"]).iterrows():
            sym = str(row["Symbol"]).strip().upper()
            desc = str(row.get("Description", "")).strip()
            if desc and exclude_regex.search(desc):
                continue

            if pd.notna(row.get("Cost/Share")):
                try:
                    price_map[sym] = float(str(row["Cost/Share"]).replace("$", "").replace(",", "").strip())
                except ValueError:
                    pass

            if pd.notna(row.get("Description")):
                name_map[sym] = desc.upper()

        return price_map, name_map
    except Exception:
        return {}, {}


def current_session_only(df: pd.DataFrame) -> pd.DataFrame:
    temp = df.copy()
    if "Datetime" in temp.columns:
        temp["Datetime"] = pd.to_datetime(temp["Datetime"], errors="coerce")
    elif "Timestamp" in temp.columns:
        temp["Datetime"] = pd.to_datetime(temp["Timestamp"], unit="s", errors="coerce")

    temp = temp.dropna(subset=["Datetime"]).sort_values("Datetime")
    if temp.empty:
        return temp

    session_day = temp["Datetime"].max().normalize()
    temp = temp[temp["Datetime"].dt.normalize() == session_day].copy()
    temp = temp.set_index("Datetime")
    temp = temp[~temp.index.duplicated(keep="last")]
    return temp


def find_swing_levels(df, lookback=3):
    if len(df) < lookback * 2 + 2:
        return None, None

    swing_high = None
    swing_low = None

    for i in range(lookback, len(df) - lookback):
        current_high = df["High"].iloc[i]
        current_low = df["Low"].iloc[i]
        left_highs = df["High"].iloc[i - lookback : i]
        right_highs = df["High"].iloc[i + 1 : i + lookback + 1]
        left_lows = df["Low"].iloc[i - lookback : i]
        right_lows = df["Low"].iloc[i + 1 : i + lookback + 1]

        if swing_high is None and current_high > left_highs.max() and current_high > right_highs.max():
            swing_high = current_high
        if swing_low is None and current_low < left_lows.min() and current_low < right_lows.min():
            swing_low = current_low
        if swing_high is not None and swing_low is not None:
            break

    return swing_high, swing_low


def draw_live_dashboard(tickers, refresh_seconds=60, cols=4, save_png=True, fig=None):
    CHART_FOLDER.mkdir(exist_ok=True)
    tickers = [t for t in tickers if t]
    if not tickers:
        return

    fig_cols = min(cols, max(1, len(tickers)))
    fig_rows = int(np.ceil(len(tickers) / fig_cols))
    if fig is None:
        fig = plt.figure(figsize=(24, 13))
    fig.clf()
    fig.set_size_inches(24, 13, forward=True)
    axes = fig.subplots(fig_rows, fig_cols, squeeze=False)
    fig.patch.set_facecolor("white")
    axes = axes.flatten()

    for idx, ax in enumerate(axes):
        ax.clear()
        for spine in ax.spines.values():
            spine.set_visible(False)
        ax.grid(True, alpha=0.14, linewidth=0.6)
        ax.set_facecolor("#f9f9f9")

        if idx >= len(tickers):
            ax.axis("off")
            continue

        ticker = tickers[idx]
        csv_path = OUTPUT_FOLDER / f"{ticker}.csv"
        if not csv_path.exists():
            csv_path = INPUT_FOLDER / f"{ticker}.csv"
        if not csv_path.exists():
            ax.text(0.5, 0.5, f"{ticker}\nNo data", ha="center", va="center", fontsize=9)
            ax.axis("off")
            continue

        try:
            df = pd.read_csv(csv_path, parse_dates=["Datetime"])
            df = df.sort_values("Datetime")
            df = current_session_only(df)
            if df.empty:
                ax.text(0.5, 0.5, f"{ticker}\nNo current session", ha="center", va="center", fontsize=9)
                ax.axis("off")
                continue

            df = df.rename(columns={"Open": "Open", "High": "High", "Low": "Low", "Close": "Close", "Volume": "Volume"})
            df.index = pd.to_datetime(df.index)

            session_high = df["High"].max()
            session_low = df["Low"].min()
            current_close = df["Close"].iloc[-1]
            swing_high, swing_low = find_swing_levels(df)
            vwap = add_vwap(df)
            ema9 = add_ema(df, 9)
            ema_up = ema9.where(ema9 >= ema9.shift(1))
            ema_down = ema9.where(ema9 < ema9.shift(1))

            levels = []
            if swing_high is not None:
                levels.append(mpf.make_addplot(pd.Series(swing_high, index=df.index), color="red", linestyle="--", width=1.0, ax=ax))
            if session_high is not None:
                levels.append(mpf.make_addplot(pd.Series(session_high, index=df.index), color="orange", linestyle=":", width=1.0, ax=ax))
            if session_low is not None:
                levels.append(mpf.make_addplot(pd.Series(session_low, index=df.index), color="blue", linestyle=":", width=1.0, ax=ax))
            if swing_low is not None:
                levels.append(mpf.make_addplot(pd.Series(swing_low, index=df.index), color="green", linestyle="--", width=1.0, ax=ax))
            levels.append(mpf.make_addplot(vwap, color="cyan", width=1.2, ax=ax))
            levels.append(mpf.make_addplot(ema_up, color="lime", width=1.1, ax=ax))
            levels.append(mpf.make_addplot(ema_down, color="red", width=1.1, ax=ax))

            mpf.plot(
                df,
                type="candle",
                ax=ax,
                volume=False,
                style="yahoo",
                show_nontrading=False,
                xrotation=0,
                warn_too_much_data=2500,
                addplot=levels,
                datetime_format="%H:%M",
                scale_padding={"left": 0.03, "right": 0.03, "top": 0.03, "bottom": 0.03},
                tight_layout=True,
            )

            ax.set_title(f"{ticker}  {current_close:.2f}", fontsize=9, pad=4)
            ax.tick_params(axis="both", labelsize=6)
            ax.set_ylabel("")
            ax.set_xlabel("")
            ax.margins(x=0.02, y=0.08)

        except Exception:
            ax.text(0.5, 0.5, f"{ticker}\nError", ha="center", va="center", fontsize=9)
            ax.axis("off")

    fig.align_ylabels()
    fig.suptitle(
        f"Current Session Dashboard   {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}   Refresh {refresh_seconds}s",
        fontsize=14,
        y=0.99,
    )
    fig.subplots_adjust(left=0.03, right=0.99, top=0.93, bottom=0.04, hspace=0.18, wspace=0.12)

    if save_png:
        dashboard_path = CHART_FOLDER / "live_dashboard.png"
        fig.savefig(dashboard_path, dpi=200, bbox_inches="tight", facecolor="white")

    return fig


def create_chart(indx, file_count, csv_file, days_to_plot, schwab_prices, schwab_names):
    ticker = csv_file.stem.upper()
    entry_price = schwab_prices.get(ticker)

    df = pd.read_csv(csv_file, parse_dates=["Datetime"])
    df = df.sort_values("Datetime")
    df.set_index("Datetime", inplace=True)

    if df.empty:
        return

    unique_days = sorted(df.index.normalize().unique())
    if len(unique_days) == 0:
        return

    prev_day = unique_days[-1] if len(unique_days) == 1 else unique_days[-2]
    prev_day_mask = df.index.normalize() == prev_day
    previous_day_high = df.loc[prev_day_mask, "High"].max()
    previous_day_low = df.loc[prev_day_mask, "Low"].min()
    swing_high, swing_low = find_swing_levels(df)

    ma50_series = get_50day_ma_series(ticker, df.index)
    vwap = add_vwap(df)
    ema9 = add_ema(df, 9)
    ema_up = ema9.where(ema9 >= ema9.shift(1))
    ema_down = ema9.where(ema9 < ema9.shift(1))

    levels = []
    if swing_high is not None:
        levels.append(mpf.make_addplot(pd.Series(swing_high, index=df.index), color="red", linestyle="--", width=1.0))
    if previous_day_high is not None:
        levels.append(mpf.make_addplot(pd.Series(previous_day_high, index=df.index), color="orange", linestyle=":", width=1.0))
    if previous_day_low is not None:
        levels.append(mpf.make_addplot(pd.Series(previous_day_low, index=df.index), color="blue", linestyle=":", width=1.0))
    if swing_low is not None:
        levels.append(mpf.make_addplot(pd.Series(swing_low, index=df.index), color="green", linestyle="--", width=1.0))
    if entry_price is not None:
        entry_series = pd.Series(np.nan, index=df.index)
        entry_series.iloc[0] = entry_price
        levels.append(mpf.make_addplot(entry_series, type="scatter", markersize=120, marker="o", color="purple"))
    if ma50_series is not None:
        levels.append(mpf.make_addplot(ma50_series, color="magenta", width=1.6))
    levels.append(mpf.make_addplot(vwap, color="cyan", width=1.4))
    levels.append(mpf.make_addplot(ema_up, color="lime", width=1.3))
    levels.append(mpf.make_addplot(ema_down, color="red", width=1.3))

    fig, axlist = mpf.plot(
        df,
        type="candle",
        volume=False,
        style="yahoo",
        title="",
        ylabel="Price",
        addplot=levels,
        figsize=(18, 12),
        warn_too_much_data=5000,
        returnfig=True,
    )

    fig.text(0.02, 0.96, ticker, fontsize=42, weight="bold")
    fig.text(0.98, 0.96, f"{ticker} | current session", fontsize=12, ha="right")
    fig.savefig(CHART_FOLDER / f"{ticker.lower()}.png", bbox_inches="tight")
    plt.close(fig)


def main():
    CHART_FOLDER.mkdir(exist_ok=True)
    parser = argparse.ArgumentParser(description="Plot intraday stock charts.")
    parser.add_argument("-d", "--days", type=int, default=1, help="Number of days to include in the chart.")
    parser.add_argument("-l", "--live", action="store_true", help="Generate a live dashboard of the current session.")
    parser.add_argument("--refresh-seconds", type=int, default=30, help="Seconds between live dashboard refreshes.")
    parser.add_argument("--cols", type=int, default=4, help="Number of dashboard columns for the large monitor layout.")
    parser.add_argument("--no-volume", action="store_true", help="Disable volume in static charts.")
    parser.add_argument("-e", "--entry", type=str, default="0", help="Deprecated placeholder flag.")
    args = parser.parse_args()

    if args.live:
        tickers = read_tickers(INPUT_FOLDER / "tickers.csv")
        if not tickers:
            tickers = [p.stem.upper() for p in INPUT_FOLDER.glob("*.csv")]

        show_window = GUI_AVAILABLE
        if show_window:
            plt.ion()
        else:
            print(f"No GUI display detected. Writing dashboard to {CHART_FOLDER / 'live_dashboard.png'}")

        fig = None
        close_cid = None
        window_closed = False

        def on_close(_event):
            nonlocal window_closed
            window_closed = True

        try:
            while True:
                fig = draw_live_dashboard(
                    tickers,
                    refresh_seconds=args.refresh_seconds,
                    cols=args.cols,
                    fig=fig,
                )

                if show_window and fig is not None and close_cid is None:
                    close_cid = fig.canvas.mpl_connect("close_event", on_close)

                if show_window and fig is not None:
                    if window_closed or not plt.fignum_exists(fig.number):
                        break

                    fig.canvas.draw_idle()
                    fig.canvas.flush_events()
                    plt.pause(0.1)

                    elapsed = 0.0
                    while elapsed < args.refresh_seconds:
                        if window_closed or not plt.fignum_exists(fig.number):
                            break
                        plt.pause(0.2)
                        elapsed += 0.2

                    if window_closed or not plt.fignum_exists(fig.number):
                        break
                else:
                    time.sleep(args.refresh_seconds)
        except KeyboardInterrupt:
            print("\nLive dashboard stopped.")
        finally:
            if not show_window and fig is not None:
                plt.close(fig)
        return

    schwab_prices, schwab_names = find_schwab_data()
    files = sorted(INPUT_FOLDER.glob("*.csv"))
    for idx, file in enumerate(files, start=1):
        create_chart(idx, len(files), file, days_to_plot=args.days, schwab_prices=schwab_prices, schwab_names=schwab_names)


if __name__ == "__main__":
    main()
