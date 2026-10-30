import tkinter as tk
from tkinter import messagebox
import yfinance as yf
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.patches import Patch
import math
import pandas as pd
from datetime import datetime

def calculate_alphaspread_exact_dcf(base_rev, revenue_cagr, start_margin, end_margin,
                                   discount_rate, exit_multiple, shares_outstanding,
                                   total_cash, total_debt, margin_of_safety):
    """
    Multi-stage model:
    - Projects Revenue at constant CAGR
    - Linearly fades Net Margin from start → end
    - Discounts explicit-period Net Income
    - Terminal Value = Year-5 Revenue × Exit P/S Multiple
    """
    revenues = []
    net_margins = []
    net_incomes = []
    present_values = []

    current_rev = base_rev
    projection_years = 5

    for year in range(1, projection_years + 1):
        current_rev = current_rev * (1 + revenue_cagr)
        revenues.append(current_rev)

        if projection_years == 1:
            weight = 1.0
        else:
            weight = (year - 1) / (projection_years - 1)
        current_margin = start_margin * (1 - weight) + end_margin * weight
        net_margins.append(current_margin)

        ni = current_rev * current_margin
        net_incomes.append(ni)

        pv = ni / ((1 + discount_rate) ** year)
        present_values.append(pv)

    terminal_value = revenues[-1] * exit_multiple
    pv_terminal_value = terminal_value / ((1 + discount_rate) ** projection_years)

    sum_pv_projections = sum(present_values)
    enterprise_value = sum_pv_projections + pv_terminal_value
    equity_value = enterprise_value + total_cash - total_debt
    intrinsic_value_per_share = equity_value / shares_outstanding if shares_outstanding > 0 else 0.0
    max_buy_price = intrinsic_value_per_share * (1 - margin_of_safety)

    return (revenues, net_margins, net_incomes, present_values, pv_terminal_value,
            intrinsic_value_per_share, max_buy_price, sum_pv_projections,
            equity_value, enterprise_value, terminal_value)

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
        self.entry_ticker.insert(0, "GOOGL")
        self.entry_ticker.pack(side=tk.LEFT, padx=5)

        btn_fetch = tk.Button(ticker_frame, text="Fetch yFinance", command=self.fetch_financials, bg="#d5f5e3")
        btn_fetch.pack(side=tk.LEFT, padx=5)

        self.lbl_market_price = tk.Label(left_panel, text="Current Price: N/A", font=("Arial", 11, "bold"), fg="#566573")
        self.lbl_market_price.pack(anchor=tk.W, pady=2)

        # Section 2: Manual Adjustments
        tk.Label(left_panel, text="2. Manual Adjustments", font=("Arial", 12, "bold")).pack(anchor=tk.W, pady=(15, 5))
        self.entries = {}

        fields = [
            ("Starting Revenue ($)", "rev", "402840000000"),
            ("Revenue CAGR (%)", "cagr", "12.0"),
            ("Initial Margin (%)", "start_m", "26.5"),
            ("Target Faded Margin (%)", "end_m", "24.0"),
            ("Discount Rate (%)", "discount", "8.5"),
            ("Exit Multiple (x P/S)", "exit_mult", "5.5"),
            ("Shares Outstanding", "shares", "12050000000"),
            ("Total Cash & Equiv ($)", "cash", "126840000000"),
            ("Total Debt ($)", "debt", "59290000000"),
            ("Margin of Safety (%)", "mos", "20.0")
        ]

        for label_text, key, default in fields:
            frame = tk.Frame(left_panel)
            frame.pack(fill=tk.X, pady=2)
            tk.Label(frame, text=label_text, width=24, anchor=tk.W).pack(side=tk.LEFT)
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

        # Dynamic years based on current calendar year
        self.current_year = datetime.now().year          # 2026
        self.projection_years = list(range(self.current_year, self.current_year + 5))  # 2026-2030

        # Historical years = the 5 years immediately before current year
        self.target_hist_years = list(range(self.current_year - 5, self.current_year))  # 2021-2025
        self.historical_ni_by_year = {yr: 0.0 for yr in self.target_hist_years}

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

            total_cash = (safe_get(bs, 'Cash And Cash Equivalents') or
                          safe_get(bs, 'Cash Cash Equivalents And Short Term Investments') or
                          info.get('totalCash') or 0.0)

            total_debt = (safe_get(bs, 'Total Debt') or
                          safe_get(bs, 'Long Term Debt') or
                          info.get('totalDebt') or 0.0)

            shares = (info.get('impliedSharesOutstanding') or
                      info.get('sharesOutstanding') or
                      safe_get(bs, 'Share Issued') or 1.0)

            rev = (safe_get(income, 'Total Revenue') or
                   info.get('totalRevenue') or
                   info.get('revenue'))

            net_income = (safe_get(income, 'Net Income') or
                          safe_get(income, 'Net Income Common Stockholders') or
                          info.get('netIncomeToCommon') or
                          info.get('netIncome'))

            calculated_margin = 25.0
            if net_income is not None and rev is not None and rev > 0:
                calculated_margin = (net_income / rev) * 100.0
            elif info.get('profitMargins') is not None:
                calculated_margin = float(info['profitMargins']) * 100.0

            if rev is not None:
                self.entries['rev'].delete(0, tk.END)
                self.entries['rev'].insert(0, f"{int(rev)}")
            if shares is not None:
                self.entries['shares'].delete(0, tk.END)
                self.entries['shares'].insert(0, f"{int(shares)}")

            self.entries['start_m'].delete(0, tk.END)
            self.entries['start_m'].insert(0, f"{calculated_margin:.1f}")

            faded = max(12.0, calculated_margin - 1.0)
            self.entries['end_m'].delete(0, tk.END)
            self.entries['end_m'].insert(0, f"{faded:.1f}")

            self.entries['cash'].delete(0, tk.END)
            self.entries['cash'].insert(0, f"{int(total_cash)}")
            self.entries['debt'].delete(0, tk.END)
            self.entries['debt'].insert(0, f"{int(total_debt)}")

            # ---------- Dynamic Historical Net Income (years before current year) ----------
            self.historical_ni_by_year = {}
            if not income.empty and 'Net Income' in income.index:
                for col in income.columns:
                    try:
                        yr = col.year if hasattr(col, 'year') else int(str(col)[:4])
                        if yr < self.current_year:
                            val = income.loc['Net Income', col]
                            ni = float(val.iloc[0]) if hasattr(val, 'iloc') else float(val)
                            self.historical_ni_by_year[yr] = ni / 1_000_000.0
                    except Exception:
                        continue

            if self.historical_ni_by_year:
                sorted_years = sorted(self.historical_ni_by_year.keys())[-5:]
                self.target_hist_years = sorted_years
                self.historical_ni_by_year = {y: self.historical_ni_by_year[y] for y in sorted_years}
            else:
                self.target_hist_years = list(range(self.current_year - 5, self.current_year))
                self.historical_ni_by_year = {yr: 0.0 for yr in self.target_hist_years}

            self.run_calculation()

        except Exception as e:
            messagebox.showerror("Data Transfer Error",
                                 f"Failed fetching data for {ticker_str}:\n{str(e)}")

    def run_calculation(self):
        try:
            base_rev = float(self.entries['rev'].get())
            revenue_cagr = float(self.entries['cagr'].get()) / 100.0
            start_margin = float(self.entries['start_m'].get()) / 100.0
            end_margin = float(self.entries['end_m'].get()) / 100.0
            discount_rate = float(self.entries['discount'].get()) / 100.0
            exit_multiple = float(self.entries['exit_mult'].get())
            shares_outstanding = float(self.entries['shares'].get())
            total_cash = float(self.entries['cash'].get())
            total_debt = float(self.entries['debt'].get())
            margin_of_safety = float(self.entries['mos'].get()) / 100.0

            (revenues, net_margins, net_incomes, present_values, pv_terminal_value,
             intrinsic_value_per_share, max_buy_price, sum_pv_projections,
             equity_value, enterprise_value, terminal_value) = calculate_alphaspread_exact_dcf(
                base_rev, revenue_cagr, start_margin, end_margin, discount_rate,
                exit_multiple, shares_outstanding, total_cash, total_debt, margin_of_safety
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

            # Step 1
            o.insert(tk.END, "=== STEP 1: FORECAST PIPELINE & PRESENT VALUE ===\n\n")
            o.insert(tk.END, f"{'Year':<6} | {'Revenue':<13} | {'Margin':<8} | {'Future Val':<13} | {'Present Val':<13}\n")
            o.insert(tk.END, "-" * 66 + "\n")

            for i in range(5):
                year_label = self.projection_years[i]
                o.insert(tk.END, f"{year_label:<6} | {format_currency_short(revenues[i]):<13} | "
                                 f"{net_margins[i]*100:<7.1f}% | {format_currency_short(net_incomes[i]):<13} | "
                                 f"{format_currency_short(present_values[i]):<13}\n")

            o.insert(tk.END, "-" * 66 + "\n")
            o.insert(tk.END, f"Cumulative Explicit Projection PV Subtotal: {format_currency_short(sum_pv_projections)}\n\n")

            # Step 2 - abbreviated
            o.insert(tk.END, "=== STEP 2: TERMINAL VALUE & DISCOUNT ENGINE ===\n")
            o.insert(tk.END, f"Nominal Terminal Value = Year 5 Revenue × Exit Multiple\n")
            o.insert(tk.END, f"  {format_currency_short(revenues[-1])} × {exit_multiple:.2f}\n")
            o.insert(tk.END, f"  Subtotal Nominal TV = {format_currency_short(terminal_value)}\n\n")

            o.insert(tk.END, "Present Value of Terminal Value:\n")
            o.insert(tk.END, f"  {format_currency_short(terminal_value)}\n")
            o.insert(tk.END, "  " + "-" * 20 + "\n")
            o.insert(tk.END, f"  (1 + {discount_rate:.3f})^5\n")
            o.insert(tk.END, "  " + "═" * 30 + "\n")
            o.insert(tk.END, f"  PV of Terminal Value Subtotal = {format_currency_short(pv_terminal_value)}\n\n")

            # Step 3 - abbreviated
            o.insert(tk.END, "=== STEP 3: ENTERPRISE & EQUITY BRIDGE ===\n")
            o.insert(tk.END, f"Enterprise Value = Cumulative PV + PV of TV\n")
            o.insert(tk.END, f"  {format_currency_short(sum_pv_projections)} + {format_currency_short(pv_terminal_value)}\n")
            o.insert(tk.END, f"  Enterprise Value Subtotal = {format_currency_short(enterprise_value)}\n\n")

            o.insert(tk.END, f"Equity Value = Enterprise Value + Total Cash − Total Debt\n")
            o.insert(tk.END, f"  {format_currency_short(enterprise_value)} + {format_currency_short(total_cash)} − {format_currency_short(total_debt)}\n")
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
            hist_vals = [self.historical_ni_by_year.get(y, 0.0) for y in hist_years]

            proj_years = self.projection_years

            x_labels = [str(y) for y in hist_years] + [str(y) for y in proj_years]
            y_values = hist_vals + [ni / 1_000_000.0 for ni in net_incomes]
            colors = ['#7f8c8d'] * len(hist_years) + ['#5dade2'] * 5

            ax.bar(x_labels, y_values, color=colors, width=0.5)
            ax.set_title("Net Income Structural Trend Analysis ($ Millions)", fontsize=10, fontweight='bold')
            ax.set_xticklabels(x_labels, fontsize=7.5, rotation=45)
            ax.yaxis.set_major_formatter(
                plt.FuncFormatter(lambda val, loc: f"${val/1000:,.1f}B" if abs(val) >= 1000 else f"${val:,.0f}M")
            )

            ax.legend(handles=[
                Patch(facecolor='#7f8c8d', label='Historical GAAP Net Income'),
                Patch(facecolor='#5dade2', label='Projected Future Net Income')
            ], loc='upper left', fontsize=7.5)

            ax.grid(axis='y', linestyle='--', alpha=0.4)
            plt.tight_layout()

            self.canvas_widget = FigureCanvasTkAgg(fig, master=self.right_panel)
            self.canvas_widget.draw()
            self.canvas_widget.get_tk_widget().pack(fill=tk.BOTH, expand=tk.YES)
            plt.close(fig)

        except ValueError:
            messagebox.showerror("Input Error", "Verify parameters contain valid numbers.")

if __name__ == "__main__":
    root = tk.Tk()
    app = DCFApp(root)
    try:
        root.attributes('-zoomed', True)
    except Exception:
        root.geometry(f"{root.winfo_screenwidth()}x{root.winfo_screenheight()}+0+0")
    root.mainloop()