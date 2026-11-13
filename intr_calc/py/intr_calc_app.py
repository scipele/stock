import tkinter as tk
from tkinter import messagebox
from datetime import datetime
import json
import math
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

try:
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.patches import Patch
except ModuleNotFoundError as exc:
    raise SystemExit(
        "Missing dependency: matplotlib. Install it with:\n"
        "  python3 -m pip install matplotlib\n"
        "or create a project venv and run:\n"
        "  python3 -m venv .venv\n"
        "  . .venv/bin/activate\n"
        "  python -m pip install -r intr_calc/requirements.txt"
    ) from exc

try:
    from intr_calc_math import calculate_alphaspread_exact_dcf
    from intr_calc_format import format_currency_short, format_abbrev_number, parse_abbrev_number
except ModuleNotFoundError:
    sys.path.append(str(Path(__file__).resolve().parent))
    from intr_calc_math import calculate_alphaspread_exact_dcf
    from intr_calc_format import format_currency_short, format_abbrev_number, parse_abbrev_number

class DCFApp:
    SEC_TICKER_URL = "https://www.sec.gov/files/company_tickers.json"
    SEC_FACTS_URL_TEMPLATE = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
    SEC_SUBMISSIONS_URL_TEMPLATE = "https://data.sec.gov/submissions/CIK{cik}.json"

    def __init__(self, root):
        self.root = root
        self.root.title("Multi-Stage Fundamental Valuation Engine")
        self.root.geometry("2200x980")
        self.sec_ticker_map = None

        # Left Panel
        left_panel = tk.Frame(root, padx=15, pady=15, width=1200)
        left_panel.pack(side=tk.LEFT, fill=tk.Y)
        left_panel.pack_propagate(False)

        # Section 1: Fetch Web Data
        tk.Label(left_panel, text="1. Fetch Web Data", font=("Arial", 12, "bold")).pack(anchor=tk.W, pady=(0, 5))
        ticker_frame = tk.Frame(left_panel)
        ticker_frame.pack(fill=tk.X, pady=(0, 5))
        tk.Label(ticker_frame, text="Ticker:").pack(side=tk.LEFT)

        self.entry_ticker = tk.Entry(ticker_frame, width=10)
        self.entry_ticker.insert(0, "HLNE")
        self.entry_ticker.pack(side=tk.LEFT, padx=5)

        btn_fetch = tk.Button(ticker_frame, text="Fetch SEC Data", command=self.fetch_financials, bg="#d5f5e3")
        btn_fetch.pack(side=tk.LEFT, padx=5)

        self.lbl_market_price = tk.Label(left_panel, text="Current Price: N/A", font=("Arial", 11, "bold"), fg="#566573")
        self.lbl_market_price.pack(anchor=tk.W, pady=2)

        # Section 2: Manual Adjustments
        tk.Label(left_panel, text="2. Manual Adjustments", font=("Arial", 12, "bold")).pack(anchor=tk.W, pady=(15, 5))
        self.entries = {}

        fields = [
            ("Owner Earnings Base ($, M/B)", "owner_earnings", "1.000B"),
            ("Discount Rate (%)", "discount", "9.5"),
            ("Start Growth Rate (Yr 1) (%)", "start_growth", "19.0"),
            ("End Growth Rate (Yr 10) (%)", "end_growth", "3.0"),
            ("Terminal Growth Rate (%)", "terminal_growth", "3.0"),
            ("Shares Outstanding (#, M/B)", "shares", "100.000M"),
            ("Cash & Short-Term Investments ($, M/B)", "cash", "0M"),
            ("Total Debt (Long + Short) ($, M/B)", "debt", "0M"),
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

        self.txt_report_xscroll = tk.Scrollbar(left_panel, orient=tk.HORIZONTAL)
        self.txt_report_xscroll.pack(side=tk.BOTTOM, fill=tk.X)

        self.txt_report = tk.Text(
            left_panel,
            height=28,
            width=160,
            font=("Courier", 9),
            bg="#f8f9f9",
            relief=tk.SOLID,
            bd=1,
            wrap=tk.NONE,
            xscrollcommand=self.txt_report_xscroll.set,
            exportselection=False,
        )
        self.txt_report.pack(fill=tk.BOTH, expand=tk.YES)
        self.txt_report_xscroll.config(command=self.txt_report.xview)
        self.txt_report.bind("<Control-a>", self._report_select_all)
        self.txt_report.bind("<Control-A>", self._report_select_all)
        self.txt_report.bind("<Control-c>", self._report_copy_selection)
        self.txt_report.bind("<Control-C>", self._report_copy_selection)
        self.txt_report.bind("<Control-Insert>", self._report_copy_selection)

        # Right Panel (chart)
        self.right_panel = tk.Frame(root, bg="white", padx=10, pady=10)
        self.right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=tk.YES)

        self.canvas_widget = None
        self.current_stock_price = None
        self.last_fetch_components = None
        self.current_year_actual_owner_earnings_m = None
        self.current_year_reported_quarter_count = 0
        self.current_year_full_year_estimate_m = None
        self.ltm_owner_earnings_m = None

        # Dynamic years based on current calendar year
        self.current_year = datetime.now().year
        self.analysis_year = self.current_year
        self.projection_years = list(range(self.current_year + 1, self.current_year + 11))

        # Historical years include the five prior years plus current year.
        self.target_hist_years = list(range(self.current_year - 5, self.current_year + 1))
        self.historical_owner_earnings_by_year = {yr: 0.0 for yr in self.target_hist_years}

        self.run_calculation()

    def _report_select_all(self, event=None):
        self.txt_report.tag_add(tk.SEL, "1.0", tk.END)
        self.txt_report.mark_set(tk.INSERT, "1.0")
        self.txt_report.see(tk.INSERT)
        return "break"

    def _report_copy_selection(self, event=None):
        try:
            selected_text = self.txt_report.get(tk.SEL_FIRST, tk.SEL_LAST)
        except tk.TclError:
            return "break"
        self.root.clipboard_clear()
        self.root.clipboard_append(selected_text)
        return "break"

    def fetch_financials(self):
        ticker_str = self.entry_ticker.get().strip().upper()
        if not ticker_str:
            messagebox.showwarning("Warning", "Please enter a valid ticker.")
            return

        try:
            sec_data = self._fetch_from_sec(ticker_str)
            self.current_stock_price, price_source = self._fetch_market_price(ticker_str)
            if self.current_stock_price is not None:
                self.lbl_market_price.config(
                    text=f"Current Price: ${self.current_stock_price:,.2f} ({price_source})"
                )
            else:
                self.lbl_market_price.config(text=f"Current Price: N/A ({price_source})")
            self.last_fetch_components = sec_data["components"]

            self.entries['shares'].delete(0, tk.END)
            self.entries['shares'].insert(0, format_abbrev_number(float(sec_data["shares"])))

            self.entries['owner_earnings'].delete(0, tk.END)
            self.entries['owner_earnings'].insert(0, format_abbrev_number(float(sec_data["owner_earnings"])))

            self.entries['discount'].delete(0, tk.END)
            self.entries['discount'].insert(0, "9.5")
            self.entries['end_growth'].delete(0, tk.END)
            self.entries['end_growth'].insert(0, "3.0")
            self.entries['terminal_growth'].delete(0, tk.END)
            self.entries['terminal_growth'].insert(0, "3.0")

            self.entries['cash'].delete(0, tk.END)
            self.entries['cash'].insert(0, format_abbrev_number(float(sec_data["total_cash"])))
            self.entries['debt'].delete(0, tk.END)
            self.entries['debt'].insert(0, format_abbrev_number(float(abs(sec_data["total_debt"]))))

            available_years = sorted(sec_data["historical_owner_earnings_m"].keys())
            if len(available_years) >= 6:
                self.target_hist_years = available_years[-6:]
            else:
                self.target_hist_years = list(range(self.current_year - 5, self.current_year + 1))
            self.historical_owner_earnings_by_year = {yr: 0.0 for yr in self.target_hist_years}
            self.historical_owner_earnings_by_year.update({
                yr: sec_data["historical_owner_earnings_m"].get(yr, 0.0) for yr in self.target_hist_years
            })
            self.current_year_actual_owner_earnings_m = sec_data.get("current_year_actual_owner_earnings_m")
            self.current_year_reported_quarter_count = int(sec_data.get("current_year_reported_quarter_count", 0) or 0)
            self.current_year_full_year_estimate_m = sec_data.get("current_year_full_year_estimate_m")
            self.ltm_owner_earnings_m = sec_data.get("ltm_owner_earnings_m")
            self.analysis_year = sec_data.get("analysis_year", self.current_year)
            self.projection_years = list(range(self.analysis_year + 1, self.analysis_year + 11))
            est_growth_rate, est_growth_source = self._estimate_start_growth_rate(
                sec_data["historical_owner_earnings_m"],
                latest_owner_earnings_m=float(sec_data["owner_earnings"]) / 1_000_000.0 if sec_data.get("owner_earnings") else None,
                latest_year=self.analysis_year,
            )
            self.entries['start_growth'].delete(0, tk.END)
            self.entries['start_growth'].insert(0, f"{est_growth_rate * 100:.1f}")

            previous_years = sorted([yr for yr in self.target_hist_years if yr < self.analysis_year])[-5:]
            prior_items = [f"{yr}={self.historical_owner_earnings_by_year.get(yr, 0.0):,.1f}M" for yr in previous_years]
            self.last_fetch_components["section1_items"].append({
                "code": "1.10",
                "label": "Previous estimated Owner Earnings in reported data dollars (OCF - Maintenance CapEx - SBC)",
                "display": ", ".join(prior_items) if prior_items else "N/A",
                "source": sec_data["history_source"],
            })
            self.last_fetch_components["section1_items"].append({
                "code": "1.11",
                "label": "Auto-estimated Start Growth Rate",
                "display": f"{est_growth_rate*100:.1f}%",
                "source": est_growth_source,
            })
            self.run_calculation()

        except Exception as e:
            messagebox.showerror("Data Transfer Error",
                                 f"Failed fetching data for {ticker_str}:\n{str(e)}")

    def _sec_headers(self):
        return {
            "User-Agent": os.environ.get(
                "SEC_USER_AGENT",
                "stock-intrinsic-value/1.0 (contact: support@localhost)"
            ),
            "Accept": "application/json,text/plain,*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "Connection": "keep-alive",
            "Referer": "https://www.sec.gov/",
        }

    def _sec_get_json(self, url):
        req = urllib.request.Request(url, headers=self._sec_headers(), method="GET")
        try:
            with urllib.request.urlopen(req, timeout=25) as resp:
                body = resp.read().decode("utf-8")
                return json.loads(body)
        except urllib.error.HTTPError as exc:
            raise ValueError(f"SEC request failed ({exc.code}) for {url}") from exc
        except urllib.error.URLError as exc:
            raise ValueError(f"Unable to reach SEC endpoint: {url}") from exc
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON from SEC endpoint: {url}") from exc

    @staticmethod
    def _market_headers():
        return {
            "User-Agent": "Mozilla/5.0 (compatible; intrinsic-value-tool/1.0)",
            "Accept": "application/json,text/csv,text/plain,*/*",
        }

    def _fetch_market_price(self, ticker):
        ticker = ticker.strip().upper()
        if not ticker:
            return None, "No ticker"

        yahoo_url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=1d"
        req = urllib.request.Request(yahoo_url, headers=self._market_headers(), method="GET")
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                body = resp.read().decode("utf-8")
                payload = json.loads(body)
                result = payload.get("chart", {}).get("result", [])
                if result:
                    meta = result[0].get("meta", {})
                    price = self._to_float(meta.get("regularMarketPrice"))
                    if price and price > 0:
                        return price, "Yahoo Finance"
        except (urllib.error.HTTPError, urllib.error.URLError, json.JSONDecodeError, ValueError):
            pass

        stooq_url = f"https://stooq.com/q/l/?s={ticker.lower()}.us&i=d"
        req = urllib.request.Request(stooq_url, headers=self._market_headers(), method="GET")
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                body = resp.read().decode("utf-8").strip()
                lines = [line.strip() for line in body.splitlines() if line.strip()]
                if len(lines) >= 2:
                    headers = [h.strip().lower() for h in lines[0].split(",")]
                    values = [v.strip() for v in lines[1].split(",")]
                    if "close" in headers:
                        close_idx = headers.index("close")
                        if close_idx < len(values):
                            price = self._to_float(values[close_idx])
                            if price and price > 0:
                                return price, "Stooq"
        except (urllib.error.HTTPError, urllib.error.URLError, ValueError):
            pass

        return None, "Unavailable"

    def _load_ticker_map(self):
        if self.sec_ticker_map is not None:
            return self.sec_ticker_map

        raw = self._sec_get_json(self.SEC_TICKER_URL)
        mapping = {}
        for _, item in raw.items():
            ticker = str(item.get("ticker", "")).upper()
            cik = item.get("cik_str")
            if ticker and cik is not None:
                mapping[ticker] = f"{int(cik):010d}"
        self.sec_ticker_map = mapping
        return mapping

    @staticmethod
    def _parse_date(date_text):
        return datetime.strptime(date_text, "%Y-%m-%d")

    def _days_between(self, older_date, newer_date):
        if not older_date or not newer_date:
            return None
        try:
            return (self._parse_date(newer_date) - self._parse_date(older_date)).days
        except ValueError:
            return None

    def _is_stale_against_anchor(self, candidate_end, anchor_end, max_age_days=540):
        age_days = self._days_between(candidate_end, anchor_end)
        if age_days is None:
            return False
        return age_days > max_age_days

    def _sort_entries(self, entries):
        return sorted(
            entries,
            key=lambda e: (
                self._parse_date(e.get("end", "1900-01-01")),
                self._parse_date(e.get("filed", e.get("end", "1900-01-01")))
            ),
            reverse=True,
        )

    @staticmethod
    def _duration_days(entry):
        start = entry.get("start")
        end = entry.get("end")
        if not start or not end:
            return None
        try:
            return (datetime.strptime(end, "%Y-%m-%d") - datetime.strptime(start, "%Y-%m-%d")).days
        except ValueError:
            return None

    @staticmethod
    def _to_float(value):
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _extract_fact_entries(self, facts, taxonomy, tags, units):
        for tag in tags:
            for unit in units:
                entries = facts.get(taxonomy, {}).get(tag, {}).get("units", {}).get(unit, [])
                parsed = []
                for item in entries:
                    v = self._to_float(item.get("val"))
                    if v is None:
                        continue
                    parsed.append({
                        "val": v,
                        "start": item.get("start"),
                        "end": item.get("end"),
                        "form": item.get("form"),
                        "filed": item.get("filed"),
                        "fy": item.get("fy"),
                        "fp": item.get("fp"),
                    })
                if parsed:
                    return parsed, tag, unit
        return [], None, None

    def _extract_most_recent_fact_entries(self, facts, taxonomy, tags, units, quarterly=False):
        best_entries = []
        best_tag = None
        best_unit = None
        best_end = None

        for tag in tags:
            for unit in units:
                entries = facts.get(taxonomy, {}).get(tag, {}).get("units", {}).get(unit, [])
                parsed = []
                for item in entries:
                    v = self._to_float(item.get("val"))
                    if v is None:
                        continue
                    parsed.append({
                        "val": v,
                        "start": item.get("start"),
                        "end": item.get("end"),
                        "form": item.get("form"),
                        "filed": item.get("filed"),
                        "fy": item.get("fy"),
                        "fp": item.get("fp"),
                    })
                if not parsed:
                    continue

                candidate = self._unique_quarter_entries(parsed) if quarterly else parsed
                if not candidate:
                    continue

                ends = [c.get("end") for c in candidate if c.get("end")]
                if not ends:
                    continue
                newest = max(ends, key=self._parse_date)

                if best_end is None or self._parse_date(newest) > self._parse_date(best_end):
                    best_entries = parsed
                    best_tag = tag
                    best_unit = unit
                    best_end = newest

        return best_entries, best_tag, best_unit

    def _latest_instant_value(self, entries):
        candidates = [e for e in entries if e.get("end")]
        if not candidates:
            return None
        return self._sort_entries(candidates)[0]

    def _ttm_from_quarters(self, entries):
        q_entries = self._standalone_quarter_entries(entries)
        latest = sorted(q_entries, key=lambda e: self._parse_date(e["end"]), reverse=True)
        picked = latest[:4]
        if len(picked) < 4:
            return None, [], []
        ordered = list(reversed(picked))
        return (
            sum(e["val"] for e in picked),
            [e["val"] for e in ordered],
            [e["end"] for e in ordered],
        )

    def _is_quarter_entry(self, item):
        fp = str(item.get("fp", "")).upper()
        if fp in {"Q1", "Q2", "Q3", "Q4"} and item.get("end"):
            return True
        days = self._duration_days(item)
        if days is None or not item.get("end"):
            return False
        return 70 <= days <= 120

    def _unique_quarter_entries(self, entries):
        by_end = {}
        for item in entries:
            if not self._is_quarter_entry(item):
                continue
            end = item["end"]
            prev = by_end.get(end)
            if prev is None:
                by_end[end] = item
                continue

            def rank(candidate):
                duration = self._duration_days(candidate) or 999
                fp = str(candidate.get("fp", "")).upper()
                quarter_like = 1 if fp in {"Q1", "Q2", "Q3", "Q4"} else 0
                filed = self._parse_date(candidate.get("filed") or candidate.get("end"))
                return (quarter_like, -abs(duration - 90), filed)

            if rank(item) > rank(prev):
                by_end[end] = item
        return list(by_end.values())

    def _standalone_quarter_entries(self, entries):
        if not entries:
            return []

        parsed = []
        for item in entries:
            end = item.get("end")
            if not end:
                continue
            val = self._to_float(item.get("val"))
            if val is None:
                continue
            parsed.append(
                {
                    "val": val,
                    "start": item.get("start"),
                    "end": end,
                    "form": item.get("form"),
                    "filed": item.get("filed"),
                    "fy": item.get("fy"),
                    "fp": str(item.get("fp", "")).upper(),
                }
            )
        if not parsed:
            return []

        by_start_end = {}
        for item in self._sort_entries(parsed):
            key = (item.get("start"), item["end"])
            if key not in by_start_end:
                by_start_end[key] = item
        deduped = list(by_start_end.values())

        by_start = {}
        for item in deduped:
            start = item.get("start")
            if not start:
                continue
            by_start.setdefault(start, []).append(item)

        standalone = {}
        for start, group in by_start.items():
            ordered = sorted(group, key=lambda e: self._parse_date(e["end"]))
            durations = [d for d in (self._duration_days(e) for e in ordered) if d is not None]
            cumulative_style = any(d > 120 for d in durations)
            prev_val = None
            for item in ordered:
                end = item["end"]
                if cumulative_style:
                    if prev_val is None:
                        val = item["val"]
                    else:
                        val = item["val"] - prev_val
                    prev_val = item["val"]
                else:
                    val = item["val"]
                standalone[end] = val

        fallback_quarters = self._unique_quarter_entries(deduped)
        for item in fallback_quarters:
            standalone.setdefault(item["end"], item["val"])

        result = [
            {"end": end, "val": value}
            for end, value in standalone.items()
        ]
        return sorted(result, key=lambda e: self._parse_date(e["end"]))

    def _annual_values_by_year(self, entries):
        annual = {}
        for item in entries:
            days = self._duration_days(item)
            if days is None or days < 300 or days > 390:
                continue
            end = item.get("end")
            if not end:
                continue
            year_key = int(end[:4])
            prior = annual.get(year_key)
            item_filed = item.get("filed") or item.get("end") or "1900-01-01"
            prior_filed = (prior.get("filed") or prior.get("end") or "1900-01-01") if prior else "1900-01-01"
            if prior is None or self._parse_date(item_filed) > self._parse_date(prior_filed):
                annual[year_key] = item
        return {year: v["val"] for year, v in annual.items()}

    @staticmethod
    def _maintenance_capex_outflow(capex_outflow, depreciation_outflow):
        capex_val = max(0.0, capex_outflow or 0.0)
        dep_val = max(0.0, depreciation_outflow or 0.0)
        if dep_val > 0.0:
            return min(capex_val, dep_val)
        return capex_val

    def _annual_depreciation_by_year(self, facts):
        dep_tags = [
            "DepreciationDepletionAndAmortization",
            "DepreciationAndAmortization",
            "DepreciationAmortizationAndAccretionNet",
            "OtherDepreciationAndAmortization",
            "Depreciation",
        ]
        best_values = {}
        best_source = None
        best_rank = None
        for tag in dep_tags:
            dep_entries, _, _ = self._extract_fact_entries(facts, "us-gaap", [tag], ["USD"])
            dep_annual = self._annual_values_by_year(dep_entries)
            source_label = tag
            if not dep_annual:
                dep_quarters = self._standalone_quarter_entries(dep_entries)
                if dep_quarters:
                    dep_annual_from_quarters = {}
                    quarter_counts = {}
                    for item in dep_quarters:
                        end = item.get("end")
                        if not end:
                            continue
                        year = int(end[:4])
                        dep_annual_from_quarters[year] = dep_annual_from_quarters.get(year, 0.0) + max(0.0, item.get("val", 0.0))
                        quarter_counts[year] = quarter_counts.get(year, 0) + 1
                    dep_annual = {
                        y: v for y, v in dep_annual_from_quarters.items()
                        if quarter_counts.get(y, 0) >= 3
                    }
                    source_label = f"{tag} (from standalone quarters)"
            if not dep_annual:
                continue
            rank = (max(dep_annual.keys()), len(dep_annual))
            if best_rank is None or rank > best_rank:
                best_rank = rank
                best_values = dep_annual
                best_source = source_label
        return best_values, best_source

    def _estimate_start_growth_rate(self, historical_owner_earnings_m, latest_owner_earnings_m=None, latest_year=None):
        points = sorted(
            [(int(year), float(value)) for year, value in historical_owner_earnings_m.items() if value and value > 0.0],
            key=lambda item: item[0],
        )
        if latest_owner_earnings_m is not None and latest_owner_earnings_m > 0 and latest_year is not None:
            points = [p for p in points if p[0] != int(latest_year)]
            points.append((int(latest_year), float(latest_owner_earnings_m)))
            points = sorted(points, key=lambda item: item[0])
        if len(points) < 2:
            return 0.10, "Fallback 10.0% (insufficient positive history)"

        yoy_rates = []
        for (year0, val0), (year1, val1) in zip(points[:-1], points[1:]):
            if year1 - year0 != 1 or val0 <= 0 or val1 <= 0:
                continue
            rate = (val1 / val0) - 1.0
            if -0.90 <= rate <= 5.00:
                yoy_rates.append((year1, rate))

        recent_weighted_yoy = None
        if yoy_rates:
            clipped = [max(-0.50, min(1.00, r)) for _, r in yoy_rates]
            weights = list(range(1, len(clipped) + 1))
            recent_weighted_yoy = sum(r * w for r, w in zip(clipped, weights)) / sum(weights)

        def cagr_from_lookback(lookback_years):
            if len(points) < lookback_years + 1:
                return None
            base_year, base_val = points[-(lookback_years + 1)]
            last_year, last_val = points[-1]
            years = last_year - base_year
            if years <= 0 or base_val <= 0 or last_val <= 0:
                return None
            return (last_val / base_val) ** (1.0 / years) - 1.0

        cagr_3 = cagr_from_lookback(3)
        cagr_5 = cagr_from_lookback(5)

        log_trend = None
        trend_points = points[-6:] if len(points) > 6 else points[:]
        if len(trend_points) >= 3:
            xs = [p[0] for p in trend_points]
            ys = [math.log(p[1]) for p in trend_points if p[1] > 0]
            if len(ys) == len(xs):
                mean_x = sum(xs) / len(xs)
                mean_y = sum(ys) / len(ys)
                num = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
                den = sum((x - mean_x) ** 2 for x in xs)
                if den > 0:
                    slope = num / den
                    log_trend = math.exp(slope) - 1.0

        long_term_parts = []
        if cagr_3 is not None:
            long_term_parts.append(("CAGR3", cagr_3))
        if cagr_5 is not None:
            long_term_parts.append(("CAGR5", cagr_5))
        if log_trend is not None:
            long_term_parts.append(("LogTrend", log_trend))

        if recent_weighted_yoy is None and not long_term_parts:
            return 0.10, "Fallback 10.0% (no valid growth factors)"

        long_term_anchor = (
            sum(rate for _, rate in long_term_parts) / len(long_term_parts)
            if long_term_parts else recent_weighted_yoy
        )

        if yoy_rates:
            clipped = [max(-0.50, min(1.00, r)) for _, r in yoy_rates]
            mean_yoy = sum(clipped) / len(clipped)
            variance = sum((r - mean_yoy) ** 2 for r in clipped) / len(clipped)
            yoy_stdev = math.sqrt(variance)
        else:
            yoy_stdev = 0.0

        # Damp recent-growth influence when historical series is choppy.
        # stdev <= 10% => near full weight to recent; stdev >= 50% => mostly long-term anchor.
        stability_weight = 1.0 - max(0.0, min((yoy_stdev - 0.10) / 0.40, 1.0))
        if recent_weighted_yoy is None:
            stability_weight = 0.0

        estimated = (
            stability_weight * recent_weighted_yoy +
            (1.0 - stability_weight) * long_term_anchor
        ) if recent_weighted_yoy is not None else long_term_anchor
        estimated = max(-0.20, min(0.40, estimated))

        source_bits = []
        if recent_weighted_yoy is not None:
            source_bits.append(f"YoY(recency)={recent_weighted_yoy*100:.1f}%")
        for name, rate in long_term_parts:
            source_bits.append(f"{name}={rate*100:.1f}%")
        source_bits.append(f"YoY stdev={yoy_stdev*100:.1f}%")
        source_bits.append(f"Stability weight={stability_weight:.2f}")
        if latest_owner_earnings_m is not None and latest_year is not None:
            source_bits.append(f"BaselineOverride={latest_owner_earnings_m:,.1f}M@{int(latest_year)}")
        source_note = f"Auto-estimated from history ({', '.join(source_bits)})"
        return estimated, source_note

    def _require_ticker_cik(self, ticker):
        mapping = self._load_ticker_map()
        cik = mapping.get(ticker.upper())
        if not cik:
            raise ValueError(f"No SEC CIK found for ticker '{ticker}'")
        return cik

    def _fetch_from_sec(self, ticker):
        cik = self._require_ticker_cik(ticker)
        facts_doc = self._sec_get_json(self.SEC_FACTS_URL_TEMPLATE.format(cik=cik))
        _ = self._sec_get_json(self.SEC_SUBMISSIONS_URL_TEMPLATE.format(cik=cik))
        facts = facts_doc.get("facts", {})

        net_income_entries, net_income_tag, _ = self._extract_most_recent_fact_entries(
            facts, "us-gaap",
            ["NetIncomeLoss", "NetIncomeLossAvailableToCommonStockholdersBasic"],
            ["USD"],
            quarterly=True
        )
        net_income_ttm, _, net_income_periods = self._ttm_from_quarters(net_income_entries)
        net_income_anchor_end = net_income_periods[-1] if net_income_periods else None

        eps_entries, eps_tag, eps_unit = self._extract_most_recent_fact_entries(
            facts, "us-gaap", ["EarningsPerShareDiluted", "EarningsPerShareBasic"], ["USD/shares", "USD"], quarterly=True
        )
        eps_ttm, eps_components, eps_periods = self._ttm_from_quarters(eps_entries)
        eps_source_note = f"SEC us-gaap:{eps_tag} ({eps_unit})"
        eps_latest_end = eps_periods[-1] if eps_periods else None
        if eps_ttm is None:
            annual_eps_entries, annual_eps_tag, annual_eps_unit = self._extract_most_recent_fact_entries(
                facts, "us-gaap",
                ["EarningsPerShareDiluted", "EarningsPerShareBasic"],
                ["USD/shares", "USD"],
                quarterly=False
            )
            annual_eps_item = self._latest_instant_value(annual_eps_entries)
            if annual_eps_item and annual_eps_item.get("val") is not None:
                eps_ttm = float(annual_eps_item["val"])
                eps_components = [eps_ttm]
                eps_periods = [annual_eps_item.get("end")] if annual_eps_item.get("end") else []
                eps_latest_end = annual_eps_item.get("end")
                eps_tag = annual_eps_tag
                eps_unit = annual_eps_unit
                eps_source_note = f"SEC annual us-gaap:{eps_tag} ({eps_unit}) fallback"
            else:
                eps_ttm = 0.0
                eps_components = []
                eps_periods = []
                eps_latest_end = None
                eps_source_note = "No SEC EPS tag found"

        diluted_shares_entries, diluted_shares_tag, diluted_shares_unit = self._extract_most_recent_fact_entries(
            facts, "us-gaap",
            [
                "WeightedAverageNumberOfDilutedSharesOutstanding",
                "WeightedAverageNumberOfSharesOutstandingBasicAndDiluted",
            ],
            ["shares"],
            quarterly=True
        )
        diluted_shares_item = self._latest_instant_value(diluted_shares_entries)

        shares_entries, shares_tag, shares_unit = self._extract_fact_entries(
            facts, "dei",
            ["EntityCommonStockSharesOutstanding"],
            ["shares"]
        )
        if not shares_entries:
            shares_entries, shares_tag, shares_unit = self._extract_fact_entries(
                facts, "us-gaap",
                ["CommonStockSharesOutstanding"],
                ["shares"]
            )
        shares_item = self._latest_instant_value(shares_entries)

        if diluted_shares_item and diluted_shares_item.get("val", 0) > 0:
            shares = diluted_shares_item["val"]
            shares_source_tag = diluted_shares_tag
            shares_source_unit = diluted_shares_unit
            shares_source_note = f"SEC {shares_source_tag} ({shares_source_unit}) latest"
            shares_latest_end = diluted_shares_item.get("end")
        else:
            shares = shares_item["val"] if shares_item else 1.0
            shares_source_tag = shares_tag
            shares_source_unit = shares_unit
            shares_source_note = f"SEC {shares_source_tag} ({shares_source_unit}) latest" if shares_source_tag else None
            shares_latest_end = shares_item.get("end") if shares_item else None

        if shares <= 0:
            diluted_income_entries, diluted_income_tag, diluted_income_unit = self._extract_most_recent_fact_entries(
                facts, "us-gaap",
                ["NetIncomeLossAvailableToCommonStockholdersDiluted", "NetIncomeLossAvailableToCommonStockholdersBasic"],
                ["USD"],
                quarterly=False
            )
            diluted_income_item = self._latest_instant_value(diluted_income_entries)
            if diluted_income_item and eps_ttm and eps_ttm > 0:
                derived_shares = diluted_income_item["val"] / eps_ttm
                if derived_shares > 0:
                    shares = derived_shares
                    shares_source_note = (
                        f"Derived fallback: us-gaap:{diluted_income_tag} ({diluted_income_unit}) "
                        f"÷ EPS {eps_ttm:.4f}"
                    )
                    shares_latest_end = diluted_income_item.get("end")

        anchor_end = net_income_anchor_end
        eps_is_stale = self._is_stale_against_anchor(eps_latest_end, anchor_end) if eps_latest_end and anchor_end else False
        shares_is_stale = self._is_stale_against_anchor(shares_latest_end, anchor_end) if shares_latest_end and anchor_end else False

        if shares_is_stale and net_income_ttm and eps_ttm and eps_ttm > 0 and not eps_is_stale:
            refreshed_shares = net_income_ttm / eps_ttm
            if refreshed_shares > 0:
                shares = refreshed_shares
                shares_source_note = (
                    f"Derived from recent TTM net income ({net_income_anchor_end}) ÷ EPS {eps_ttm:.4f} "
                    f"(replaced stale share count as of {shares_latest_end})"
                )
                shares_latest_end = net_income_anchor_end
                shares_is_stale = False

        if eps_is_stale and net_income_ttm and shares and shares > 0:
            refreshed_eps = net_income_ttm / shares
            if refreshed_eps > 0:
                eps_ttm = refreshed_eps
                eps_components = [eps_ttm]
                eps_periods = [net_income_anchor_end] if net_income_anchor_end else []
                eps_source_note = (
                    f"Derived from recent SEC TTM net income ({net_income_anchor_end}) ÷ diluted shares {format_abbrev_number(shares)} "
                    f"(replaced stale EPS as of {eps_latest_end})"
                )
                eps_latest_end = net_income_anchor_end
                eps_is_stale = False

        if eps_is_stale and eps_latest_end:
            eps_source_note = f"{eps_source_note} [STALE as of {eps_latest_end}]"
        if shares_is_stale and shares_latest_end:
            shares_source_note = f"{shares_source_note} [STALE as of {shares_latest_end}]"

        combined_cash_entries, combined_cash_tag, combined_cash_unit = self._extract_most_recent_fact_entries(
            facts, "us-gaap",
            [
                "CashAndShortTermInvestments",
                "CashCashEquivalentsAndShortTermInvestments",
                "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
            ],
            ["USD"]
        )
        combined_cash_item = self._latest_instant_value(combined_cash_entries)

        cash_entries, cash_tag, cash_unit = self._extract_most_recent_fact_entries(
            facts, "us-gaap",
            ["CashAndCashEquivalentsAtCarryingValue"],
            ["USD"]
        )
        cash_item = self._latest_instant_value(cash_entries)

        short_term_entries, short_term_tag, short_term_unit = self._extract_most_recent_fact_entries(
            facts, "us-gaap",
            [
                "ShortTermInvestments",
                "MarketableSecuritiesCurrent",
                "AvailableForSaleSecuritiesCurrent",
                "AvailableForSaleSecuritiesDebtSecuritiesCurrent",
                "AvailableForSaleSecuritiesDebtMaturitiesWithinOneYearFairValue",
                "AvailableForSaleSecuritiesDebtMaturitiesWithinOneYearAmortizedCost",
            ],
            ["USD"]
        )
        short_term_item = self._latest_instant_value(short_term_entries)

        if combined_cash_item:
            total_cash = combined_cash_item["val"]
            cash_source_label = f"SEC us-gaap:{combined_cash_tag} ({combined_cash_unit}) latest"
        else:
            cash_val = cash_item["val"] if cash_item else 0.0
            short_term_val = short_term_item["val"] if short_term_item else 0.0
            total_cash = cash_val + short_term_val
            if cash_item and short_term_item:
                cash_source_label = (
                    f"SEC us-gaap:{cash_tag} ({cash_unit}) "
                    f"{format_currency_short(cash_val)} as of {cash_item.get('end')} + "
                    f"us-gaap:{short_term_tag} ({short_term_unit}) "
                    f"{format_currency_short(short_term_val)} as of {short_term_item.get('end')}"
                )
            elif cash_item:
                cash_source_label = f"SEC us-gaap:{cash_tag} ({cash_unit}) latest"
            elif short_term_item:
                cash_source_label = f"SEC us-gaap:{short_term_tag} ({short_term_unit}) latest"
            else:
                cash_source_label = "No SEC cash/short-term-investment tag found"

        long_term_debt_entries, long_term_debt_tag, long_term_debt_unit = self._extract_fact_entries(
            facts, "us-gaap",
            ["LongTermDebt", "LongTermDebtNoncurrent", "LongTermDebtAndCapitalLeaseObligations"],
            ["USD"]
        )
        long_term_debt_item = self._latest_instant_value(long_term_debt_entries)
        long_term_debt = long_term_debt_item["val"] if long_term_debt_item else 0.0

        short_term_debt_entries, short_term_debt_tag, short_term_debt_unit = self._extract_fact_entries(
            facts, "us-gaap",
            ["DebtCurrent", "ShortTermBorrowings", "CommercialPaper"],
            ["USD"]
        )
        short_term_debt_item = self._latest_instant_value(short_term_debt_entries)
        short_term_debt = short_term_debt_item["val"] if short_term_debt_item else 0.0

        total_debt = long_term_debt + short_term_debt
        debt_source_parts = []
        if long_term_debt_item:
            debt_source_parts.append(f"us-gaap:{long_term_debt_tag} ({long_term_debt_unit})")
        if short_term_debt_item:
            debt_source_parts.append(f"us-gaap:{short_term_debt_tag} ({short_term_debt_unit})")
        debt_source_label = (
            "SEC " + " + ".join(debt_source_parts) + " latest"
            if debt_source_parts else
            "No SEC debt tag found"
        )

        net_income_entries_for_periods, _, _ = self._extract_most_recent_fact_entries(
            facts, "us-gaap",
            ["NetIncomeLoss", "NetIncomeLossAvailableToCommonStockholdersBasic"],
            ["USD"],
            quarterly=True
        )
        _, _, net_income_periods = self._ttm_from_quarters(net_income_entries_for_periods)

        def recent_quarter_periods(*entry_sets):
            all_ends = []
            for entries in entry_sets:
                for item in self._standalone_quarter_entries(entries):
                    if item.get("end"):
                        all_ends.append(item["end"])
            if not all_ends:
                return []
            unique_ends = sorted(set(all_ends), key=self._parse_date, reverse=True)
            recent = list(reversed(unique_ends[:4]))
            return recent

        dep_candidate_entries = []
        for tag in [
            "DepreciationDepletionAndAmortization",
            "DepreciationAndAmortization",
            "DepreciationAmortizationAndAccretionNet",
            "OtherDepreciationAndAmortization",
            "Depreciation",
            "AmortizationOfDeferredCharges",
            "AmortizationOfIntangibleAssets",
        ]:
            entries = facts.get("us-gaap", {}).get(tag, {}).get("units", {}).get("USD", [])
            dep_candidate_entries.extend(entries)

        other_candidate_entries = []
        for tag in [
            "OtherNoncashIncomeExpense",
            "OtherNoncashExpense",
            "OtherNoncashIncome",
            "ShareBasedCompensation",
            "AssetImpairmentCharges",
            "DeferredTaxExpenseBenefit",
        ]:
            entries = facts.get("us-gaap", {}).get(tag, {}).get("units", {}).get("USD", [])
            other_candidate_entries.extend(entries)

        capex_candidate_entries = []
        for tag in [
            "PaymentsToAcquirePropertyPlantAndEquipment",
            "CapitalExpendituresIncurredButNotYetPaid",
        ]:
            entries = facts.get("us-gaap", {}).get(tag, {}).get("units", {}).get("USD", [])
            capex_candidate_entries.extend(entries)

        anchor_periods = recent_quarter_periods(
            eps_entries,
            net_income_entries_for_periods,
            dep_candidate_entries,
            other_candidate_entries,
            capex_candidate_entries,
        )
        if len(anchor_periods) < 4:
            anchor_periods = net_income_periods[:]

        def values_for_periods(entries, periods):
            quarter_entries = self._standalone_quarter_entries(entries)
            value_by_period = {e["end"]: e["val"] for e in quarter_entries}
            return [value_by_period.get(p, 0.0) for p in periods]

        def select_tag_values(taxonomy, tags, units, periods):
            best_tag = None
            best_unit = None
            best_values = []
            best_coverage = -1
            for tag in tags:
                for unit in units:
                    entries = facts.get(taxonomy, {}).get(tag, {}).get("units", {}).get(unit, [])
                    parsed = []
                    for item in entries:
                        v = self._to_float(item.get("val"))
                        if v is None:
                            continue
                        parsed.append({
                            "val": v,
                            "start": item.get("start"),
                            "end": item.get("end"),
                            "form": item.get("form"),
                            "filed": item.get("filed"),
                            "fy": item.get("fy"),
                            "fp": item.get("fp"),
                        })
                    if not parsed:
                        continue
                    vals = values_for_periods(parsed, periods)
                    coverage = sum(1 for x in vals if x != 0.0)
                    if coverage > best_coverage:
                        best_coverage = coverage
                        best_tag = tag
                        best_unit = unit
                        best_values = vals
            return best_tag, best_unit, best_values

        dep_tag, dep_unit, dep_components = select_tag_values(
            "us-gaap",
            [
                "DepreciationDepletionAndAmortization",
                "DepreciationAndAmortization",
                "DepreciationAmortizationAndAccretionNet",
                "OtherDepreciationAndAmortization",
                "Depreciation",
            ],
            ["USD"],
            anchor_periods
        )
        dep_periods = anchor_periods[:]
        dep_non_zero_count = sum(1 for v in dep_components if v != 0.0)
        dep_source_note = f"SEC us-gaap:{dep_tag} ({dep_unit})"
        dep_component_tags_used = set()
        if dep_non_zero_count < 2:
            dep_fallback_tags = [
                "Depreciation",
                "AmortizationOfDeferredCharges",
                "AmortizationOfIntangibleAssets",
            ]
            fallback_total = [0.0 for _ in anchor_periods]
            fallback_sources = []
            for fb_tag in dep_fallback_tags:
                fb_entries, _, _ = self._extract_fact_entries(facts, "us-gaap", [fb_tag], ["USD"])
                fb_vals = values_for_periods(fb_entries, anchor_periods)
                if not fb_vals:
                    continue
                if any(v != 0.0 for v in fb_vals):
                    fallback_sources.append(fb_tag)
                for idx, value in enumerate(fb_vals):
                    fallback_total[idx] += value
            fallback_non_zero = sum(1 for v in fallback_total if v != 0.0)
            if fallback_non_zero > dep_non_zero_count:
                dep_components = fallback_total
                dep_source_note = "SEC composite: " + " + ".join(fallback_sources)
                dep_component_tags_used = set(fallback_sources)

        depreciation_depletion = max(0.0, sum(dep_components))

        other_non_cash_components = []
        other_non_cash_sources = []
        other_non_cash_periods = []

        direct_other_tag, direct_other_unit, direct_components = select_tag_values(
            "us-gaap",
            ["OtherNoncashIncomeExpense", "OtherNoncashExpense", "OtherNoncashIncome"],
            ["USD"],
            anchor_periods
        )
        direct_ttm = sum(direct_components) if direct_components else None
        direct_periods = anchor_periods[:]

        if direct_ttm is not None:
            other_non_cash_items = max(0.0, direct_ttm)
            other_non_cash_components = [max(0.0, v) for v in direct_components]
            other_non_cash_sources.append(f"{direct_other_tag}={format_currency_short(other_non_cash_items)}")
            other_non_cash_periods = direct_periods
        else:
            component_tags = [
                "AssetImpairmentCharges",
                "DeferredTaxExpenseBenefit",
                "AmortizationOfDeferredCharges",
                "AmortizationOfIntangibleAssets",
            ]
            component_tags = [tag for tag in component_tags if tag not in dep_component_tags_used]
            aggregate_by_quarter = {p: 0.0 for p in anchor_periods}
            for tag in component_tags:
                entries, _, _ = self._extract_fact_entries(facts, "us-gaap", [tag], ["USD"])
                if not entries:
                    continue
                vals = values_for_periods(entries, anchor_periods)
                if not vals:
                    continue
                for idx, period in enumerate(anchor_periods):
                    aggregate_by_quarter[period] += max(0.0, vals[idx])
                ttm_val, _, _ = self._ttm_from_quarters(entries)
                if ttm_val is not None:
                    other_non_cash_sources.append(f"{tag}={format_currency_short(max(0.0, ttm_val))}")

            other_non_cash_components = [aggregate_by_quarter[d] for d in anchor_periods]
            other_non_cash_periods = anchor_periods[:]
            other_non_cash_items = sum(other_non_cash_components)

        capex_tag, capex_unit, capex_components = select_tag_values(
            "us-gaap",
            ["PaymentsToAcquirePropertyPlantAndEquipment", "CapitalExpendituresIncurredButNotYetPaid"],
            ["USD"],
            anchor_periods
        )
        capex_periods = anchor_periods[:]
        capex_source_note = f"SEC us-gaap:{capex_tag} ({capex_unit})" if capex_tag else "No SEC capex tag found"

        if not capex_components or not any(v != 0.0 for v in capex_components):
            ppe_entries, ppe_tag, ppe_unit = self._extract_fact_entries(
                facts, "us-gaap",
                ["PropertyPlantAndEquipmentNet"],
                ["USD"]
            )
            if ppe_entries:
                ppe_by_end = {e["end"]: e["val"] for e in self._unique_quarter_entries(ppe_entries)}
                ppe_fallback = []
                for idx, period in enumerate(anchor_periods):
                    current_val = ppe_by_end.get(period)
                    prev_period = anchor_periods[idx - 1] if idx > 0 else None
                    prev_val = ppe_by_end.get(prev_period) if prev_period else current_val
                    dep_val = dep_components[idx] if idx < len(dep_components) else 0.0
                    if current_val is None or prev_val is None:
                        ppe_fallback.append(0.0)
                    else:
                        ppe_fallback.append(max(0.0, (current_val - prev_val) + dep_val))
                if any(v > 0.0 for v in ppe_fallback):
                    capex_tag = f"{ppe_tag} fallback"
                    capex_unit = ppe_unit
                    capex_components = ppe_fallback
                    capex_periods = anchor_periods[:]
                    capex_source_note = "SEC balance-sheet fallback: ΔNet PP&E + current-quarter depreciation"

        maintenance_capex_components = []
        for idx, capex_val in enumerate(capex_components):
            dep_val = dep_components[idx] if idx < len(dep_components) else 0.0
            maintenance_capex_components.append(self._maintenance_capex_outflow(capex_val, dep_val))
        maintenance_capex_outflow = sum(maintenance_capex_components) if maintenance_capex_components else 0.0
        capital_expenditures = -maintenance_capex_outflow
        capex_source_note = (
            f"{capex_source_note}; maintenance proxy=min(CapEx, Depreciation) per quarter"
        )

        gaap_baseline_source = "1.01 × 1.02"
        gaap_net_income_baseline = None
        if net_income_ttm is not None and (eps_is_stale or shares_is_stale):
            gaap_net_income_baseline = net_income_ttm
            gaap_baseline_source = f'us-gaap:{net_income_tag or "NetIncomeLoss"} TTM (freshness override)'
        elif eps_ttm is not None and shares is not None:
            gaap_net_income_baseline = eps_ttm * shares
        else:
            gaap_net_income_baseline = net_income_ttm or 0.0
            gaap_baseline_source = f'us-gaap:{net_income_tag or "NetIncomeLoss"} TTM'

        owner_earnings = gaap_net_income_baseline + depreciation_depletion + other_non_cash_items + capital_expenditures

        op_cf_entries, op_cf_tag, _ = self._extract_fact_entries(
            facts, "us-gaap",
            ["NetCashProvidedByUsedInOperatingActivities", "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations"],
            ["USD"]
        )
        annual_op_cf = self._annual_values_by_year(op_cf_entries)
        annual_capex_entries, annual_capex_tag, _ = self._extract_fact_entries(
            facts, "us-gaap",
            ["PaymentsToAcquirePropertyPlantAndEquipment", "CapitalExpendituresIncurredButNotYetPaid"],
            ["USD"]
        )
        annual_capex = self._annual_values_by_year(annual_capex_entries)
        annual_sbc_entries, annual_sbc_tag, _ = self._extract_fact_entries(
            facts, "us-gaap",
            ["ShareBasedCompensation"],
            ["USD"]
        )
        annual_sbc = self._annual_values_by_year(annual_sbc_entries)
        annual_dep, annual_dep_tag = self._annual_depreciation_by_year(facts)

        all_annual_years = set(annual_op_cf.keys()) | set(annual_capex.keys()) | set(annual_sbc.keys()) | set(annual_dep.keys())
        historical_owner_earnings_m = {}
        for year in all_annual_years:
            ocf = annual_op_cf.get(year, 0.0)
            capex_outflow = annual_capex.get(year, 0.0)
            dep_outflow = annual_dep.get(year, 0.0)
            maintenance_capex_outflow_annual = self._maintenance_capex_outflow(capex_outflow, dep_outflow)
            sbc_addback = annual_sbc.get(year, 0.0)
            owner_earnings_annual = ocf - maintenance_capex_outflow_annual - sbc_addback
            historical_owner_earnings_m[year] = owner_earnings_annual / 1_000_000.0

        current_year_quarter_actual_m = None
        current_year_full_year_estimate_m = None
        ocf_quarters = self._standalone_quarter_entries(op_cf_entries)
        capex_quarters = self._standalone_quarter_entries(annual_capex_entries)
        sbc_quarters = self._standalone_quarter_entries(annual_sbc_entries)
        ocf_by_end = {e["end"]: e["val"] for e in ocf_quarters}
        capex_by_end = {e["end"]: e["val"] for e in capex_quarters}
        sbc_by_end = {e["end"]: e["val"] for e in sbc_quarters}
        dep_by_end = {period: dep_components[idx] for idx, period in enumerate(anchor_periods)}
        available_quarter_years = sorted({int(end[:4]) for end in ocf_by_end.keys()})
        analysis_year = available_quarter_years[-1] if available_quarter_years else self.current_year
        current_year_periods = sorted(
            [end for end in ocf_by_end.keys() if int(end[:4]) == analysis_year],
            key=self._parse_date,
        )
        if current_year_periods:
            current_year_owner_earnings = 0.0
            for period_end in current_year_periods:
                ocf_val = ocf_by_end.get(period_end, 0.0)
                capex_val = capex_by_end.get(period_end, 0.0)
                dep_val = dep_by_end.get(period_end, 0.0)
                maintenance_capex_val = self._maintenance_capex_outflow(capex_val, dep_val)
                sbc_val = sbc_by_end.get(period_end, 0.0)
                current_year_owner_earnings += (ocf_val - maintenance_capex_val - sbc_val)
            current_year_quarter_actual_m = current_year_owner_earnings / 1_000_000.0
            quarter_count = len(current_year_periods)
            if quarter_count >= 4:
                current_year_full_year_estimate_m = current_year_quarter_actual_m
            elif quarter_count > 0:
                current_year_full_year_estimate_m = current_year_quarter_actual_m * (4.0 / float(quarter_count))

        components = {
            "eps_ttm": eps_ttm if eps_ttm is not None else 0.0,
            "shares": shares,
            "gaap_baseline": gaap_net_income_baseline,
            "depreciation_depletion": depreciation_depletion,
            "other_non_cash_items": other_non_cash_items,
            "capital_expenditures": capital_expenditures,
            "owner_earnings": owner_earnings,
            "total_cash": total_cash,
            "total_debt": -abs(total_debt),
            "section1_items": [
                {"code": "1.01", "label": "GAAP EPS (TTM)", "display": f"{(eps_ttm if eps_ttm is not None else 0.0):.4f}", "source": eps_source_note, "components": eps_components, "periods": eps_periods},
                {"code": "1.02", "label": "Shares Outstanding (Diluted)", "display": format_abbrev_number(float(shares)), "source": (shares_source_note or "No SEC share-count tag found")},
                {"code": "1.03", "label": "GAAP Net Income Baseline", "display": format_currency_short(gaap_net_income_baseline), "source": gaap_baseline_source},
                {"code": "1.04", "label": "Depreciation/Depletion", "display": format_currency_short(depreciation_depletion), "source": dep_source_note, "components": dep_components, "periods": dep_periods},
                {"code": "1.05", "label": "Other non-cash items", "display": format_currency_short(other_non_cash_items), "source": ", ".join(other_non_cash_sources) or "No SEC non-cash tag values found", "components": other_non_cash_components, "periods": other_non_cash_periods},
                {"code": "1.06", "label": "Maintenance Capital Expenditures", "display": format_currency_short(capital_expenditures), "source": capex_source_note, "components": [-abs(v) for v in maintenance_capex_components], "periods": capex_periods},
                {"code": "1.07", "label": "Owner Earnings (1.03+1.04+1.05+1.06)", "display": format_currency_short(owner_earnings), "source": "Program calc: 1.03 + 1.04 + 1.05 + 1.06"},
                {"code": "1.08", "label": "Cash and Short Term Investments", "display": format_currency_short(total_cash), "source": cash_source_label},
                {"code": "1.09", "label": "Total Debt (Long + Short)", "display": format_currency_short(-abs(total_debt)), "source": debt_source_label},
            ],
        }

        return {
            "shares": shares,
            "owner_earnings": owner_earnings,
            "total_cash": total_cash,
            "total_debt": total_debt,
            "historical_owner_earnings_m": historical_owner_earnings_m,
            "current_year_actual_owner_earnings_m": current_year_quarter_actual_m,
            "current_year_reported_quarter_count": len(current_year_periods),
            "current_year_full_year_estimate_m": current_year_full_year_estimate_m,
            "ltm_owner_earnings_m": owner_earnings / 1_000_000.0,
            "analysis_year": analysis_year,
            "history_source": (
                f"SEC annual: {op_cf_tag or 'NetCashProvidedByUsedInOperatingActivities'}"
                f" - maintenance proxy min({annual_capex_tag or 'PaymentsToAcquirePropertyPlantAndEquipment'}, {annual_dep_tag or 'Depreciation'})"
                f" - {annual_sbc_tag or 'ShareBasedCompensation'}"
            ),
            "components": components,
            "cik": cik,
        }

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
                o.insert(tk.END, "SECTION 1 DATA USED (Spreadsheet numbering):\n")
                for item in c.get("section1_items", []):
                    o.insert(tk.END, f"  {item['code']} {item['label']}: {item['display']}\n")
                    o.insert(tk.END, f"      source: {item['source']}\n")
                    if item.get("components"):
                        if item["code"] == "1.01":
                            component_vals = ", ".join(f"{v:.4f}" for v in item["components"])
                        else:
                            component_vals = ", ".join(format_currency_short(v) for v in item["components"])
                        o.insert(tk.END, f"      last 4 quarters: {component_vals}\n")
                        if item.get("periods"):
                            o.insert(tk.END, f"      quarter end dates: {', '.join(item['periods'])}\n")
                    o.insert(tk.END, "\n")
                o.insert(tk.END, f"-----------------------------------------\n\n")

            o.insert(tk.END, "=== PAST OWNER EARNINGS (FULL-YEAR REPORTED) ===\n\n")
            o.insert(tk.END, f"{'Year':<6} | {'Owner Earnings':<15}\n")
            o.insert(tk.END, "-" * 28 + "\n")

            full_year_hist_years = [y for y in self.target_hist_years if y < self.analysis_year]
            for hist_year in full_year_hist_years:
                owner_earnings_m = self.historical_owner_earnings_by_year.get(hist_year, 0.0)
                owner_earnings_amount = owner_earnings_m * 1_000_000.0
                o.insert(
                    tk.END,
                    f"{hist_year:<6} | {format_currency_short(owner_earnings_amount):<15}\n"
                )

            o.insert(tk.END, "-" * 28 + "\n\n")
            if self.current_year_actual_owner_earnings_m is not None:
                o.insert(
                    tk.END,
                    f"Current-year reported-to-date owner earnings ({self.analysis_year}, partial period): "
                    f"{format_currency_short(self.current_year_actual_owner_earnings_m * 1_000_000.0)}\n\n"
                )
            if self.current_year_full_year_estimate_m is not None:
                o.insert(
                    tk.END,
                    f"Current-year full-year estimate ({self.analysis_year} FY run-rate): "
                    f"{format_currency_short(self.current_year_full_year_estimate_m * 1_000_000.0)}\n"
                )
            if self.ltm_owner_earnings_m is not None:
                o.insert(
                    tk.END,
                    f"LTM owner earnings baseline used for valuation: "
                    f"{format_currency_short(self.ltm_owner_earnings_m * 1_000_000.0)}\n\n"
                )

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

            debt_deduction = -abs(total_debt)
            o.insert(tk.END, f"Equity Value = Corporate Value + Total Cash - Total Debt\n")
            o.insert(tk.END, f"  {format_currency_short(corporate_value)} + {format_currency_short(total_cash)} + {format_currency_short(debt_deduction)}\n")
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

            hist_years = [y for y in self.target_hist_years if y < self.analysis_year]
            hist_map = {year: self.historical_owner_earnings_by_year.get(year, 0.0) for year in hist_years}
            current_year_estimate_m = (
                self.current_year_full_year_estimate_m
                if self.current_year_full_year_estimate_m is not None
                else (base_owner_earnings / 1_000_000.0)
            )

            proj_years = self.projection_years[:10]
            proj_map = {
                year: (future_values[idx] / 1_000_000.0)
                for idx, year in enumerate(proj_years)
            }

            plot_years = sorted(set(hist_map.keys()) | set(proj_map.keys()) | {self.analysis_year})
            x_positions = list(range(len(plot_years)))
            x_labels = []
            for year in plot_years:
                if year < self.analysis_year:
                    x_labels.append(f"{year}A")
                elif year == self.analysis_year:
                    x_labels.append(f"{year} FYE")
                else:
                    x_labels.append(f"{year}E")

            historical_components = []
            projected_components = []
            projected_bottoms = []
            mixed_sign_components = []
            total_values = []

            for year in plot_years:
                hist_val = hist_map.get(year, 0.0)
                proj_val = proj_map.get(year, 0.0)

                if year == self.analysis_year:
                    actual_val = float(self.current_year_actual_owner_earnings_m or 0.0)
                    estimated_val = current_year_estimate_m - actual_val
                elif year in hist_map and year in proj_map:
                    actual_val = hist_val
                    estimated_val = max(0.0, proj_val - hist_val)
                elif year in proj_map:
                    actual_val = 0.0
                    estimated_val = proj_val
                else:
                    actual_val = hist_val
                    estimated_val = 0.0

                historical_components.append(actual_val)
                projected_components.append(estimated_val)
                if actual_val == 0.0 or estimated_val == 0.0 or ((actual_val > 0) == (estimated_val > 0)):
                    projected_bottoms.append(actual_val)
                    mixed_sign_components.append(False)
                else:
                    projected_bottoms.append(0.0)
                    mixed_sign_components.append(True)
                total_values.append(actual_val + estimated_val)

            hist_bars = ax.bar(
                x_positions,
                historical_components,
                color="#c7ced6",
                edgecolor="#7f8c8d",
                linewidth=0.6,
                width=0.55,
                label="Historical / Reported Owner Earnings",
            )
            proj_bars = ax.bar(
                x_positions,
                projected_components,
                bottom=projected_bottoms,
                color="#a8d8ff",
                edgecolor="#2e86c1",
                linewidth=0.6,
                width=0.55,
                label="Estimated / Projected Owner Earnings",
            )
            ax.set_title("Owner Earnings Trend Analysis (A=Actual FY, FYE=Current-Year Full-Year Estimate, E=Estimated; $ Millions)", fontsize=10, fontweight='bold')
            ax.set_xticks(x_positions)
            ax.set_xticklabels(x_labels, fontsize=7.5, rotation=45)
            ax.yaxis.set_major_formatter(
                plt.FuncFormatter(lambda val, loc: f"${val/1000:,.1f}B" if abs(val) >= 1000 else f"${val:,.0f}M")
            )

            max_abs_val = max((abs(v) for v in total_values), default=0.0)
            value_offset = min(max(max_abs_val * 0.006, 4.0), 12.0)
            for idx, (bar, value_m) in enumerate(zip(hist_bars, total_values)):
                if plot_years[idx] == self.analysis_year:
                    continue
                label = f"${value_m/1000:,.2f}B" if abs(value_m) >= 1000 else f"${value_m:,.0f}M"
                x = bar.get_x() + bar.get_width() / 2.0
                if value_m >= 0:
                    y = value_m + value_offset
                    va = "bottom"
                else:
                    y = value_m - value_offset
                    va = "top"
                ax.text(x, y, label, ha="center", va=va, fontsize=6.7, color="#000000", fontweight="bold")

            if self.analysis_year in plot_years:
                idx = plot_years.index(self.analysis_year)
                actual_val = historical_components[idx]
                estimated_val = projected_components[idx]
                if actual_val != 0 and estimated_val != 0:
                    cx = x_positions[idx]
                    est_bottom = projected_bottoms[idx]
                    actual_mid = actual_val * 0.5
                    est_mid = est_bottom + (estimated_val * 0.5)
                    min_sep = max(20.0, max_abs_val * 0.03)
                    if abs(est_mid - actual_mid) < min_sep:
                        est_mid += min_sep if estimated_val >= 0 else -min_sep
                    ax.text(
                        cx,
                        actual_mid,
                        f"Actual {format_currency_short(actual_val * 1_000_000.0)}",
                        ha="center",
                        va="center",
                        fontsize=6.4,
                        color="#000000",
                        fontweight="bold",
                    )
                    net_val = actual_val + estimated_val
                    net_label = f"Net {format_currency_short(net_val * 1_000_000.0)}"
                    if net_val >= 0:
                        net_y = net_val + value_offset
                        net_va = "bottom"
                    else:
                        net_y = net_val - value_offset
                        net_va = "top"
                    ax.text(
                        cx,
                        net_y,
                        net_label,
                        ha="center",
                        va=net_va,
                        fontsize=6.2,
                        color="#000000",
                        fontweight="bold",
                    )
                else:
                    cx = x_positions[idx]
                    net_val = actual_val + estimated_val
                    net_label = f"{format_currency_short(net_val * 1_000_000.0)}"
                    if net_val >= 0:
                        net_y = net_val + value_offset
                        net_va = "bottom"
                    else:
                        net_y = net_val - value_offset
                        net_va = "top"
                    ax.text(
                        cx,
                        net_y,
                        net_label,
                        ha="center",
                        va=net_va,
                        fontsize=6.7,
                        color="#000000",
                        fontweight="bold",
                    )
                    if estimated_val != 0:
                        est_mid = projected_bottoms[idx] + (estimated_val * 0.5)
                        ax.text(
                            cx,
                            est_mid,
                            f"Est {format_currency_short(estimated_val * 1_000_000.0)}",
                            ha="center",
                            va="center",
                            fontsize=6.4,
                            color="#000000",
                            fontweight="bold",
                        )

            ax.legend(handles=[
                Patch(facecolor='#c7ced6', label='Historical / Reported Owner Earnings'),
                Patch(facecolor='#a8d8ff', label='Estimated / Projected Owner Earnings')
            ], loc='upper left', fontsize=7.5)

            ax.grid(axis='y', linestyle='--', alpha=0.4)
            plt.tight_layout()

            self.canvas_widget = FigureCanvasTkAgg(fig, master=self.right_panel)
            self.canvas_widget.draw()
            self.canvas_widget.get_tk_widget().pack(fill=tk.BOTH, expand=tk.YES)
            plt.close(fig)

        except ValueError:
            messagebox.showerror("Input Error", "Verify parameters contain valid numbers. M/B/T suffixes are supported.")

def main():
    root = tk.Tk()
    DCFApp(root)
    try:
        root.attributes('-zoomed', True)
    except Exception:
        root.geometry(f"{root.winfo_screenwidth()}x{root.winfo_screenheight()}+0+0")
    root.mainloop()


if __name__ == "__main__":
    main()