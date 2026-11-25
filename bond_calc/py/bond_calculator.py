#!/usr/bin/env python3
"""
Bond Calculator
---------------
Reads a Schwab-style positions export, filters Asset Type == 'Fixed Income',
generates remaining coupon + principal cash flows by yyyy_mm, computes
YTM and CAGR for each bond and for the aggregated portfolio, then writes
tabular Excel output and a stacked-column + cumulative chart.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from dataclasses import dataclass, field
from datetime import date, datetime
from io import StringIO
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.optimize import brentq

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
VALUATION_DATE = date(2026, 11, 24)  # as-of date from the positions header
DAY_COUNT = 365.25                   # for year fractions / CAGR


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------
@dataclass
class Bond:
    symbol: str
    description: str
    face: float                  # par / face value (Qty for Treasuries)
    clean_price: float           # current price as % of par
    cost_per_share: float        # cost basis price as % of par
    market_value: float
    cost_basis: float
    coupon_rate: float           # annual coupon rate (decimal), 0 for bills
    maturity: date
    frequency: int = 2           # semi-annual for notes
    account: str = ""

    # computed later
    cashflows: Dict[str, float] = field(default_factory=dict)  # yyyy_mm -> amount
    ytm: float = 0.0
    cagr: float = 0.0
    years_to_mat: float = 0.0

    @property
    def is_zero(self) -> bool:
        return self.coupon_rate <= 0.0


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------
def parse_money(val: str) -> float:
    """Parse '$1,234.56' or 'N/A' / '--' / empty -> float or nan."""
    if val is None:
        return float("nan")
    s = str(val).strip().replace("$", "").replace(",", "").replace("%", "")
    if s in ("", "--", "N/A", "n/a", "-"):
        return float("nan")
    try:
        return float(s)
    except ValueError:
        return float("nan")


def extract_coupon_and_maturity(desc: str) -> Tuple[float, Optional[date]]:
    """
    Pull coupon rate and maturity date from typical Schwab Treasury descriptions.
    Examples:
      "US TREASURY BILL27U S T BILL DUE 02/02/27"
      "US TREASU NT 4.875%10/30UST NOTE DUE 10/31/30"
      "US TREASUR NT 4.5%12/31UST NOTE DUE 12/31/31"
    """
    coupon = 0.0
    m = re.search(r"(\d+\.?\d*)\s*%", desc)
    if m:
        coupon = float(m.group(1)) / 100.0

    maturity = None
    m = re.search(r"DUE\s+(\d{1,2})/(\d{1,2})/(\d{2,4})", desc, re.IGNORECASE)
    if m:
        mo, dy, yr = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if yr < 100:
            yr += 2000
        try:
            maturity = date(yr, mo, dy)
        except ValueError:
            maturity = None
    return coupon, maturity


def csv_reader(lines):
    """Minimal CSV reader that respects quotes."""
    return csv.reader(StringIO("\n".join(lines)))


def parse_positions_text(text: str) -> List[Bond]:
    """
    Parse the multi-account positions dump.
    Keeps only rows where the last column (Asset Type) == 'Fixed Income'.
    """
    bonds: List[Bond] = []
    current_account = ""
    lines = text.strip().splitlines()

    for raw in lines:
        line = raw.strip()
        if not line:
            continue

        # Account header lines look like "Roth_Tony ...497" or "Indiv_Tony ...729"
        if re.match(r"^[A-Za-z].*\.\.\.\d+$", line) or (
            line.startswith('"') is False and "..." in line and not line.startswith("Symbol")
        ):
            current_account = line.strip('"')
            continue

        # Skip pure header rows
        if line.startswith('"Symbol"') or line.startswith("Symbol,"):
            continue

        # CSV-ish row – use proper csv module (handles quotes & trailing commas)
        try:
            parts = list(csv_reader([line]))[0]
        except Exception:
            parts = [p.strip().strip('"') for p in line.split(",")]

        # strip trailing empty fields caused by trailing comma
        while parts and parts[-1].strip() == "":
            parts.pop()

        if len(parts) < 23:
            continue

        asset_type = parts[-1].strip().strip('"')
        if asset_type != "Fixed Income":
            continue

        symbol = parts[0].strip().strip('"')
        description = parts[1].strip().strip('"')
        qty = parse_money(parts[4])
        price = parse_money(parts[5])
        cost_share = parse_money(parts[6])
        mkt_val = parse_money(parts[9])
        cost_basis = parse_money(parts[12])

        if np.isnan(qty) or qty <= 0:
            continue

        coupon, maturity = extract_coupon_and_maturity(description)
        if maturity is None:
            print(f"WARNING: could not parse maturity for {symbol}: {description}", file=sys.stderr)
            continue

        # For Treasuries Qty is face value in dollars
        face = qty
        if np.isnan(cost_share) and not np.isnan(cost_basis) and face > 0:
            cost_share = (cost_basis / face) * 100.0

        bonds.append(
            Bond(
                symbol=symbol,
                description=description,
                face=face,
                clean_price=price if not np.isnan(price) else 100.0,
                cost_per_share=cost_share if not np.isnan(cost_share) else price,
                market_value=mkt_val if not np.isnan(mkt_val) else face * price / 100.0,
                cost_basis=cost_basis if not np.isnan(cost_basis) else face * cost_share / 100.0,
                coupon_rate=coupon,
                maturity=maturity,
                account=current_account,
            )
        )
    return bonds


# ---------------------------------------------------------------------------
# Cash-flow generation
# ---------------------------------------------------------------------------
def generate_coupon_dates(maturity: date, frequency: int, valuation: date) -> List[date]:
    """Generate remaining coupon dates up to and including maturity (semi-annual)."""
    if frequency <= 0:
        return [maturity]

    months = 12 // frequency
    dates = []
    d = maturity
    while d > valuation:
        dates.append(d)
        year = d.year
        month = d.month - months
        while month <= 0:
            month += 12
            year -= 1
        try:
            d = date(year, month, d.day)
        except ValueError:
            import calendar
            last = calendar.monthrange(year, month)[1]
            d = date(year, month, min(d.day, last))
    dates.reverse()
    return dates


def build_cashflows(bond: Bond, valuation: date = VALUATION_DATE) -> Dict[str, float]:
    """
    Return dict yyyy_mm -> cash amount received in that month.
    Includes final principal + last coupon on maturity month.
    """
    cfs: Dict[str, float] = {}
    if bond.maturity <= valuation:
        return cfs

    if bond.is_zero:
        key = bond.maturity.strftime("%Y_%m")
        cfs[key] = bond.face
        return cfs

    coupon_dates = generate_coupon_dates(bond.maturity, bond.frequency, valuation)
    periodic_coupon = bond.face * bond.coupon_rate / bond.frequency

    for d in coupon_dates:
        key = d.strftime("%Y_%m")
        cfs[key] = cfs.get(key, 0.0) + periodic_coupon

    mat_key = bond.maturity.strftime("%Y_%m")
    cfs[mat_key] = cfs.get(mat_key, 0.0) + bond.face
    return cfs


# ---------------------------------------------------------------------------
# Yield / CAGR calculations
# ---------------------------------------------------------------------------
def year_fraction(d1: date, d2: date) -> float:
    return (d2 - d1).days / DAY_COUNT


def price_from_ytm(bond: Bond, ytm: float, valuation: date) -> float:
    """
    Dirty price (as % of par) given annual YTM with semi-annual compounding
    (standard Treasury convention approximation).
    """
    if bond.is_zero:
        t = year_fraction(valuation, bond.maturity)
        if t <= 0:
            return 100.0
        return 100.0 / ((1 + ytm / 2) ** (2 * t))

    pv = 0.0
    cfs = bond.cashflows
    for key, amt in cfs.items():
        y, m = map(int, key.split("_"))
        cf_date = date(y, m, min(15, 28))
        if cf_date <= valuation:
            continue
        t = year_fraction(valuation, cf_date)
        pv += amt / ((1 + ytm / 2) ** (2 * t))
    return (pv / bond.face) * 100.0


def solve_ytm(bond: Bond, target_price: float, valuation: date) -> float:
    """Solve for YTM that makes model price == target_price (clean ≈ dirty)."""
    if bond.maturity <= valuation:
        return 0.0

    def objective(y: float) -> float:
        return price_from_ytm(bond, y, valuation) - target_price

    try:
        return brentq(objective, -0.05, 0.30, xtol=1e-8)
    except ValueError:
        if bond.is_zero:
            t = year_fraction(valuation, bond.maturity)
            if t <= 0 or target_price <= 0:
                return 0.0
            return (100.0 / target_price) ** (1 / t) - 1.0
        return float("nan")


def compute_cagr(bond: Bond, valuation: date) -> float:
    """
    CAGR from current cost basis to maturity, treating all future cash flows
    as the terminal value received (i.e. the IRR assuming purchase today at cost).
    """
    return solve_ytm(bond, bond.cost_per_share, valuation)


def portfolio_irr(cfs: Dict[str, float], initial_outlay: float, valuation: date) -> float:
    """
    IRR of the aggregated cash-flow stream given an initial market (or cost) outlay.
    Returns annualized rate.
    """
    if initial_outlay <= 0:
        return float("nan")

    times = []
    amounts = []
    for key in sorted(cfs.keys()):
        y, m = map(int, key.split("_"))
        cf_date = date(y, m, 15)
        t = year_fraction(valuation, cf_date)
        if t > 0 and cfs[key] != 0:
            times.append(t)
            amounts.append(cfs[key])

    if not times:
        return 0.0

    def npv(r: float) -> float:
        total = -initial_outlay
        for t, a in zip(times, amounts):
            total += a / ((1 + r / 2) ** (2 * t))
        return total

    try:
        return brentq(npv, -0.05, 0.30, xtol=1e-8)
    except ValueError:
        return float("nan")


# ---------------------------------------------------------------------------
# Main processing
# ---------------------------------------------------------------------------
def process_bonds(bonds: List[Bond], valuation: date = VALUATION_DATE) -> Tuple[List[Bond], Dict[str, float]]:
    """Populate cashflows, YTM, CAGR for each bond; return also aggregated CF dict."""
    agg: Dict[str, float] = {}
    for b in bonds:
        b.cashflows = build_cashflows(b, valuation)
        b.years_to_mat = year_fraction(valuation, b.maturity)
        b.ytm = solve_ytm(b, b.clean_price, valuation)
        b.cagr = compute_cagr(b, valuation)
        for k, v in b.cashflows.items():
            agg[k] = agg.get(k, 0.0) + v
    return bonds, agg


def make_cashflow_table(bonds: List[Bond], agg: Dict[str, float]) -> pd.DataFrame:
    """Wide table: rows = yyyy_mm, columns = each bond + Total + Cumulative."""
    all_periods = sorted(set().union(*(b.cashflows.keys() for b in bonds), agg.keys()))
    data = {}
    for b in bonds:
        label = f"{b.symbol}"
        data[label] = [b.cashflows.get(p, 0.0) for p in all_periods]
    data["Total"] = [agg.get(p, 0.0) for p in all_periods]
    df = pd.DataFrame(data, index=all_periods)
    df.index.name = "Period (yyyy_mm)"
    df["Cumulative"] = df["Total"].cumsum()
    return df


def make_summary_table(bonds: List[Bond], agg: Dict[str, float], valuation: date) -> pd.DataFrame:
    rows = []
    for b in bonds:
        rows.append(
            {
                "Symbol": b.symbol,
                "Account": b.account,
                "Description": b.description[:50],
                "Face": b.face,
                "Coupon %": b.coupon_rate * 100,
                "Maturity": b.maturity.isoformat(),
                "Years to Mat": round(b.years_to_mat, 3),
                "Clean Price": b.clean_price,
                "Market Value": round(b.market_value, 2),
                "Cost Basis": round(b.cost_basis, 2),
                "YTM (mkt) %": round(b.ytm * 100, 3),
                "CAGR (cost) %": round(b.cagr * 100, 3),
            }
        )

    total_mv = sum(b.market_value for b in bonds)
    total_cost = sum(b.cost_basis for b in bonds)
    port_ytm = portfolio_irr(agg, total_mv, valuation)
    port_cagr = portfolio_irr(agg, total_cost, valuation)
    rows.append(
        {
            "Symbol": "PORTFOLIO",
            "Account": "",
            "Description": "Aggregated Fixed Income",
            "Face": sum(b.face for b in bonds),
            "Coupon %": "",
            "Maturity": "",
            "Years to Mat": "",
            "Clean Price": "",
            "Market Value": round(total_mv, 2),
            "Cost Basis": round(total_cost, 2),
            "YTM (mkt) %": round(port_ytm * 100, 3) if not np.isnan(port_ytm) else "",
            "CAGR (cost) %": round(port_cagr * 100, 3) if not np.isnan(port_cagr) else "",
        }
    )
    return pd.DataFrame(rows)


def plot_cashflows(df: pd.DataFrame, bonds: List[Bond], out_path: Path) -> None:
    """
    Vertical stacked column chart of each bond's CF by period,
    with cumulative total on secondary axis.
    """
    periods = df.index.tolist()
    bond_cols = [c for c in df.columns if c not in ("Total", "Cumulative")]

    fig, ax1 = plt.subplots(figsize=(14, 7))

    bottom = np.zeros(len(periods))
    colors = plt.cm.tab10(np.linspace(0, 1, max(len(bond_cols), 1)))
    for i, col in enumerate(bond_cols):
        vals = df[col].values.astype(float)
        ax1.bar(periods, vals, bottom=bottom, label=col, color=colors[i % len(colors)], width=0.7)
        bottom += vals

    ax1.set_xlabel("Period (yyyy_mm)")
    ax1.set_ylabel("Cash Flow ($)")
    ax1.set_title("Bond Cash Flows by Period (Stacked) + Cumulative")
    ax1.tick_params(axis="x", rotation=45)
    ax1.legend(loc="upper left", fontsize=8)
    ax1.grid(axis="y", alpha=0.3)

    ax2 = ax1.twinx()
    ax2.plot(periods, df["Cumulative"].values, color="black", linewidth=2.0, marker="o", markersize=4, label="Cumulative")
    ax2.set_ylabel("Cumulative Cash Flow ($)")
    ax2.legend(loc="upper right")

    fig.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Chart written: {out_path}")


def write_excel(
    summary: pd.DataFrame,
    cf_table: pd.DataFrame,
    bonds: List[Bond],
    out_path: Path,
) -> None:
    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        summary.to_excel(writer, sheet_name="Summary", index=False)
        cf_table.to_excel(writer, sheet_name="CashFlows_by_Period")

        for b in bonds:
            detail = pd.DataFrame(
                [
                    {"Period": k, "CashFlow": v}
                    for k, v in sorted(b.cashflows.items())
                ]
            )
            detail["Cumulative"] = detail["CashFlow"].cumsum()
            sheet = b.symbol[:31]
            detail.to_excel(writer, sheet_name=sheet, index=False)
    print(f"Excel written: {out_path}")


# ---------------------------------------------------------------------------
# Locate latest positions file
# ---------------------------------------------------------------------------
POSITIONS_PATTERN = re.compile(
    r"^All-Accounts-Positions-(\d{4})-(\d{2})-(\d{2})-(\d{6})\.csv$",
    re.IGNORECASE,
)


def find_latest_positions_file(search_dirs: List[Path]) -> Optional[Path]:
    """
    Find the newest All-Accounts-Positions-YYYY-MM-DD-HHMMSS.csv
    across the given directories.  Newest is determined by the date+time
    embedded in the filename (not mtime).
    """
    candidates: List[Tuple[str, Path]] = []
    for d in search_dirs:
        if not d.is_dir():
            continue
        for p in d.glob("All-Accounts-Positions-*.csv"):
            m = POSITIONS_PATTERN.match(p.name)
            if m:
                # key = YYYYMMDDHHMMSS for correct chronological sort
                key = "".join(m.groups())
                candidates.append((key, p))
    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]


def guess_valuation_from_filename(path: Path) -> Optional[date]:
    """Pull the as-of date from All-Accounts-Positions-YYYY-MM-DD-....csv"""
    m = POSITIONS_PATTERN.match(path.name)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    return None


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Bond Calculator – Fixed Income cash-flow & yield analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Auto-find newest All-Accounts-Positions-*.csv in cwd and common folders
  python3 bond_calculator.py

  # Search a specific directory for the latest positions file
  python3 bond_calculator.py --dir ~/Downloads

  # Explicit file
  python3 bond_calculator.py -i All-Accounts-Positions-2026-11-24-125028.csv
""",
    )
    parser.add_argument(
        "-i", "--input",
        type=Path,
        default=None,
        help="Explicit path to positions CSV/text. If omitted, the newest "
             "All-Accounts-Positions-YYYY-MM-DD-HHMMSS.csv is used.",
    )
    parser.add_argument(
        "-d", "--dir",
        type=Path,
        action="append",
        default=None,
        help="Directory to search for All-Accounts-Positions-*.csv "
             "(can be repeated). Defaults: current dir, ~/Downloads, "
             "~/Desktop, project root.",
    )
    parser.add_argument(
        "-o", "--outdir",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "output",
        help="Output directory (default: ../output relative to this script)",
    )
    parser.add_argument(
        "--valuation-date",
        type=str,
        default=None,
        help="Valuation / as-of date YYYY-MM-DD. "
             "Default: date embedded in the positions filename, else 2026-11-24.",
    )
    args = parser.parse_args()

    # Resolve input file
    if args.input is not None:
        input_path = args.input.expanduser().resolve()
        if not input_path.is_file():
            print(f"ERROR: input file not found: {input_path}", file=sys.stderr)
            sys.exit(1)
    else:
        search_dirs: List[Path] = []
        if args.dir:
            search_dirs = [d.expanduser().resolve() for d in args.dir]
        else:
            home = Path.home()
            search_dirs = [
                Path.cwd(),
                home / "Downloads",
                home / "Desktop",
                Path(__file__).resolve().parent.parent,          # project root
                Path(__file__).resolve().parent,                 # py/
            ]
        input_path = find_latest_positions_file(search_dirs)
        if input_path is None:
            print(
                "ERROR: No All-Accounts-Positions-YYYY-MM-DD-HHMMSS.csv found.\n"
                "  Searched: " + ", ".join(str(d) for d in search_dirs) + "\n"
                "  Either drop a file matching that name into one of those folders,\n"
                "  or pass an explicit path with -i / --input.",
                file=sys.stderr,
            )
            sys.exit(1)
        print(f"Using latest positions file: {input_path}")

    # Valuation date
    if args.valuation_date:
        valuation = datetime.strptime(args.valuation_date, "%Y-%m-%d").date()
    else:
        guessed = guess_valuation_from_filename(input_path)
        valuation = guessed if guessed is not None else VALUATION_DATE
        print(f"Valuation date: {valuation.isoformat()}")

    args.outdir.mkdir(parents=True, exist_ok=True)

    text = input_path.read_text(encoding="utf-8", errors="replace")
    bonds = parse_positions_text(text)
    if not bonds:
        print("ERROR: No Fixed Income positions found in the file.", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(bonds)} Fixed Income position(s):")
    for b in bonds:
        print(f"  {b.symbol}  face={b.face:,.0f}  coupon={b.coupon_rate*100:.3f}%  mat={b.maturity}  px={b.clean_price}")

    bonds, agg = process_bonds(bonds, valuation)

    summary = make_summary_table(bonds, agg, valuation)
    cf_table = make_cashflow_table(bonds, agg)

    print("\n=== Summary ===")
    print(summary.to_string(index=False))
    print("\n=== Cash Flows by Period (first / last rows) ===")
    print(cf_table.head(8).to_string())
    if len(cf_table) > 16:
        print("...")
    print(cf_table.tail(8).to_string())

    stamp = valuation.strftime("%Y%m%d")
    xlsx_path = args.outdir / f"bond_calc_{stamp}.xlsx"
    png_path = args.outdir / f"bond_cashflows_{stamp}.png"

    write_excel(summary, cf_table, bonds, xlsx_path)
    plot_cashflows(cf_table, bonds, png_path)

    print("\nDone.")


if __name__ == "__main__":
    main()
