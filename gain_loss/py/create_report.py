#!/usr/bin/env python3

import csv
import html
from collections import defaultdict
from datetime import datetime, timedelta
import re
import sys
from pathlib import Path
import webbrowser

try:
    import yfinance as yf
except ImportError:  # pragma: no cover - runtime dependency check
    yf = None

BASE_DIR = Path("/home/dev/stock/gain_loss")
OUTPUT_DIR = BASE_DIR / "output"
INPUT_FILE = OUTPUT_DIR / "gain_loss.csv"
TRANSACTIONS_FILE = OUTPUT_DIR / "transactions.csv"
OUTPUT_FILE = OUTPUT_DIR / "days_held.html"


def esc(value):
    return html.escape(str(value))


def fmt_signed_money(value):
    value = float(value)
    if value < 0:
        return f"({abs(value):,.2f})"
    return f"{value:,.2f}"


def fmt_total(value):
    value = float(value)
    if value < 0:
        return f"({abs(value):,.2f})"
    return f"{value:,.2f}"


def fmt_percent(value):
  value = float(value)
  return f"{value * 100:,.2f}%"


def parse_txn_date(value):
  text = str(value or "")
  match = re.search(r"\d{1,2}/\d{1,2}/\d{4}", text)
  if not match:
    return None
  return datetime.strptime(match.group(0), "%m/%d/%Y").date()


def parse_period_arg(value):
    value = str(value or "").strip()
    for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def parse_money(value):
  text = str(value or "").strip().replace("$", "").replace(",", "")
  if not text:
    return 0.0
  if text.startswith("(") and text.endswith(")"):
    text = "-" + text[1:-1]
  try:
    return float(text)
  except ValueError:
    return 0.0


def load_transaction_records(transactions_file):
    if not transactions_file.exists():
        return []

    records = []
    with open(transactions_file, "r", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for idx, row in enumerate(reader):
            tx_date = parse_txn_date(row.get("Date", ""))
            if tx_date is None:
                continue

            action = str(row.get("Action", "")).strip().upper()
            symbol = str(row.get("Symbol", "")).strip()
            account = str(row.get("AccountId", "")).strip()
            qty = abs(parse_money(row.get("Quantity", "")))
            price = abs(parse_money(row.get("Price", "")))
            fees = abs(parse_money(row.get("Fees & Comm", "")))

            if not symbol or qty <= 0:
                continue

            records.append(
                {
                    "date": tx_date,
                    "action": action,
                    "symbol": symbol,
                    "account": account,
                    "qty": qty,
                    "price": price,
                    "fees": fees,
                    "order": idx,
                }
            )

    def action_priority(action):
        if action == "BUY":
            return 0
        if action == "SELL":
            return 1
        return 2

    records.sort(key=lambda r: (r["date"], action_priority(r["action"]), r["order"]))
    return records


def normalize_account_id(value):
    text = str(value or "").strip()
    match = re.search(r"\.\.\.(\d+)", text)
    if match:
        return f"XXX{match.group(1)}"
    return text


def load_current_positions_cost_basis(positions_file):
    if not positions_file.exists():
        return {}

    positions = {}
    current_account = None
    header = None
    account_symbol_seen = set()

    with open(positions_file, "r", newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        for row in reader:
            if not row:
                continue

            cells = [str(cell or "").strip() for cell in row]
            first = cells[0].strip('"') if cells else ""

            if len(cells) == 1 and first and first not in {"Symbol", "Cash & Cash Investments", "Positions Total"}:
                current_account = normalize_account_id(first)
                header = None
                continue

            if "Symbol" in cells and "Cost/Share" in cells and "Qty (Quantity)" in cells:
                header = {name: idx for idx, name in enumerate(cells)}
                continue

            if header is None or not first or first in {"Cash & Cash Investments", "Positions Total"}:
                continue

            symbol = first
            qty_text = cells[header.get("Qty (Quantity)", -1)] if header.get("Qty (Quantity)", -1) < len(cells) else ""
            cost_text = cells[header.get("Cost/Share", -1)] if header.get("Cost/Share", -1) < len(cells) else ""
            asset_text = cells[header.get("Asset Type", -1)] if header.get("Asset Type", -1) < len(cells) else ""
            if asset_text != "Equity":
                continue
            qty = abs(parse_money(qty_text))
            cost = abs(parse_money(cost_text))
            if qty <= 0 or cost <= 0:
                continue

            key = f"{current_account}|{symbol}" if current_account else symbol
            if key in account_symbol_seen:
                continue
            account_symbol_seen.add(key)
            positions[key] = {"qty": qty, "cost": cost}

    return positions


def yfinance_symbol(symbol):
    normalized = str(symbol or "").strip().upper()
    if normalized in {"BRKB", "BRK.B", "BRK/B", "BRK-B"}:
        return "BRK-B"
    return normalized.replace(".", "-")


def yfinance_symbol_candidates(symbol):
    normalized = str(symbol or "").strip().upper()
    if normalized in {"BRKB", "BRK.B", "BRK/B", "BRK-B"}:
        return ["BRK-B", "BRK.B", "BRK/B", "BRKB"]
    return [yfinance_symbol(normalized)]


def download_close_lookup(symbol, start_date, end_date):
    if yf is None:
        raise SystemExit("ERROR: yfinance is required to compute unrealized gain/loss.")

    fetch_start = (start_date - timedelta(days=30)).isoformat()
    fetch_end = (end_date + timedelta(days=1)).isoformat()
    for candidate in yfinance_symbol_candidates(symbol):
        data = yf.download(
            candidate,
            start=fetch_start,
            end=fetch_end,
            auto_adjust=False,
            actions=False,
            progress=False,
            threads=False,
        )

        if data is None or data.empty or "Close" not in data:
            continue

        close_data = data["Close"]
        if hasattr(close_data, "columns"):
            if len(close_data.columns) == 0:
                continue
            close_data = close_data.iloc[:, 0]

        close_by_day = {}
        for ts, close in close_data.items():
            if close is None:
                continue
            try:
                close_value = float(close)
            except (TypeError, ValueError):
                continue
            if close_value != close_value:
                continue
            close_by_day[getattr(ts, "date", lambda: ts)()] = close_value

        if close_by_day:
            return close_by_day

    return {}


def build_daily_price_lookup(symbols, start_date, end_date):
    price_history = {}
    for symbol in symbols:
        price_history[symbol] = download_close_lookup(symbol, start_date, end_date)

    daily_lookup = {}
    for symbol, close_by_day in price_history.items():
        filled = {}
        last_close = None
        day = start_date
        while day <= end_date:
            if day in close_by_day:
                last_close = close_by_day[day]
            filled[day] = last_close
            day += timedelta(days=1)
        daily_lookup[symbol] = filled

    return daily_lookup


def build_unrealized_market_value_series(records, start_date, end_date):
    positions = load_current_positions_cost_basis(OUTPUT_DIR / "positions.csv")
    if not positions:
        return [], {}

    symbols = sorted({key.split("|", 1)[1] if "|" in key else key for key in positions})
    price_lookup = build_daily_price_lookup(symbols, start_date, end_date)

    series = []
    day = start_date
    while day <= end_date:
        total_unrealized = 0.0
        for key, pos in positions.items():
            symbol = key.split("|", 1)[1] if "|" in key else key
            current_price = price_lookup.get(symbol, {}).get(day)
            if current_price is None:
                continue

            lot_gain_loss = pos["qty"] * (current_price - pos["cost"])
            if lot_gain_loss < 0.0:
                total_unrealized += lot_gain_loss

        series.append(round(total_unrealized, 2))
        day += timedelta(days=1)

    return series, price_lookup


def build_benchmark_series(symbol, start_date, end_date, starting_capital):
    days = (end_date - start_date).days + 1
    if days <= 0:
        return [], None, None
    if starting_capital <= 0:
        return [0.0] * days, None, None

    close_by_day = download_close_lookup(symbol, start_date, end_date)
    if not close_by_day:
        return [0.0] * days, None, None

    filled = {}
    last_close = None
    day = start_date
    while day <= end_date:
        if day in close_by_day:
            last_close = close_by_day[day]
        filled[day] = last_close
        day += timedelta(days=1)

    entry_day = None
    entry_price = None
    day = start_date
    while day <= end_date:
        price = filled.get(day)
        if price is not None and price > 0:
            entry_day = day
            entry_price = float(price)
            break
        day += timedelta(days=1)

    if entry_price is None or entry_price <= 0:
        return [0.0] * days, None, None

    shares = starting_capital / entry_price
    series = []
    day = start_date
    while day <= end_date:
        price = filled.get(day)
        if price is None:
            series.append(0.0)
        else:
            series.append(round(shares * (float(price) - entry_price), 2))
        day += timedelta(days=1)

    return series, entry_day, entry_price


def compute_realized_metrics(transactions_file, start_date, end_date):
    records = load_transaction_records(transactions_file)
    if not records:
        return None

    # Include all account/symbol books so unsold holdings are part of deployed capital.
    all_keys = set()
    for r in records:
        k = f"{r['account']}|{r['symbol']}" if r["account"] else r["symbol"]
        all_keys.add(k)

    if not all_keys:
        return None

    lots = defaultdict(list)
    realized_gain = 0.0
    open_cost_basis = 0.0
    end_of_day_cost_basis = {}
    daily_buy_notional = defaultdict(float)
    daily_sell_notional = defaultdict(float)
    sell_transactions_count = 0

    idx = 0
    while idx < len(records):
        current_day = records[idx]["date"]

        while idx < len(records) and records[idx]["date"] == current_day:
            tx = records[idx]
            lot_key = f"{tx['account']}|{tx['symbol']}" if tx["account"] else tx["symbol"]

            if tx["action"] == "BUY":
                lots[lot_key].append({"qty": tx["qty"], "price": tx["price"]})
                open_cost_basis += tx["qty"] * tx["price"]
                if start_date <= tx["date"] <= end_date:
                    daily_buy_notional[tx["date"]] += tx["qty"] * tx["price"]
                idx += 1
                continue

            if tx["action"] != "SELL":
                idx += 1
                continue

            if start_date <= tx["date"] <= end_date:
                daily_sell_notional[tx["date"]] += tx["qty"] * tx["price"]
                sell_transactions_count += 1

            remaining = tx["qty"]
            lot_idx = 0
            account_lots = lots[lot_key]

            while remaining > 1e-9 and lot_idx < len(account_lots):
                lot = account_lots[lot_idx]
                if lot["qty"] <= 1e-9:
                    account_lots.pop(lot_idx)
                    continue

                matched = min(remaining, lot["qty"])
                if start_date <= tx["date"] <= end_date:
                    fee_share = tx["fees"] * (matched / tx["qty"]) if tx["qty"] > 1e-9 else 0.0
                    realized_gain += matched * (tx["price"] - lot["price"]) - fee_share

                open_cost_basis -= matched * lot["price"]

                lot["qty"] -= matched
                remaining -= matched

                if lot["qty"] <= 1e-9:
                    account_lots.pop(lot_idx)
                else:
                    lot_idx += 1

            idx += 1

        end_of_day_cost_basis[current_day] = max(open_cost_basis, 0.0)

    period_days = max((end_date - start_date).days, 1)
    days_in_period = period_days + 1

    running_cost_basis = 0.0
    total_cost_basis = 0.0
    day = start_date
    while day <= end_date:
        if day in end_of_day_cost_basis:
            running_cost_basis = end_of_day_cost_basis[day]
        total_cost_basis += running_cost_basis
        day += timedelta(days=1)

    avg_all_holdings_cost_basis = total_cost_basis / days_in_period if days_in_period > 0 else 0.0

    trade_days = sorted(set(daily_buy_notional.keys()) | set(daily_sell_notional.keys()))
    if trade_days:
        gross_turnover_total = 0.0
        for day in trade_days:
            gross_turnover_total += daily_buy_notional[day] + daily_sell_notional[day]
        avg_trading_capital = gross_turnover_total / len(trade_days)
    else:
        avg_trading_capital = 0.0

    # Primary denominator: validated daily trading deployment, which aligns with
    # a rotating capital sleeve. Keep all-holdings basis as reference.
    avg_invested_capital = avg_trading_capital if avg_trading_capital > 0 else avg_all_holdings_cost_basis

    if avg_invested_capital <= 0:
        return None

    period_return = realized_gain / avg_invested_capital
    cagr = None
    if period_return > -1.0:
        cagr = (1.0 + period_return) ** (365.25 / period_days) - 1.0

    return {
        "realized_gain": realized_gain,
        "avg_invested_capital": avg_invested_capital,
        "avg_trading_capital": avg_trading_capital,
        "avg_all_holdings_cost_basis": avg_all_holdings_cost_basis,
        "sell_transactions_count": sell_transactions_count,
        "trade_days": len(trade_days),
        "all_keys": len(all_keys),
        "period_days": period_days,
        "period_return": period_return,
        "cagr": cagr,
    }


def build_svg_chart(labels, daily, cumulative):
    if not labels:
        return "<p>No data available for chart.</p>"

    width = 1040
    height = 420
    left = 78
    right = 78
    top = 24
    bottom = 88
    plot_w = width - left - right
    plot_h = height - top - bottom

    min_daily = min(min(daily), 0.0)
    max_daily = max(max(daily), 0.0)
    if abs(max_daily - min_daily) < 1e-9:
        max_daily += 1.0
        min_daily -= 1.0

    raw_min_cum = min(min(cumulative), 0.0)
    raw_max_cum = max(max(cumulative), 0.0)

    # Align the 0-value across both axes to reduce visual confusion.
    # Daily zero location ratio from top (0..1):
    #   r_top = max_daily / (max_daily - min_daily)
    daily_span = max_daily - min_daily
    r_top = max_daily / daily_span if daily_span > 1e-9 else 0.5

    if 1e-6 < r_top < 1 - 1e-6:
        # Build cumulative bounds as [-k*(1-r), k*r] so y_cum(0) aligns with y_daily(0).
        need_from_max = raw_max_cum / r_top if r_top > 1e-9 else 0.0
        need_from_min = (-raw_min_cum) / (1.0 - r_top) if (1.0 - r_top) > 1e-9 else 0.0
        k = max(need_from_max, need_from_min, 1.0)
        max_cum = k * r_top
        min_cum = -k * (1.0 - r_top)
    else:
        # Degenerate daily range; fall back to natural cumulative bounds including zero.
        min_cum = raw_min_cum
        max_cum = raw_max_cum
        if abs(max_cum - min_cum) < 1e-9:
            max_cum += 1.0
            min_cum -= 1.0

    def y_daily(v):
        return top + (max_daily - v) * plot_h / (max_daily - min_daily)

    def y_cum(v):
        return top + (max_cum - v) * plot_h / (max_cum - min_cum)

    def tick_values(min_value, max_value, step):
        if step <= 0:
            return []
        start = int(min_value // step) * step
        if start > min_value:
            start -= step
        end = int(-(-max_value // step)) * step
        values = []
        current = start
        while current <= end:
            values.append(current)
            current += step
        return values

    n = len(labels)
    step = plot_w / max(n, 1)
    bar_w = max(2.0, step * 0.68)
    x_mid = [left + (i + 0.5) * step for i in range(n)]
    y_zero = y_daily(0.0)

    svg = []
    svg.append(
        f'<svg viewBox="0 0 {width} {height}" width="100%" height="100%" role="img" aria-label="Daily and cumulative gain loss chart">'
    )
    svg.append(f'<rect x="0" y="0" width="{width}" height="{height}" fill="#ffffff" />')

    svg.append(
        f'<rect x="{left}" y="{top}" width="{plot_w}" height="{plot_h}" fill="#ffffff" stroke="#d1d5db"/>'
    )
    svg.append(
        f'<line x1="{left}" y1="{y_zero:.2f}" x2="{left + plot_w}" y2="{y_zero:.2f}" stroke="#9ca3af" stroke-dasharray="4 3"/>'
    )

    for x, label, value in zip(x_mid, labels, daily):
        y = y_daily(value)
        h = abs(y - y_zero)
        y_top = min(y, y_zero)
        color = "#16a34a" if value >= 0 else "#dc2626"
        svg.append(
            f'<rect x="{x - bar_w / 2:.2f}" y="{y_top:.2f}" width="{bar_w:.2f}" height="{max(h, 1):.2f}" fill="{color}">'
            f'<title>{esc(label)} Daily {value:,.2f}</title></rect>'
        )

    line_points = " ".join(f"{x:.2f},{y_cum(v):.2f}" for x, v in zip(x_mid, cumulative))
    svg.append(f'<polyline fill="none" stroke="#1d4ed8" stroke-width="2.5" points="{line_points}"/>')
    for x, label, v in zip(x_mid, labels, cumulative):
        y = y_cum(v)
        svg.append(
            f'<circle cx="{x:.2f}" cy="{y:.2f}" r="2.3" fill="#1d4ed8"><title>{esc(label)} Cumulative {v:,.2f}</title></circle>'
        )

    for val in tick_values(min_daily, max_daily, 1000):
        y = y_daily(val)
        is_major = (val % 5000) == 0
        svg.append(
            f'<line x1="{left - 5 if is_major else left - 3}" y1="{y:.2f}" x2="{left}" y2="{y:.2f}" stroke="#6b7280" stroke-width="{1.4 if is_major else 1}"/>'
        )
        if is_major:
            svg.append(
                f'<text x="{left - 8}" y="{y + 4:.2f}" text-anchor="end" font-size="11" fill="#374151">{val:,.0f}</text>'
            )

    for val in tick_values(min_cum, max_cum, 1000):
        y = y_cum(val)
        is_major = (val % 5000) == 0
        svg.append(
            f'<line x1="{left + plot_w}" y1="{y:.2f}" x2="{left + plot_w + (5 if is_major else 3)}" y2="{y:.2f}" stroke="#6b7280" stroke-width="{1.4 if is_major else 1}"/>'
        )
        if is_major:
            svg.append(
                f'<text x="{left + plot_w + 8}" y="{y + 4:.2f}" text-anchor="start" font-size="11" fill="#1e40af">{val:,.0f}</text>'
            )

    # Explicit zero ticks on both axes to make alignment obvious.
    y_zero_cum = y_cum(0.0)
    svg.append(f'<line x1="{left - 6}" y1="{y_zero:.2f}" x2="{left}" y2="{y_zero:.2f}" stroke="#374151"/>')
    svg.append(f'<text x="{left - 10}" y="{y_zero + 4:.2f}" text-anchor="end" font-size="11" fill="#374151">0</text>')
    svg.append(f'<line x1="{left + plot_w}" y1="{y_zero_cum:.2f}" x2="{left + plot_w + 6}" y2="{y_zero_cum:.2f}" stroke="#1e40af"/>')
    svg.append(f'<text x="{left + plot_w + 10}" y="{y_zero_cum + 4:.2f}" text-anchor="start" font-size="11" fill="#1e40af">0</text>')

    tick_count = min(10, n)
    if tick_count <= 1:
        idxs = [0]
    else:
        idxs = sorted(set(round(i * (n - 1) / (tick_count - 1)) for i in range(tick_count)))

    for i in idxs:
        x = x_mid[i]
        label = labels[i]
        svg.append(
            f'<line x1="{x:.2f}" y1="{top + plot_h}" x2="{x:.2f}" y2="{top + plot_h + 4}" stroke="#6b7280"/>'
        )
        svg.append(
            f'<text x="{x:.2f}" y="{top + plot_h + 20}" text-anchor="end" transform="rotate(-35 {x:.2f} {top + plot_h + 20})" font-size="11" fill="#374151">{esc(label)}</text>'
        )

    svg.append(
        f'<text x="18" y="{top + plot_h / 2:.2f}" transform="rotate(-90 18 {top + plot_h / 2:.2f})" text-anchor="middle" font-size="12" fill="#374151">Daily Gain/Loss ($)</text>'
    )
    svg.append(
        f'<text x="{width - 18}" y="{top + plot_h / 2:.2f}" transform="rotate(90 {width - 18} {top + plot_h / 2:.2f})" text-anchor="middle" font-size="12" fill="#1e40af">Cumulative Gain/Loss ($)</text>'
    )
    svg.append(
        f'<rect x="{left}" y="6" width="10" height="10" fill="#16a34a"/><text x="{left + 14}" y="15" font-size="11" fill="#374151">Daily Gain/Loss (green=positive, red=negative)</text>'
    )
    svg.append(
        f'<line x1="{left + 285}" y1="11" x2="{left + 315}" y2="11" stroke="#1d4ed8" stroke-width="2.5"/><text x="{left + 320}" y="15" font-size="11" fill="#374151">Cumulative Gain/Loss</text>'
    )

    svg.append("</svg>")
    return "".join(svg)


def build_cumulative_compare_chart(
    labels,
    realized_cumulative,
    unrealized_cumulative_loss,
    net_cumulative,
    voo_benchmark,
):
    if not labels:
        return "<p>No data available for chart.</p>"

    width = 1040
    height = 420
    left = 78
    right = 40
    top = 24
    bottom = 88
    plot_w = width - left - right
    plot_h = height - top - bottom

    all_values = realized_cumulative + unrealized_cumulative_loss + net_cumulative + voo_benchmark + [0.0]
    min_y = min(all_values)
    max_y = max(all_values)
    if abs(max_y - min_y) < 1e-9:
        max_y += 1.0
        min_y -= 1.0
    else:
        pad = (max_y - min_y) * 0.08
        max_y += pad
        min_y -= pad

    def y_val(v):
        return top + (max_y - v) * plot_h / (max_y - min_y)

    n = len(labels)
    step = plot_w / max(n, 1)
    x_mid = [left + (i + 0.5) * step for i in range(n)]
    y_zero = y_val(0.0)

    def line_points(values):
        return " ".join(f"{x:.2f},{y_val(v):.2f}" for x, v in zip(x_mid, values))

    def tick_values(min_value, max_value, step):
        if step <= 0:
            return []
        start = int(min_value // step) * step
        if start > min_value:
            start -= step
        end = int(-(-max_value // step)) * step
        values = []
        current = start
        while current <= end:
            values.append(current)
            current += step
        return values

    svg = []
    svg.append(
        f'<svg viewBox="0 0 {width} {height}" width="100%" height="100%" role="img" aria-label="Cumulative realized, unrealized loss, and net gain chart">'
    )
    svg.append(f'<rect x="0" y="0" width="{width}" height="{height}" fill="#ffffff" />')
    svg.append(
        f'<rect x="{left}" y="{top}" width="{plot_w}" height="{plot_h}" fill="#ffffff" stroke="#d1d5db"/>'
    )
    svg.append(
        f'<line x1="{left}" y1="{y_zero:.2f}" x2="{left + plot_w}" y2="{y_zero:.2f}" stroke="#9ca3af" stroke-dasharray="4 3"/>'
    )

    for val in tick_values(min_y, max_y, 1000):
        y = y_val(val)
        is_major = (val % 5000) == 0
        svg.append(
            f'<line x1="{left - 5 if is_major else left - 3}" y1="{y:.2f}" x2="{left}" y2="{y:.2f}" stroke="#6b7280" stroke-width="{1.4 if is_major else 1}"/>'
        )
        svg.append(
            f'<line x1="{left}" y1="{y:.2f}" x2="{left + plot_w}" y2="{y:.2f}" stroke="{('#e5e7eb' if is_major else '#f3f4f6')}" stroke-width="{1.2 if is_major else 1}"/>'
        )
        if is_major:
            svg.append(
                f'<text x="{left - 8}" y="{y + 4:.2f}" text-anchor="end" font-size="11" fill="#374151">{val:,.0f}</text>'
            )

    y_zero_cum = y_val(0.0)
    svg.append(f'<line x1="{left - 6}" y1="{y_zero_cum:.2f}" x2="{left}" y2="{y_zero_cum:.2f}" stroke="#374151"/>')
    svg.append(f'<text x="{left - 10}" y="{y_zero_cum + 4:.2f}" text-anchor="end" font-size="11" fill="#374151">0</text>')
    svg.append(f'<line x1="{left + plot_w}" y1="{y_zero_cum:.2f}" x2="{left + plot_w + 6}" y2="{y_zero_cum:.2f}" stroke="#1e40af"/>')
    svg.append(f'<text x="{left + plot_w + 10}" y="{y_zero_cum + 4:.2f}" text-anchor="start" font-size="11" fill="#1e40af">0</text>')

    lines = [
        (realized_cumulative, "#1d4ed8", "Realized Cumulative"),
        (unrealized_cumulative_loss, "#dc2626", "Unrealized Cumulative Gain/Loss"),
        (net_cumulative, "#059669", "Net Cumulative (Realized + Unrealized Gain/Loss)"),
        (voo_benchmark, "#b45309", "VOO Gain/Loss (Avg Trading Capital Benchmark)"),
    ]

    for values, color, label in lines:
        svg.append(f'<polyline fill="none" stroke="{color}" stroke-width="2.5" points="{line_points(values)}"/>')
        for x, date_label, v in zip(x_mid, labels, values):
            y = y_val(v)
            svg.append(
                f'<circle cx="{x:.2f}" cy="{y:.2f}" r="2.1" fill="{color}"><title>{esc(date_label)} {esc(label)} {v:,.2f}</title></circle>'
            )

    tick_count = min(10, n)
    if tick_count <= 1:
        idxs = [0]
    else:
        idxs = sorted(set(round(i * (n - 1) / (tick_count - 1)) for i in range(tick_count)))

    for i in idxs:
        x = x_mid[i]
        label = labels[i]
        svg.append(
            f'<line x1="{x:.2f}" y1="{top + plot_h}" x2="{x:.2f}" y2="{top + plot_h + 4}" stroke="#6b7280"/>'
        )
        svg.append(
            f'<text x="{x:.2f}" y="{top + plot_h + 20}" text-anchor="end" transform="rotate(-35 {x:.2f} {top + plot_h + 20})" font-size="11" fill="#374151">{esc(label)}</text>'
        )

    svg.append(
        f'<text x="18" y="{top + plot_h / 2:.2f}" transform="rotate(-90 18 {top + plot_h / 2:.2f})" text-anchor="middle" font-size="12" fill="#374151">Cumulative Gain/Loss ($)</text>'
    )
    svg.append(
        f'<line x1="{left}" y1="11" x2="{left + 30}" y2="11" stroke="#1d4ed8" stroke-width="2.5"/><text x="{left + 36}" y="15" font-size="11" fill="#374151">Realized Cumulative</text>'
    )
    svg.append(
        f'<line x1="{left + 230}" y1="11" x2="{left + 260}" y2="11" stroke="#dc2626" stroke-width="2.5"/><text x="{left + 266}" y="15" font-size="11" fill="#374151">Unrealized Cumulative Gain/Loss</text>'
    )
    svg.append(
        f'<line x1="{left + 520}" y1="11" x2="{left + 550}" y2="11" stroke="#059669" stroke-width="2.5"/><text x="{left + 556}" y="15" font-size="11" fill="#374151">Net Cumulative</text>'
    )
    svg.append(
        f'<line x1="{left + 730}" y1="11" x2="{left + 760}" y2="11" stroke="#b45309" stroke-width="2.5"/><text x="{left + 766}" y="15" font-size="11" fill="#374151">VOO Benchmark</text>'
    )

    svg.append("</svg>")
    return "".join(svg)


if not INPUT_FILE.exists():
    raise SystemExit(f"ERROR: Input file not found:\n{INPUT_FILE}")

with open(INPUT_FILE, "r", newline="", encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)
    rows = list(reader)

if not rows:
    raise SystemExit("ERROR: gain_loss.csv contains no data.")

for row in rows:
    row["Avg_Days_Held"] = int(float(row.get("Avg_Days_Held", 0) or 0))
    row["Gain_Loss"] = float(row.get("Gain_Loss", 0.0) or 0.0)

by_date = defaultdict(list)
for row in rows:
    by_date[row["Date"]].append(row)

for key in by_date:
    by_date[key].sort(key=lambda item: item["Symbol"])

report_date = datetime.now().strftime("%B %-d, %Y")
try:
    report_time = datetime.now().strftime("%-I:%M %p")
except ValueError:
    report_time = datetime.now().strftime("%I:%M %p")

total_gain = sum(float(r["Gain_Loss"]) for r in rows)

sorted_gain_dates = sorted(by_date.keys())
period_start = datetime.strptime(sorted_gain_dates[0], "%Y-%m-%d").date()
period_end = datetime.strptime(sorted_gain_dates[-1], "%Y-%m-%d").date()
if len(sys.argv) >= 3:
    arg_start = parse_period_arg(sys.argv[1])
    arg_end = parse_period_arg(sys.argv[2])
    if arg_start is not None and arg_end is not None:
        period_start = arg_start
        period_end = arg_end

if period_start > period_end:
    period_start, period_end = period_end, period_start

chart_labels = []
daily_totals = []
cumulative_totals = []
running_total = 0.0
day = period_start
while day <= period_end:
    day_key = day.strftime("%Y-%m-%d")
    day_total = sum(float(r["Gain_Loss"]) for r in by_date.get(day_key, []))
    running_total += day_total
    chart_labels.append(day_key)
    daily_totals.append(round(day_total, 2))
    cumulative_totals.append(round(running_total, 2))
    day += timedelta(days=1)

chart_svg = build_svg_chart(chart_labels, daily_totals, cumulative_totals)

realized_metrics = compute_realized_metrics(
    TRANSACTIONS_FILE,
    period_start,
    period_end,
)

transaction_records = load_transaction_records(TRANSACTIONS_FILE)
unrealized_market_value_series, price_lookup = build_unrealized_market_value_series(
    transaction_records,
    period_start,
    period_end,
)
net_cumulative = [
    round(realized + unrealized, 2)
    for realized, unrealized in zip(cumulative_totals, unrealized_market_value_series)
]
benchmark_capital = realized_metrics["avg_trading_capital"] if realized_metrics else 0.0
voo_benchmark_series, voo_entry_day, voo_entry_price = build_benchmark_series(
    "VOO",
    period_start,
    period_end,
    benchmark_capital,
)
compare_chart_svg = build_cumulative_compare_chart(
    chart_labels,
    cumulative_totals,
    unrealized_market_value_series,
    net_cumulative,
    voo_benchmark_series,
)

if realized_metrics and realized_metrics["cagr"] is not None:
    voo_summary_text = (
        f"VOO Benchmark Gain/Loss (same avg trading capital): {fmt_total(voo_benchmark_series[-1] if voo_benchmark_series else 0.0)}"
    )
    if voo_entry_day is not None and voo_entry_price is not None:
        voo_summary_text += f" (entry {voo_entry_day.isoformat()} @ {voo_entry_price:,.2f})"
else:
    voo_summary_text = ""

sections_html = []
for date_key in sorted(by_date):
    day_rows = by_date[date_key]
    day_total = sum(float(r["Gain_Loss"]) for r in day_rows)

    item_rows = []
    for item in day_rows:
        item_rows.append(
            f"""
            <tr>
                <td class=\"symbol\">{esc(item['Symbol'])}</td>
                <td class=\"days\">{item['Avg_Days_Held']}</td>
                <td class=\"gain\">{fmt_signed_money(item['Gain_Loss'])}</td>
            </tr>
            """
        )

    sections_html.append(
        f"""
        <div class=\"date-block\">
            <div class=\"date-label\">Date {esc(date_key)}:</div>
            <table class=\"day-table\" cellspacing=\"0\" cellpadding=\"0\">
                <thead>
                    <tr>
                        <th>Symbol</th>
                        <th>Avg_Days_Held</th>
                        <th>Gain_Loss</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(item_rows)}
                </tbody>
            </table>
            <div class=\"day-total\">Total &nbsp; {fmt_total(day_total)}</div>
        </div>
        """
    )

page = f"""<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"UTF-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />
  <title>Stock Gain / Loss</title>
  <style>
    body {{
      margin: 0;
      padding: 30px;
      background: #f3f4f6;
      font-family: Arial, sans-serif;
      color: #111827;
    }}
    .container {{
      max-width: 1100px;
      margin: 0 auto;
      background: white;
      border-radius: 12px;
      box-shadow: 0 4px 16px rgba(0,0,0,0.08);
      padding: 24px 28px;
    }}
    h1 {{
      margin: 0 0 10px 0;
      font-size: 2rem;
    }}
    .subtitle {{
      margin-bottom: 22px;
      color: #6b7280;
      font-size: 14px;
    }}
    .chart-block {{
      border-top: 1px solid #e5e7eb;
      margin-bottom: 24px;
      padding-top: 16px;
    }}
        .summary-block {{
            margin: 10px 0 18px 0;
            padding: 12px 14px;
            background: #f9fafb;
            border: 1px solid #e5e7eb;
            border-radius: 8px;
        }}
        .summary-title {{
            font-weight: 700;
            margin-bottom: 6px;
            color: #111827;
        }}
    .chart-title {{
      font-weight: 700;
      font-size: 1.1rem;
      margin: 0 0 10px 0;
    }}
    .chart-wrap {{
      position: relative;
      width: 100%;
      min-height: 320px;
      height: 420px;
      overflow-x: auto;
    }}
    .date-block {{
      margin-bottom: 26px;
      border-top: 1px solid #e5e7eb;
      padding-top: 18px;
    }}
    .date-label {{
      font-weight: 700;
      font-size: 1.2rem;
      margin-bottom: 8px;
    }}
    .day-table {{
      width: 100%;
      border-collapse: collapse;
      table-layout: fixed;
    }}
    th, td {{
      padding: 8px 12px;
      text-align: left;
      border-bottom: 1px solid #e5e7eb;
    }}
    th {{
      font-size: 12px;
      letter-spacing: 0.04em;
      text-transform: uppercase;
      color: #4b5563;
      background: #f9fafb;
    }}
    .symbol {{
      width: 50%;
      font-weight: 600;
    }}
    .days {{
      width: 20%;
      text-align: right;
      font-variant-numeric: tabular-nums;
    }}
    .gain {{
      width: 30%;
      text-align: right;
      font-variant-numeric: tabular-nums;
      font-weight: 700;
    }}
    .day-total {{
      margin-top: 8px;
      text-align: right;
      font-weight: 700;
      font-size: 1.05rem;
    }}
    .period-total {{
      margin-top: 20px;
      border-top: 2px solid #111827;
      padding-top: 12px;
      text-align: right;
      font-size: 1.15rem;
      font-weight: 700;
    }}
    .period-metrics {{
      margin-top: 8px;
      text-align: right;
      color: #374151;
      font-size: 0.95rem;
      line-height: 1.5;
    }}
    @media (max-width: 768px) {{
      body {{
        padding: 16px;
      }}
      .container {{
        padding: 16px;
      }}
      .chart-wrap {{
        height: 340px;
      }}
    }}
  </style>
</head>
<body>
  <div class=\"container\">
    <h1>Stock Gain / Loss</h1>
    <div class=\"subtitle\">{esc(report_date)} at {esc(report_time)}</div>
        <div class="summary-block">
            <div class="summary-title">Summary Statistics</div>
            <div class="period-total">Total Gain for Period Entered &nbsp; {fmt_total(total_gain)}</div>
            <div class="period-metrics">
                {f"Realized Return (validated trading-capital basis): {fmt_percent(realized_metrics['period_return'])}<br/>CAGR (annualized over {realized_metrics['period_days']} calendar days): {fmt_percent(realized_metrics['cagr'])}<br/>Average Trading Capital (daily gross buy+sell notional): {fmt_total(realized_metrics['avg_trading_capital'])}<br/>Completed Transactions (sell count): {realized_metrics['sell_transactions_count']}<br/>Trading Days in Period: {realized_metrics['trade_days']}<br/>Account/Symbol Books Included: {realized_metrics['all_keys']}<br/>{voo_summary_text}" if realized_metrics and realized_metrics['cagr'] is not None else "CAGR unavailable for this period."}
            </div>
        </div>
    <div class=\"chart-block\">
            <div class="chart-title">Cumulative Realized vs Unrealized Loss vs Net vs VOO Benchmark</div>
      <div class=\"chart-wrap\">
        {chart_svg}
      </div>
    </div>
        <div class=\"chart-block\">
            <div class=\"chart-title\">Cumulative Realized vs Unrealized Loss vs Net</div>
            <div class=\"chart-wrap\">
                {compare_chart_svg}
            </div>
        </div>
    {''.join(sections_html)}
  </div>
</body>
</html>
"""

OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    f.write(page)

print()
print("HTML report created:")
print(OUTPUT_FILE)
print()

webbrowser.open(OUTPUT_FILE.resolve().as_uri())
