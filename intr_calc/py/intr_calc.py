import tkinter as tk
from tkinter import messagebox
import yfinance as yf
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.patches import Patch
import math
import pandas as pd
from datetime import datetime

APP_SPREADSHEET_OWNER_EARNINGS_MILLIONS = {
    2021: 362.0,
    2022: 413.0,
    2023: 1062.0,
    2024: 2099.0,
    2025: 4015.0,
    2026: 5473.0,
}

def calculate_alphaspread_exact_dcf(base_owner_earnings, discount_rate,
                                   start_growth_rate, end_growth_rate,
                                   terminal_growth_rate, shares_outstanding,
                                   total_cash, total_debt, margin_of_safety):
    """
    Warren Buffett owner-earnings model from the attached spreadsheet.

    - Starts from owner earnings base, not revenue.
    - Growth rate fades linearly from start rate to end rate over 10 years.
    - Terminal value uses Gordon Growth on the 10th-year cash flow.
    - Cash is added and debt is added as a negative number to match the worksheet logic.
    """
    future_values = []
    growth_rates = []
    present_values = []

    projection_years = 10
    previous_value = base_owner_earnings

    for year in range(1, projection_years + 1):
        if year == 1:
            growth_rate = start_growth_rate
        else:
            growth_rate = start_growth_rate - ((year / projection_years) * (start_growth_rate - end_growth_rate))
        growth_rates.append(growth_rate)

        previous_value *= (1 + growth_rate)
        future_values.append(previous_value)

        pv = previous_value / ((1 + discount_rate) ** year)
        present_values.append(pv)

    terminal_value = future_values[-1] * (1 + terminal_growth_rate) / (discount_rate - terminal_growth_rate)
    pv_terminal_value = terminal_value / ((1 + discount_rate) ** projection_years)

    sum_pv_projections = sum(present_values)
    corporate_value = sum_pv_projections + pv_terminal_value
    equity_value = corporate_value + total_cash + total_debt
    intrinsic_value_per_share = equity_value / shares_outstanding if shares_outstanding > 0 else 0.0
    max_buy_price = intrinsic_value_per_share * (1 - margin_of_safety)

    return (future_values, growth_rates, future_values, present_values, pv_terminal_value,
            intrinsic_value_per_share, max_buy_price, sum_pv_projections,
            equity_value, corporate_value, terminal_value)

def format_currency_short(val):
    abs_val = abs(val)
    sign = "-" if val < 0 else ""
    if abs_val >= 1_000_000_000_000:
        return f"{sign}${abs_val / 1_000_000_000_000:,.2f}T"
    elif abs_val >= 1_000_000_000:
        return f"{sign}${abs_val / 1_000_000_000:,.2f}B"
    elif abs_val >= 1_000_000:
        return f"{sign}${abs_val / 1_000_000:,.1f}M"
    else:
        return f"{sign}${abs_val:,.0f}"

def format_abbrev_number(val):
    abs_val = abs(val)
    sign = "-" if val < 0 else ""

    def trim_num(v):
        return f"{v:,.3f}".rstrip("0").rstrip(".")

    if abs_val >= 1_000_000_000_000:
        return f"{sign}{trim_num(abs_val / 1_000_000_000_000)}T"
    if abs_val >= 1_000_000_000:
        return f"{sign}{trim_num(abs_val / 1_000_000_000)}B"
    if abs_val >= 1_000_000:
        return f"{sign}{trim_num(abs_val / 1_000_000)}M"
    return f"{val:,.0f}"

def parse_abbrev_number(text):
    raw = text.strip().upper().replace(",", "").replace("$", "")
    if not raw:
        raise ValueError("Empty numeric value")

    multiplier = 1.0
    suffix = raw[-1]
    if suffix == "T":
        multiplier = 1_000_000_000_000.0
        raw = raw[:-1]
    elif suffix == "B":
        multiplier = 1_000_000_000.0
        raw = raw[:-1]
    elif suffix == "M":
        multiplier = 1_000_000.0
        raw = raw[:-1]

    return float(raw) * multiplier

class DCFApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Multi-Stage Fundamental Valuation Engine")
        self.root.geometry("1350x820")

        # Left Panel
        left_panel = tk.Frame(root, padx=15, pady=15, width=510)
        left_panel.pack(side=tk.LEFT, fill=tk.Y)
        left_panel.pack_propagate(False)

        # Section 1: Fetch Web Data
        tk.Label(left_panel, text="1. Fetch Web Data", font=("Arial", 12, "bold")).pack(anchor=tk.W, pady=(0, 5))
        ticker_frame = tk.Frame(left_panel)
        ticker_frame.pack(fill=tk.X, pady=(0, 5))
        tk.Label(ticker_frame, text="Ticker:").pack(side=tk.LEFT)

        self.entry_ticker = tk.Entry(ticker_frame, width=10)
        self.entry_ticker.insert(0, "APP")
        self.entry_ticker.pack(side=tk.LEFT, padx=5)

        btn_fetch = tk.Button(ticker_frame, text="Fetch yFinance", command=self.fetch_financials, bg="#d5f5e3")
        btn_fetch.pack(side=tk.LEFT, padx=5)

        self.lbl_market_price = tk.Label(left_panel, text="Current Price: N/A", font=("Arial", 11, "bold"), fg="#566573")
        self.lbl_market_price.pack(anchor=tk.W, pady=2)

        # Section 2: Manual Adjustments
        tk.Label(left_panel, text="2. Manual Adjustments", font=("Arial", 12, "bold")).pack(anchor=tk.W, pady=(15, 5))
        self.entries = {}

        fields = [
            ("Owner Earnings Base ($, M/B)", "owner_earnings", "5.473B"),
            ("Discount Rate (%)", "discount", "9.5"),
            ("Start Growth Rate (Yr 1) (%)", "start_growth", "19.0"),
            ("End Growth Rate (Yr 10) (%)", "end_growth", "3.0"),
            ("Terminal Growth Rate (%)", "terminal_growth", "3.0"),
            ("Shares Outstanding (#, M/B)", "shares", "331.320M"),
            ("Cash & Short-Term Investments ($, M/B)", "cash", "3.174B"),
            ("Total Long-Term Debt ($, M/B)", "debt", "-3.516B"),
            ("Margin of Safety (%)", "mos", "20.0")
        ]

        for label_text, key, default in fields:
            frame = tk.Frame(left_panel)
            frame.pack(fill=tk.X, pady=2)
            tk.Label(frame, text=label_text, width=34, anchor=tk.W).pack(side=tk.LEFT)
            entry = tk.Entry(frame)
            entry.insert(0, default)
            entry.pack(side=tk.RIGHT, expand=tk.YES, fill=tk.X)
            self.entries[key] = entry

        self.btn_calc = tk.Button(left_panel, text="Calculate Intrinsic Value",
                                  command=self.run_calculation, font=("Arial", 11, "bold"),
                                  bg="#2e86c1", fg="white", pady=5)
        self.btn_calc.pack(fill=tk.X, pady=10)

        self.txt_report = tk.Text(left_panel, height=22, font=("Courier", 9), bg="#f8f9f9", relief=tk.SOLID, bd=1)
        self.txt_report.pack(fill=tk.BOTH, expand=tk.YES)

        # Right Panel (chart)
        self.right_panel = tk.Frame(root, bg="white", padx=10, pady=10)
        self.right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=tk.YES)

        self.canvas_widget = None
        self.current_stock_price = None
        self.last_fetch_components = None

        # Dynamic years based on current calendar year
        self.current_year = datetime.now().year
        self.projection_years = list(range(self.current_year, self.current_year + 10))

        # Historical years include the five prior years plus current year.
        self.target_hist_years = list(range(self.current_year - 5, self.current_year + 1))
        self.historical_owner_earnings_by_year = {yr: 0.0 for yr in self.target_hist_years}

        self.run_calculation()

    def fetch_financials(self):
        ticker_str = self.entry_ticker.get().strip().upper()
        if not ticker_str:
            messagebox.showwarning("Warning", "Please enter a valid ticker.")
            return

        try:
            ticker = yf.Ticker(ticker_str)
            info = ticker.info

            # Current price
            self.current_stock_price = (info.get('currentPrice') or
                                        info.get('regularMarketPrice') or
                                        info.get('previousClose'))
            if self.current_stock_price:
                self.lbl_market_price.config(text=f"Current Price: ${self.current_stock_price:,.2f}")
            else:
                self.lbl_market_price.config(text="Current Price: N/A")

            try:
                income = ticker.income_stmt
            except Exception:
                income = pd.DataFrame()

            try:
                q_income = ticker.quarterly_income_stmt
            except Exception:
                q_income = pd.DataFrame()

            try:
                q_cashflow = ticker.quarterly_cash_flow
            except Exception:
                q_cashflow = pd.DataFrame()

            try:
                bs = ticker.balance_sheet
            except Exception:
                bs = pd.DataFrame()

            def safe_get(df, row_name, col_idx=0):
                if df is None or df.empty or row_name not in df.index:
                    return None
                try:
                    val = df.loc[row_name].iloc[col_idx]
                    return float(val)
                except (TypeError, ValueError, IndexError):
                    return None

            def ttm_sum(df, row_names):
                if df is None or df.empty:
                    return None
                for row_name in row_names:
                    if row_name in df.index:
                        try:
                            vals = pd.to_numeric(df.loc[row_name].iloc[:4], errors='coerce').fillna(0.0)
                            return float(vals.sum())
                        except (TypeError, ValueError, IndexError):
                            continue
                return None

            def first_non_null(values, default=0.0):
                for val in values:
                    if val is not None:
                        return float(val)
                return float(default)

            total_cash = (safe_get(bs, 'Cash And Cash Equivalents') or
                          safe_get(bs, 'Cash Cash Equivalents And Short Term Investments') or
                          info.get('totalCash') or 0.0)

            total_debt = (safe_get(bs, 'Total Debt') or
                          safe_get(bs, 'Long Term Debt') or
                          info.get('totalDebt') or 0.0)

            shares = (info.get('impliedSharesOutstanding') or
                      info.get('sharesOutstanding') or
                      safe_get(bs, 'Share Issued') or 1.0)

            # 1.03 GAAP Net Income baseline = GAAP EPS (TTM) × Shares Outstanding
            # Prefer quarterly TTM EPS to avoid annual-period mismatches.
            eps_ttm = ttm_sum(q_income, ['Diluted EPS', 'Basic EPS'])
            if eps_ttm is None:
                eps_ttm = info.get('trailingEps') or info.get('forwardEps')
            gaap_net_income_baseline = (eps_ttm * shares) if (eps_ttm is not None and shares is not None) else None
            if gaap_net_income_baseline is None:
                gaap_net_income_baseline = (
                    ttm_sum(q_income, ['Net Income', 'Net Income Common Stockholders']) or
                    safe_get(income, 'Net Income') or
                    safe_get(income, 'Net Income Common Stockholders') or
                    info.get('netIncomeToCommon') or
                    info.get('netIncome') or
                    0.0
                )

            # 1.04 Other non-cash items from last four quarters (cash flow statement basis).
            # Build non-cash addbacks from TTM quarterly cash-flow rows.
            # We keep addbacks non-negative to prevent sign-convention flips from reducing owner earnings.
            non_cash_components = [
                ttm_sum(q_cashflow, ['Depreciation And Amortization', 'Depreciation Amortization Depletion']),
                ttm_sum(q_cashflow, ['Stock Based Compensation']),
                ttm_sum(q_cashflow, ['Asset Impairment Charge']),
                ttm_sum(q_cashflow, ['Deferred Tax']),
                ttm_sum(q_cashflow, ['Other Non Cash Items'])
            ]
            other_non_cash_items = sum(max(0.0, float(v)) for v in non_cash_components if v is not None)

            # 1.05 Other investing cash flow from last four quarters.
            investing_cash_flow = first_non_null([
                ttm_sum(q_cashflow, ['Investing Cash Flow', 'Cash Flow From Continuing Investing Activities']),
                ttm_sum(q_cashflow, ['Net Other Investing Changes', 'Other Investing Activities']),
                ttm_sum(q_cashflow, ['Capital Expenditure', 'Capital Expenditures'])
            ], default=0.0)

            owner_earnings = gaap_net_income_baseline + other_non_cash_items + investing_cash_flow
            self.last_fetch_components = {
                "eps_ttm": eps_ttm if eps_ttm is not None else 0.0,
                "shares": shares,
                "gaap_baseline": gaap_net_income_baseline,
                "other_non_cash_items": other_non_cash_items,
                "investing_cash_flow": investing_cash_flow,
                "owner_earnings": owner_earnings
            }

            if shares is not None:
                self.entries['shares'].delete(0, tk.END)
                self.entries['shares'].insert(0, format_abbrev_number(float(shares)))

            if owner_earnings is not None:
                self.entries['owner_earnings'].delete(0, tk.END)
                self.entries['owner_earnings'].insert(0, format_abbrev_number(float(owner_earnings)))

            self.entries['discount'].delete(0, tk.END)
            self.entries['discount'].insert(0, "9.5")
            self.entries['start_growth'].delete(0, tk.END)
            self.entries['start_growth'].insert(0, "19.0")
            self.entries['end_growth'].delete(0, tk.END)
            self.entries['end_growth'].insert(0, "3.0")
            self.entries['terminal_growth'].delete(0, tk.END)
            self.entries['terminal_growth'].insert(0, "3.0")

            self.entries['cash'].delete(0, tk.END)
            self.entries['cash'].insert(0, format_abbrev_number(float(total_cash)))
            self.entries['debt'].delete(0, tk.END)
            self.entries['debt'].insert(0, format_abbrev_number(float(-abs(total_debt))))

            # ---------- Historical owner earnings for past-year present-value section ----------
            self.target_hist_years = list(range(self.current_year - 5, self.current_year + 1))
            self.historical_owner_earnings_by_year = {yr: 0.0 for yr in self.target_hist_years}

            if ticker_str == "APP":
                self.historical_owner_earnings_by_year.update(
                    {yr: APP_SPREADSHEET_OWNER_EARNINGS_MILLIONS.get(yr, 0.0) for yr in self.target_hist_years}
                )
            elif not income.empty and 'Net Income' in income.index:
                for col in income.columns:
                    try:
                        yr = col.year if hasattr(col, 'year') else int(str(col)[:4])
                        if yr in self.historical_owner_earnings_by_year:
                            val = income.loc['Net Income', col]
                            ni = float(val.iloc[0]) if hasattr(val, 'iloc') else float(val)
                            self.historical_owner_earnings_by_year[yr] = ni / 1_000_000.0
                    except Exception:
                        continue

            self.run_calculation()

        except Exception as e:
            messagebox.showerror("Data Transfer Error",
                                 f"Failed fetching data for {ticker_str}:\n{str(e)}")

    def run_calculation(self):
        try:
            base_owner_earnings = parse_abbrev_number(self.entries['owner_earnings'].get())
            discount_rate = float(self.entries['discount'].get()) / 100.0
            start_growth_rate = float(self.entries['start_growth'].get()) / 100.0
            end_growth_rate = float(self.entries['end_growth'].get()) / 100.0
            terminal_growth_rate = float(self.entries['terminal_growth'].get()) / 100.0
            shares_outstanding = parse_abbrev_number(self.entries['shares'].get())
            total_cash = parse_abbrev_number(self.entries['cash'].get())
            total_debt = parse_abbrev_number(self.entries['debt'].get())
            margin_of_safety = float(self.entries['mos'].get()) / 100.0

            (future_values, growth_rates, _, present_values, pv_terminal_value,
             intrinsic_value_per_share, max_buy_price, sum_pv_projections,
             equity_value, corporate_value, terminal_value) = calculate_alphaspread_exact_dcf(
                base_owner_earnings, discount_rate, start_growth_rate, end_growth_rate,
                terminal_growth_rate, shares_outstanding, total_cash, total_debt, margin_of_safety
            )

            # ---------- Report ----------
            self.txt_report.delete("1.0", tk.END)
            o = self.txt_report
            ticker_str = self.entry_ticker.get().strip().upper()

            o.insert(tk.END, f"=== CALC RESULTS FOR TICKER: {ticker_str} ===\n")
            o.insert(tk.END, f"-----------------------------------------\n")
            o.insert(tk.END, f"Intrinsic Value :  ${intrinsic_value_per_share:,.2f}  (per share)\n")

            if self.current_stock_price:
                o.insert(tk.END, f"Current Price   :  ${self.current_stock_price:,.2f}\n")
                diff_pct = ((intrinsic_value_per_share - self.current_stock_price) / self.current_stock_price) * 100
                status_str = "Undervalued by" if diff_pct > 0 else "Overvalued by"
                o.insert(tk.END, f"{status_str:<16}:  {abs(diff_pct):.1f}%\n")
            else:
                o.insert(tk.END, f"Current Price   :  N/A\n")
                o.insert(tk.END, f"Variance Pct    :  N/A\n")

            o.insert(tk.END, f"Minimum Buy     :  ${max_buy_price:,.2f}  (At {margin_of_safety*100:.0f}% Margin of Safety)\n")
            o.insert(tk.END, f"-----------------------------------------\n\n")

            if self.last_fetch_components is not None:
                c = self.last_fetch_components
                o.insert(tk.END, "Fetched Owner Earnings Breakdown:\n")
                o.insert(tk.END, f"  GAAP Baseline (EPS TTM × Shares): {format_currency_short(c['gaap_baseline'])}\n")
                o.insert(tk.END, f"    EPS TTM={c['eps_ttm']:.2f}, Shares={c['shares']:,.0f}\n")
                o.insert(tk.END, f"  Other non-cash items: {format_currency_short(c['other_non_cash_items'])}\n")
                o.insert(tk.END, f"  Other investing cash flow: {format_currency_short(c['investing_cash_flow'])}\n")
                o.insert(tk.END, f"  Owner Earnings Base: {format_currency_short(c['owner_earnings'])}\n")
                o.insert(tk.END, f"-----------------------------------------\n\n")

            o.insert(tk.END, "=== PAST OWNER EARNINGS DISCOUNTED TO PRESENT ===\n\n")
            o.insert(tk.END, f"{'Year':<6} | {'Owner Earnings':<15} | {'Discount Factor':<15} | {'Past Present Value':<15}\n")
            o.insert(tk.END, "-" * 76 + "\n")

            for hist_year in self.target_hist_years:
                owner_earnings_m = self.historical_owner_earnings_by_year.get(hist_year, 0.0)
                owner_earnings_amount = owner_earnings_m * 1_000_000.0
                year_delta = hist_year - self.current_year
                discount_factor = 1.0 / ((1.0 + discount_rate) ** year_delta)
                past_present_value = owner_earnings_amount * discount_factor
                o.insert(
                    tk.END,
                    f"{hist_year:<6} | {format_currency_short(owner_earnings_amount):<15} | "
                    f"{discount_factor:<15.3f} | {format_currency_short(past_present_value):<15}\n"
                )

            o.insert(tk.END, "-" * 76 + "\n\n")

            # Step 1
            o.insert(tk.END, "=== STEP 1: OWNER EARNINGS GROWTH & PV ===\n\n")
            o.insert(tk.END, f"{'Year':<6} | {'Growth':<9} | {'Future Val':<13} | {'Present Val':<13}\n")
            o.insert(tk.END, "-" * 66 + "\n")

            for i in range(10):
                year_label = self.projection_years[i]
                o.insert(tk.END, f"{year_label:<6} | {growth_rates[i]*100:<8.1f}% | "
                                 f"{format_currency_short(future_values[i]):<13} | "
                                 f"{format_currency_short(present_values[i]):<13}\n")

            o.insert(tk.END, "-" * 66 + "\n")
            o.insert(tk.END, f"Cumulative Explicit Projection PV Subtotal: {format_currency_short(sum_pv_projections)}\n\n")

            # Step 2 - abbreviated
            o.insert(tk.END, "=== STEP 2: TERMINAL VALUE & DISCOUNT ENGINE ===\n")
            o.insert(tk.END, f"Nominal Terminal Value = Year 10 Owner Earnings × (1+g) ÷ (r-g)\n")
            o.insert(tk.END, f"  {format_currency_short(future_values[-1])} × {1 + terminal_growth_rate:.3f} ÷ ({discount_rate:.3f} - {terminal_growth_rate:.3f})\n")
            o.insert(tk.END, f"  Subtotal Nominal TV = {format_currency_short(terminal_value)}\n\n")

            o.insert(tk.END, "Present Value of Terminal Value:\n")
            o.insert(tk.END, f"  {format_currency_short(terminal_value)}\n")
            o.insert(tk.END, "  " + "-" * 20 + "\n")
            o.insert(tk.END, f"  (1 + {discount_rate:.3f})^10\n")
            o.insert(tk.END, "  " + "═" * 30 + "\n")
            o.insert(tk.END, f"  PV of Terminal Value Subtotal = {format_currency_short(pv_terminal_value)}\n\n")

            # Step 3 - abbreviated
            o.insert(tk.END, "=== STEP 3: CORPORATE & EQUITY BRIDGE ===\n")
            o.insert(tk.END, f"Corporate Value = Cumulative PV + PV of TV\n")
            o.insert(tk.END, f"  {format_currency_short(sum_pv_projections)} + {format_currency_short(pv_terminal_value)}\n")
            o.insert(tk.END, f"  Corporate Value Subtotal = {format_currency_short(corporate_value)}\n\n")

            o.insert(tk.END, f"Equity Value = Corporate Value + Total Cash + Total Debt\n")
            o.insert(tk.END, f"  {format_currency_short(corporate_value)} + {format_currency_short(total_cash)} + {format_currency_short(total_debt)}\n")
            o.insert(tk.END, f"  Total Equity Value Subtotal = {format_currency_short(equity_value)}\n\n")

            # Step 4 - abbreviated
            o.insert(tk.END, "=== STEP 4: INTRINSIC PER-SHARE SUMMARY ===\n")
            o.insert(tk.END, "Intrinsic Value Per Share:\n")
            o.insert(tk.END, f"  {format_currency_short(equity_value)}\n")
            o.insert(tk.END, "  " + "-" * 20 + "\n")
            o.insert(tk.END, f"  {shares_outstanding:,.0f} shares\n")
            o.insert(tk.END, "  " + "═" * 30 + "\n")
            o.insert(tk.END, f"  INTRINSIC VALUE = ${intrinsic_value_per_share:,.2f} per share\n")

            # ---------- Chart ----------
            if self.canvas_widget:
                self.canvas_widget.get_tk_widget().destroy()

            fig, ax = plt.subplots(figsize=(7, 4.5), dpi=100)

            hist_years = self.target_hist_years
            hist_vals = [self.historical_owner_earnings_by_year.get(y, 0.0) for y in hist_years]

            proj_years = self.projection_years[:10]
            x_labels = [str(y) for y in hist_years] + [str(y) for y in proj_years]
            y_values = hist_vals + [val / 1_000_000.0 for val in future_values]
            colors = ['#7f8c8d'] * len(hist_years) + ['#5dade2'] * len(proj_years)

            ax.bar(x_labels, y_values, color=colors, width=0.5)
            ax.set_title("Owner Earnings Trend Analysis ($ Millions)", fontsize=10, fontweight='bold')
            ax.set_xticklabels(x_labels, fontsize=7.5, rotation=45)
            ax.yaxis.set_major_formatter(
                plt.FuncFormatter(lambda val, loc: f"${val/1000:,.1f}B" if abs(val) >= 1000 else f"${val:,.0f}M")
            )

            ax.legend(handles=[
                Patch(facecolor='#7f8c8d', label='Historical Owner Earnings'),
                Patch(facecolor='#5dade2', label='Projected Owner Earnings')
            ], loc='upper left', fontsize=7.5)

            ax.grid(axis='y', linestyle='--', alpha=0.4)
            plt.tight_layout()

            self.canvas_widget = FigureCanvasTkAgg(fig, master=self.right_panel)
            self.canvas_widget.draw()
            self.canvas_widget.get_tk_widget().pack(fill=tk.BOTH, expand=tk.YES)
            plt.close(fig)

        except ValueError:
            messagebox.showerror("Input Error", "Verify parameters contain valid numbers. M/B/T suffixes are supported.")

if __name__ == "__main__":
    root = tk.Tk()
    app = DCFApp(root)
    try:
        root.attributes('-zoomed', True)
    except Exception:
        root.geometry(f"{root.winfo_screenwidth()}x{root.winfo_screenheight()}+0+0")
    root.mainloop()