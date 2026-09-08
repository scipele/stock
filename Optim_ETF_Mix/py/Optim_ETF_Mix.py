#!/usr/bin/env python3
"""
Optim_ETF_Mix.py
================
Retirement ETF portfolio optimizer that:
  1. Prioritizes Vanguard funds first, then Schwab, then other low-cost providers.
  2. Automatically selects promising fund combinations from a curated low-ER universe.
  3. Optimizes for high, *consistent* returns across multiple historical windows
     (not just a single back-test period). Goal = best sustainable growth/yield
     over any ~20-year horizon, with expense ratios fully deducted.

Designed for a 53-year-old early retiree with ~$1.46 M rollover IRA at Schwab
(you can hold Vanguard ETFs commission-free at Schwab).

Features:
- Curated universe ranked Vanguard > Schwab > others
- Automatic fund-combination search (3–6 fund portfolios)
- Expense-ratio drag applied to every return series
- Consistency score: full-period CAGR + rolling-window CAGRs + downturn resilience
- Monte-Carlo 20-year projections and optional withdrawal stress test
- Clear ranking of the most consistent high-performing mixes

Requirements:
    pip install yfinance pandas numpy matplotlib scipy seaborn

Typical usage:
    python Optim_ETF_Mix.py
    python Optim_ETF_Mix.py --max-funds 5 --n-combos 40 --n-random 800
    python Optim_ETF_Mix.py --capital 1460000 --withdraw 55000
"""

import argparse
import itertools
import warnings
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
import yfinance as yf
from scipy.optimize import minimize

warnings.filterwarnings("ignore", category=FutureWarning)
sns.set_style("whitegrid")
plt.rcParams["figure.figsize"] = (12, 6)


# ---------------------------------------------------------------------------
# Curated universe – Vanguard first, then Schwab, then others
# Only low-expense-ratio, highly liquid core / retirement-friendly ETFs
# ---------------------------------------------------------------------------
# Format: (ticker, provider_priority, category, annual_ER)
# provider_priority: 1 = Vanguard (preferred), 2 = Schwab, 3 = other
FUND_UNIVERSE = [
    # --- Vanguard (priority 1) ---
    ("VTI",  1, "US Total Market",     0.0003),
    ("VOO",  1, "US Large Cap (S&P)",  0.0003),
    ("VIG",  1, "US Dividend Growth",  0.0004),
    ("VYM",  1, "US High Dividend",    0.0004),
    ("VEA",  1, "Intl Developed",      0.0003),
    ("VXUS", 1, "Intl Total",          0.0005),
    ("VWO",  1, "Emerging Markets",    0.0006),
    ("BND",  1, "US Total Bond",       0.0003),
    ("BNDX", 1, "Intl Bond",           0.0007),
    ("VTIP", 1, "Short TIPS",          0.0004),
    ("VGSH", 1, "Short Treasury",      0.0003),
    ("BSV",  1, "Short Bond",          0.0003),
    # --- Schwab (priority 2) – excellent when Vanguard equivalent unavailable or for Schwab ecosystem ---
    ("SCHB", 2, "US Total Market",     0.0003),
    ("SCHX", 2, "US Large Cap",        0.0003),
    ("SCHD", 2, "US Dividend Quality", 0.0006),
    ("SCHF", 2, "Intl Developed",      0.0003),
    ("SCHE", 2, "Emerging Markets",    0.0006),
    ("SCHZ", 2, "US Total Bond",       0.0003),
    ("SCHP", 2, "TIPS",                0.0003),
    ("SCHO", 2, "Short Treasury",      0.0003),
    # --- Other low-cost (priority 3) ---
    ("ITOT", 3, "US Total Market",     0.0003),
    ("AGG",  3, "US Total Bond",       0.0003),
    ("AOR",  3, "60/40 Allocation",    0.0015),  # iShares Core Growth Allocation (benchmark)
]

# Quick lookup
EXPENSE_RATIOS = {t: er for t, _, _, er in FUND_UNIVERSE}
PROVIDER_PRIORITY = {t: p for t, p, _, _ in FUND_UNIVERSE}
CATEGORY = {t: c for t, _, c, _ in FUND_UNIVERSE}

def equity_bond_weights(weights: Dict[str, float]) -> Tuple[float, float]:
    """Return (equity_weight, bond_weight) based on category."""
    eq = 0.0
    bd = 0.0
    for t, w in weights.items():
        cat = CATEGORY.get(t, "")
        if any(x in cat for x in ("Bond", "TIPS", "Treasury")):
            bd += w
        else:
            eq += w
    return eq, bd

DEFAULT_CAPITAL = 1_460_000.0
DEFAULT_HORIZON_YEARS = 20
DEFAULT_START = "2014-01-01"          # ~10+ year window – more ETFs have complete data
DEFAULT_RF = 0.02
DOWNTURNS = {
    # "GFC (2007-2009)": ("2007-10-01", "2009-03-01"),  # often incomplete for newer ETFs
    "COVID Crash (2020)": ("2020-02-01", "2020-04-01"),
    "2022 Bear": ("2022-01-01", "2022-10-01"),
}


@dataclass
class PortfolioResult:
    weights: Dict[str, float]
    cagr: float
    vol: float
    sharpe: float
    max_dd: float
    calmar: float
    total_return: float
    final_value: float
    weighted_er: float = 0.0
    consistency_score: float = 0.0      # higher = more consistent high returns
    rolling_cagrs: List[float] = field(default_factory=list)
    min_rolling_cagr: float = 0.0
    median_rolling_cagr: float = 0.0
    downturn_dds: Dict[str, float] = field(default_factory=dict)
    equity_curve: Optional[pd.Series] = None
    provider_score: float = 0.0         # lower is better (prefers Vanguard)


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------
def download_prices(tickers: List[str], start: str, end: Optional[str] = None) -> pd.DataFrame:
    print(f"Downloading data for {len(tickers)} tickers from {start} ...")
    data = yf.download(
        tickers, start=start, end=end, auto_adjust=True, progress=False, group_by="ticker",
    )
    if len(tickers) == 1:
        prices = data[["Close"]].rename(columns={"Close": tickers[0]})
    else:
        if isinstance(data.columns, pd.MultiIndex):
            level1 = data.columns.get_level_values(1)
            if "Close" in level1:
                prices = data.xs("Close", axis=1, level=1)
            else:
                prices = data.xs("Adj Close", axis=1, level=1)
        else:
            prices = data
    prices = prices.dropna(how="all").ffill().dropna(how="any")
    available = [t for t in tickers if t in prices.columns]
    missing = set(tickers) - set(available)
    if missing:
        print(f"  Warning: no data for {missing} – they will be skipped")
    print(f"  Got {len(prices)} trading days ({prices.index[0].date()} → {prices.index[-1].date()}) for {len(available)} funds")
    return prices[available]


def daily_returns(prices: pd.DataFrame) -> pd.DataFrame:
    return prices.pct_change().dropna()


# ---------------------------------------------------------------------------
# Metrics + expense drag
# ---------------------------------------------------------------------------
def get_expense_ratio(ticker: str) -> float:
    return EXPENSE_RATIOS.get(ticker.upper(), 0.0010)


def weighted_expense_ratio(weights: Dict[str, float]) -> float:
    return sum(w * get_expense_ratio(t) for t, w in weights.items())


def apply_expense_drag(returns: pd.Series, annual_er: float) -> pd.Series:
    return returns - (annual_er / 252.0)


def portfolio_returns(returns: pd.DataFrame, weights: np.ndarray) -> pd.Series:
    return (returns * np.asarray(weights)).sum(axis=1)


def max_drawdown(equity: pd.Series) -> float:
    peak = equity.cummax()
    return ((equity - peak) / peak).min()


def compute_metrics(returns: pd.Series, capital: float = 1.0, rf: float = DEFAULT_RF):
    equity = (1 + returns).cumprod() * capital
    total_ret = equity.iloc[-1] / capital - 1.0
    n_years = (returns.index[-1] - returns.index[0]).days / 365.25
    cagr = (equity.iloc[-1] / capital) ** (1 / max(n_years, 1e-6)) - 1
    vol = returns.std() * np.sqrt(252)
    excess = returns.mean() * 252 - rf
    sharpe = excess / vol if vol > 0 else 0.0
    mdd = max_drawdown(equity)
    calmar = cagr / abs(mdd) if mdd != 0 else 0.0
    return cagr, vol, sharpe, mdd, calmar, total_ret, equity


def rolling_cagrs(returns: pd.Series, window_years: float = 10.0) -> List[float]:
    """Compute CAGR on rolling windows to measure consistency."""
    if returns.empty:
        return []
    window = int(window_years * 252)
    if len(returns) < window + 20:
        n = max(3, len(returns) // max(window // 2, 1))
        chunk = len(returns) // n
        cagrs = []
        for i in range(n):
            seg = returns.iloc[i * chunk : (i + 1) * chunk]
            if len(seg) < 100:
                continue
            eq = (1 + seg).cumprod()
            yrs = len(seg) / 252
            cagrs.append(eq.iloc[-1] ** (1 / yrs) - 1)
        return cagrs
    cagrs = []
    step = max(63, window // 4)
    for start in range(0, len(returns) - window, step):
        seg = returns.iloc[start : start + window]
        eq = (1 + seg).cumprod()
        cagrs.append(eq.iloc[-1] ** (1 / window_years) - 1)
    return cagrs


def simulate_rebalanced_returns(
    returns: pd.DataFrame,
    weights: Dict[str, float],
    rebalance_months: Tuple[int, ...] = (1, 7),
) -> pd.Series:
    """
    Simulate portfolio returns with periodic rebalancing.
    Default: rebalance on the first trading day of January and July
    (simple, widely used schedule).
    Between rebalance dates the portfolio drifts with market returns.
    """
    tickers = list(weights.keys())
    target = np.array([weights[t] for t in tickers])
    rets = returns[tickers].copy()

    # Identify rebalance dates: first trading day of the chosen months
    months = rets.index.month
    years = rets.index.year
    is_first_of_month = rets.index.to_series().groupby([years, months]).transform('idxmin') == rets.index
    rebalance_mask = is_first_of_month & rets.index.month.isin(rebalance_months)

    # Day-by-day simulation
    n = len(rets)
    port_rets = np.zeros(n)
    # Start fully invested at target weights
    w = target.copy()

    for i in range(n):
        # Portfolio return that day = weighted sum of asset returns
        r = rets.iloc[i].values
        port_rets[i] = np.dot(w, r)
        # Update weights by drift
        w = w * (1.0 + r)
        total = w.sum()
        if total > 0:
            w = w / total
        # Rebalance if this is a rebalance day
        if rebalance_mask.iloc[i]:
            w = target.copy()

    return pd.Series(port_rets, index=rets.index, name="portfolio")


def evaluate_portfolio(
    returns: pd.DataFrame,
    weights: Dict[str, float],
    capital: float,
    rf: float = DEFAULT_RF,
    downturns: Optional[Dict[str, Tuple[str, str]]] = None,
    roll_years: float = 5.0,
    rebalance_months: Tuple[int, ...] = (1, 7),
) -> PortfolioResult:
    """Evaluate with semi-annual (Jan/Jul) rebalancing and expense drag."""
    tickers = list(weights.keys())
    # Only keep tickers that exist in the returns matrix
    tickers = [t for t in tickers if t in returns.columns]
    weights = {t: weights[t] for t in tickers}
    # Renormalize in case any were dropped
    s = sum(weights.values())
    if s <= 0:
        raise ValueError("No valid tickers")
    weights = {t: v / s for t, v in weights.items()}

    port_ret = simulate_rebalanced_returns(returns, weights, rebalance_months=rebalance_months)
    er = weighted_expense_ratio(weights)
    port_ret_net = apply_expense_drag(port_ret, er)

    cagr, vol, sharpe, mdd, calmar, tot, equity = compute_metrics(port_ret_net, capital, rf)

    rolls = rolling_cagrs(port_ret_net, window_years=roll_years)
    min_roll = min(rolls) if rolls else cagr
    med_roll = float(np.median(rolls)) if rolls else cagr

    consistency = (
        0.45 * med_roll
        + 0.35 * min_roll
        + 0.10 * sharpe * 0.01
        - 0.10 * abs(mdd)
    )

    prov = sum(weights[t] * PROVIDER_PRIORITY.get(t, 3) for t in tickers)

    downturn_dds = {}
    if downturns:
        for name, (s, e) in downturns.items():
            mask = (port_ret_net.index >= s) & (port_ret_net.index <= e)
            if mask.sum() > 5:
                sub_eq = (1 + port_ret_net[mask]).cumprod()
                downturn_dds[name] = max_drawdown(sub_eq)

    return PortfolioResult(
        weights=weights,
        cagr=cagr,
        vol=vol,
        sharpe=sharpe,
        max_dd=mdd,
        calmar=calmar,
        total_return=tot,
        final_value=equity.iloc[-1],
        weighted_er=er,
        consistency_score=consistency,
        rolling_cagrs=rolls,
        min_rolling_cagr=min_roll,
        median_rolling_cagr=med_roll,
        downturn_dds=downturn_dds,
        equity_curve=equity,
        provider_score=prov,
    )


# ---------------------------------------------------------------------------
# Fund selection & weight generation
# ---------------------------------------------------------------------------
def select_candidate_funds(available: List[str], max_funds: int = 5) -> List[List[str]]:
    """Build smart combinations respecting category diversity and Vanguard preference."""
    us_equity = [t for t in available if CATEGORY.get(t, "").startswith("US") and "Bond" not in CATEGORY.get(t, "") and "TIPS" not in CATEGORY.get(t, "") and "Treasury" not in CATEGORY.get(t, "")]
    intl_equity = [t for t in available if "Intl" in CATEGORY.get(t, "") or "Emerging" in CATEGORY.get(t, "")]
    bonds = [t for t in available if "Bond" in CATEGORY.get(t, "") or "TIPS" in CATEGORY.get(t, "") or "Treasury" in CATEGORY.get(t, "")]

    def prefer_vanguard(lst):
        return sorted(lst, key=lambda t: (PROVIDER_PRIORITY.get(t, 3), t))

    us_equity = prefer_vanguard(us_equity)
    intl_equity = prefer_vanguard(intl_equity)
    bonds = prefer_vanguard(bonds)

    combos = []

    # Classic 3-fund
    for u in us_equity[:4]:
        for i in intl_equity[:3]:
            for b in bonds[:4]:
                combos.append([u, i, b])

    # 4-fund with dividend sleeve
    div_funds = [t for t in available if "Dividend" in CATEGORY.get(t, "")]
    div_funds = prefer_vanguard(div_funds)
    for u in us_equity[:3]:
        for i in intl_equity[:2]:
            for b in bonds[:3]:
                for d in div_funds[:2]:
                    if d not in (u, i, b):
                        combos.append([u, i, b, d])

    # 5-fund: add short ballast or EM
    short = [t for t in bonds if "Short" in CATEGORY.get(t, "") or "TIPS" in CATEGORY.get(t, "")]
    em = [t for t in available if "Emerging" in CATEGORY.get(t, "")]
    for base in combos[:12]:
        for s in short[:2]:
            if s not in base and len(base) < max_funds:
                combos.append(base + [s])
        for e in em[:1]:
            if e not in base and len(base) < max_funds:
                combos.append(base + [e])

    unique = []
    seen = set()
    for c in combos:
        key = tuple(sorted(c))
        if key not in seen and 3 <= len(c) <= max_funds:
            seen.add(key)
            unique.append(c)
    return unique[:80]


def generate_weights_for_combo(
    tickers: List[str],
    step: float = 0.10,
    min_equity: float = 0.60,
    max_equity: float = 0.80,
) -> List[Dict[str, float]]:
    """Generate weight grids that also stay inside the desired equity band."""
    n = len(tickers)
    levels = np.arange(0.0, 1.0 + 1e-9, step)
    out = []
    for combo in itertools.product(levels, repeat=n):
        if abs(sum(combo) - 1.0) < 1e-6:
            wdict = dict(zip(tickers, combo))
            if n >= 3 and (min(combo) < 0.05 and max(combo) > 0.75):
                continue
            eq, _ = equity_bond_weights(wdict)
            if min_equity - 1e-6 <= eq <= max_equity + 1e-6:
                out.append(wdict)
    return out


def random_weights(
    tickers: List[str],
    n: int = 400,
    min_equity: float = 0.60,
    max_equity: float = 0.80,
) -> List[Dict[str, float]]:
    res = []
    attempts = 0
    while len(res) < n and attempts < n * 8:
        attempts += 1
        raw = np.random.dirichlet(np.ones(len(tickers)) * 1.2)
        if raw.min() < 0.04 and len(tickers) > 2:
            continue
        wdict = dict(zip(tickers, raw))
        eq, _ = equity_bond_weights(wdict)
        if min_equity - 1e-6 <= eq <= max_equity + 1e-6:
            res.append(wdict)
    return res


def optimize_sharpe(returns: pd.DataFrame, tickers: List[str], rf: float = DEFAULT_RF) -> Dict[str, float]:
    mu = returns[tickers].mean() * 252
    cov = returns[tickers].cov() * 252
    def neg_sharpe(w):
        r = np.dot(w, mu)
        v = np.sqrt(np.dot(w, np.dot(cov, w)))
        return -(r - rf) / v if v > 0 else 0
    cons = {"type": "eq", "fun": lambda w: np.sum(w) - 1}
    bounds = [(0.05, 0.70)] * len(tickers) if len(tickers) > 2 else [(0, 1)] * len(tickers)
    x0 = np.ones(len(tickers)) / len(tickers)
    res = minimize(neg_sharpe, x0, method="SLSQP", bounds=bounds, constraints=cons, options={"maxiter": 200})
    if res.success:
        return dict(zip(tickers, res.x))
    return dict(zip(tickers, x0))


# ---------------------------------------------------------------------------
# Forward projection
# ---------------------------------------------------------------------------
def project_historical(cagr: float, capital: float, years: int) -> float:
    return capital * (1 + cagr) ** years


def monte_carlo(returns: pd.Series, capital: float, years: int = 20, n_sims: int = 2000, block_size: int = 21) -> np.ndarray:
    daily = returns.values
    n_days = years * 252
    terminals = np.empty(n_sims)
    for i in range(n_sims):
        n_blocks = int(np.ceil(n_days / block_size))
        starts = np.random.randint(0, max(1, len(daily) - block_size), size=n_blocks)
        path = np.concatenate([daily[s:s + block_size] for s in starts])[:n_days]
        terminals[i] = capital * np.prod(1 + path)
    return terminals


def withdrawal_simulation(returns: pd.Series, capital: float, annual_withdraw: float, years: int = 20, n_sims: int = 1000):
    daily = returns.values
    n_days = years * 252
    daily_wd = annual_withdraw / 252
    success = 0
    finals = []
    for _ in range(n_sims):
        bal = capital
        path = np.random.choice(daily, size=n_days, replace=True)
        for r in path:
            bal = bal * (1 + r) - daily_wd
            if bal <= 0:
                bal = 0
                break
        if bal > 0:
            success += 1
        finals.append(bal)
    return {
        "success_rate": success / n_sims,
        "median_final": float(np.median(finals)),
        "p10_final": float(np.percentile(finals, 10)),
    }


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------
def print_result(res: PortfolioResult, label: str = ""):
    print(f"\n{'='*64}")
    if label:
        print(f"  {label}")
    print(f"{'='*64}")
    ordered = sorted(res.weights.items(), key=lambda x: -x[1])
    wstr = "  ".join(f"{k}:{v*100:5.1f}%" for k, v in ordered)
    print(f"Weights      : {wstr}")
    print(f"Providers    : score {res.provider_score:.2f}  (1.0 = pure Vanguard)")
    print(f"Wtd ER       : {res.weighted_er*100:6.3f}%")
    print(f"CAGR (net)   : {res.cagr*100:6.2f}%")
    print(f"Median roll  : {res.median_rolling_cagr*100:6.2f}%   Min roll: {res.min_rolling_cagr*100:6.2f}%")
    print(f"Consistency  : {res.consistency_score*100:6.2f}  (higher = better long-term reliability)")
    print(f"Vol / Sharpe : {res.vol*100:5.2f}%  /  {res.sharpe:5.2f}")
    print(f"Max DD       : {res.max_dd*100:6.2f}%")
    print(f"Final value  : ${res.final_value:,.0f}")
    if res.downturn_dds:
        print("Downturn Max DDs:")
        for name, dd in res.downturn_dds.items():
            print(f"  {name:22s}: {dd*100:6.2f}%")


def plot_equity_curves(results: List[PortfolioResult], title: str = "Top Consistent Portfolios"):
    plt.figure(figsize=(13, 7))
    for res in results:
        if res.equity_curve is not None:
            label = " / ".join(f"{k}{int(v*100)}" for k, v in sorted(res.weights.items(), key=lambda x: -x[1])[:4])
            plt.plot(res.equity_curve.index, res.equity_curve.values, label=label, alpha=0.85)
    plt.yscale("log")
    plt.title(title)
    plt.ylabel("Portfolio Value ($)")
    plt.legend(loc="upper left", fontsize=8)
    plt.tight_layout()
    plt.savefig("equity_curves.png", dpi=150)
    print("Saved equity_curves.png")
    plt.close()


def plot_mc_histogram(terminals: np.ndarray, capital: float, years: int):
    plt.figure(figsize=(10, 5))
    sns.histplot(terminals, bins=50, kde=True, color="steelblue")
    plt.axvline(np.median(terminals), color="red", linestyle="--", label=f"Median ${np.median(terminals):,.0f}")
    plt.axvline(capital, color="gray", linestyle=":", label=f"Start ${capital:,.0f}")
    plt.title(f"Monte-Carlo Terminal Wealth ({years} yr, {len(terminals)} sims) – net of fees")
    plt.xlabel("Final Portfolio Value ($)")
    plt.legend()
    plt.tight_layout()
    plt.savefig("mc_histogram.png", dpi=150)
    print("Saved mc_histogram.png")
    plt.close()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Vanguard-first consistent high-yield ETF optimizer")
    parser.add_argument("--start", default=DEFAULT_START, help="History start date (YYYY-MM-DD). Default ~10y window.")
    parser.add_argument("--roll-years", type=float, default=5.0, help="Length of rolling windows used for consistency score")
    parser.add_argument("--min-equity", type=float, default=0.60, help="Minimum equity allocation (e.g. 0.60 for 60/40)")
    parser.add_argument("--max-equity", type=float, default=0.80, help="Maximum equity allocation (e.g. 0.80 for 80/20)")
    parser.add_argument("--capital", type=float, default=DEFAULT_CAPITAL)
    parser.add_argument("--years", type=int, default=DEFAULT_HORIZON_YEARS)
    parser.add_argument("--max-funds", type=int, default=5, help="Max funds per portfolio")
    parser.add_argument("--n-combos", type=int, default=35, help="How many fund combinations to explore")
    parser.add_argument("--step", type=float, default=0.10)
    parser.add_argument("--n-random", type=int, default=300)
    parser.add_argument("--n-sims", type=int, default=2500)
    parser.add_argument("--withdraw", type=float, default=0.0)
    parser.add_argument("--top", type=int, default=7)
    args = parser.parse_args()

    print("\nOptim_ETF_Mix – Vanguard-first, consistency-focused retirement optimizer")
    print(f"Capital : ${args.capital:,.0f}   Horizon : {args.years} years")
    print(f"Equity band: {args.min_equity*100:.0f}% – {args.max_equity*100:.0f}%  (bonds {100-args.max_equity*100:.0f}% – {100-args.min_equity*100:.0f}%)\n")

    all_tickers = [t for t, _, _, _ in FUND_UNIVERSE]
    prices = download_prices(all_tickers, args.start)
    available = list(prices.columns)
    rets = daily_returns(prices)

    print(f"\nAvailable funds ({len(available)}):")
    for t in sorted(available, key=lambda x: (PROVIDER_PRIORITY.get(x, 9), x)):
        prov = {1: "Vanguard", 2: "Schwab", 3: "Other"}.get(PROVIDER_PRIORITY.get(t, 3), "?")
        print(f"  {t:6s}  {prov:9s}  ER {get_expense_ratio(t)*100:.2f}%  – {CATEGORY.get(t, '')}")

    print("\nBuilding fund combinations (Vanguard preferred) ...")
    combos = select_candidate_funds(available, max_funds=args.max_funds)[: args.n_combos]
    print(f"  Exploring {len(combos)} distinct fund mixes")

    candidates: List[Dict[str, float]] = []
    for combo in combos:
        candidates.extend(generate_weights_for_combo(combo, step=args.step, min_equity=args.min_equity, max_equity=args.max_equity))
        candidates.extend(random_weights(combo, n=max(30, args.n_random // max(len(combos), 1)), min_equity=args.min_equity, max_equity=args.max_equity))
        try:
            opt_w = optimize_sharpe(rets, combo)
            eq, _ = equity_bond_weights(opt_w)
            if args.min_equity - 1e-6 <= eq <= args.max_equity + 1e-6:
                candidates.append(opt_w)
        except Exception:
            pass

    unique_cands = []
    seen = set()
    for w in candidates:
        key = tuple(sorted((k, round(v, 3)) for k, v in w.items()))
        if key not in seen:
            seen.add(key)
            unique_cands.append(w)
    print(f"  Total unique portfolios to evaluate: {len(unique_cands)}")

    print("Evaluating (net of expenses + consistency scoring) ...")
    results: List[PortfolioResult] = []
    for i, w in enumerate(unique_cands):
        if (i + 1) % 200 == 0:
            print(f"  ... {i+1}/{len(unique_cands)}")
        try:
            res = evaluate_portfolio(rets, w, args.capital, downturns=DOWNTURNS, roll_years=args.roll_years)
            results.append(res)
        except Exception:
            continue

    if not results:
        print("No valid portfolios – check data availability.")
        return

    # Rank by consistency first, then CAGR, then Vanguard preference
    results.sort(key=lambda r: (-r.consistency_score, -r.cagr, r.provider_score))

    print(f"\n>>> TOP {args.top} MOST CONSISTENT HIGH-YIELD PORTFOLIOS")
    print("    (ranked by consistency of returns across rolling windows + overall growth)")
    for i, res in enumerate(results[: args.top], 1):
        print_result(res, label=f"#{i}")

    vanguard_core = [t for t in ["VTI", "VEA", "BND"] if t in available]
    if len(vanguard_core) == 3:
        eq_w = {t: 1/3 for t in vanguard_core}
        ref = evaluate_portfolio(rets, eq_w, args.capital, downturns=DOWNTURNS, roll_years=args.roll_years)
        print_result(ref, label="Reference: Equal-weight Vanguard 3-fund (VTI/VEA/BND)")

    # Benchmark: AOR (iShares Core Growth Allocation ~60/40)
    if "AOR" in available:
        aor_w = {"AOR": 1.0}
        aor_res = evaluate_portfolio(rets, aor_w, args.capital, downturns=DOWNTURNS, roll_years=args.roll_years)
        print_result(aor_res, label="Benchmark: AOR (iShares Core Growth Allocation ETF)")
    else:
        print("\n  (AOR data not available for comparison)")

    best = results[0]
    print(f"\n>>> 20-YEAR PROJECTIONS for the #1 most-consistent portfolio")
    hist_proj = project_historical(best.cagr, args.capital, args.years)
    print(f"  Historical-CAGR projection : ${hist_proj:,.0f}")

    print("  Running Monte-Carlo (net of fees, semi-annual rebalance) ...")
    # Rebuild the same rebalanced net series used in evaluation
    port_rets_gross = simulate_rebalanced_returns(rets, best.weights, rebalance_months=(1, 7))
    port_rets = apply_expense_drag(port_rets_gross, best.weighted_er)
    terminals = monte_carlo(port_rets, args.capital, years=args.years, n_sims=args.n_sims)
    print(f"  MC median terminal wealth  : ${np.median(terminals):,.0f}")
    print(f"  MC 10th percentile         : ${np.percentile(terminals, 10):,.0f}")
    print(f"  MC 90th percentile         : ${np.percentile(terminals, 90):,.0f}")
    plot_mc_histogram(terminals, args.capital, args.years)

    if args.withdraw > 0:
        print(f"\n>>> WITHDRAWAL SIMULATION (${args.withdraw:,.0f}/yr)")
        wd = withdrawal_simulation(port_rets, args.capital, args.withdraw, args.years)
        print(f"  Success rate               : {wd['success_rate']*100:.1f}%")
        print(f"  Median final balance       : ${wd['median_final']:,.0f}")
        print(f"  10th-pct final balance     : ${wd['p10_final']:,.0f}")

    plot_equity_curves(results[:5], title="Top Consistency-Ranked Portfolios (log scale)")

    print("\n>>> RECOMMENDED ALLOCATION (highest consistency + strong growth, Vanguard preferred)")
    print(f"  Weighted expense ratio : {best.weighted_er*100:.3f}% / year")
    print(f"  Consistency score     : {best.consistency_score*100:.2f}")
    eq, bd = equity_bond_weights(best.weights)
    print(f"  Equity / Bond         : {eq*100:.0f}% / {bd*100:.0f}%")
    print(f"  Expected net CAGR     : {best.cagr*100:.2f}%")
    for t, w in sorted(best.weights.items(), key=lambda x: -x[1]):
        dollars = w * args.capital
        prov = {1: "Vanguard", 2: "Schwab", 3: "Other"}.get(PROVIDER_PRIORITY.get(t, 3), "?")
        print(f"  {t:6s}  {w*100:5.1f}%   →  ${dollars:10,.0f}   ER {get_expense_ratio(t)*100:.2f}%  ({prov})")

    print("\nNotes:")
    print("  • All returns are net of the stated expense ratios.")
    print("  • Portfolios are rebalanced twice a year (first trading day of January & July).")
    print("  • Consistency score rewards portfolios that delivered solid CAGRs even in weaker sub-periods.")
    print("  • Vanguard funds receive a preference; Schwab appears only when it improves the mix.")
    print("  • AOR is shown as a simple all-in-one 60/40-style benchmark.")
    print("  • Past consistency does not guarantee future results. Re-run periodically.")
    print("Done. See equity_curves.png and mc_histogram.png.")


if __name__ == "__main__":
    main()