import os
import sys
import pandas as pd
import yfinance as yf

def main():
    ticker_file = "/home/dev/stock/buy_opp/data/tickers_sp_500.csv"
    report_file = "/home/dev/stock/intr_buy/output/combined_report.csv"
    output_xlsx = "/home/dev/stock/dividends/output/dividend_analysis.xlsx"
    output_csv = "/home/dev/stock/dividends/output/dividend_analysis.csv"
    
    print(f"   [Python] Reading S&P 500 tickers from: {ticker_file}")
    
    if not os.path.exists(ticker_file):
        print(f"   [Error] Centralized ticker file not found at: {ticker_file}")
        sys.exit(1)
        
    try:
        df_tickers = pd.read_csv(ticker_file)
        if 'Symbol' in df_tickers.columns:
            tickers = df_tickers['Symbol'].dropna().astype(str).tolist()
        else:
            tickers = df_tickers.iloc[:, 0].dropna().astype(str).tolist()
    except Exception as e:
        print(f"   [Error] Could not read CSV file: {e}")
        sys.exit(1)
        
    tickers = [t.replace('.', '-').strip() for t in tickers]
    total = len(tickers)
    
    rank_lookup = {}
    score_lookup = {}
    if os.path.exists(report_file):
        print(f"   [Python] Found external report mapping index at: {report_file}")
        try:
            df_report = pd.read_csv(report_file)
            if 'Ticker' in df_report.columns:
                df_report['Ticker_Clean'] = df_report['Ticker'].astype(str).str.replace('.', '-', regex=False).str.strip()
                if 'Rank' in df_report.columns:
                    rank_lookup = dict(zip(df_report['Ticker_Clean'], df_report['Rank']))
                if 'CombinedScore' in df_report.columns:
                    score_lookup = dict(zip(df_report['Ticker_Clean'], df_report['CombinedScore']))
        except Exception as e:
            print(f"   [Warning] Failed to parse ranking framework accurately: {e}")

    print(f"   [Python] Scanning {total} tickers for metrics...")
    screened_data = []
    
    for idx, ticker in enumerate(tickers):
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="2y", interval="1d")
            
            if hist.empty or len(hist) < 200:
                continue
                
            all_divs = hist['Dividends'][hist['Dividends'] > 0]
            
            if all_divs.empty:
                continue
                
            latest_div_date = all_divs.index[-1]
            
            # FIXED LOOKBACK WINDOW: 
            # 330 days avoids capturing the 5th overlapping quarter from 365 days ago,
            # while perfectly preserving exactly 4 quarterly or 12 monthly payments.
            start_ttm_window = latest_div_date - pd.Timedelta(days=330)
            ttm_div_series = all_divs.loc[start_ttm_window:latest_div_date]
            
            if ttm_div_series.empty:
                continue
                
            median_payment = ttm_div_series.median()
            outlier_threshold = median_payment * 2.5
            
            regular_divs = ttm_div_series[ttm_div_series <= outlier_threshold]
            special_divs = ttm_div_series[ttm_div_series > outlier_threshold]
            
            ttm_regular_total = regular_divs.sum()
            ttm_special_total = special_divs.sum()
            ttm_grand_total = ttm_regular_total + ttm_special_total
            
            if ttm_regular_total <= 0:
                continue
                
            current_price = hist['Close'].iloc[-1]
            
            # Yield calculations
            annual_yield_wo_special = (ttm_regular_total / current_price) * 100
            annual_yield_w_special = (ttm_grand_total / current_price) * 100
            
            closes = hist['Close']
            sma_200 = closes.rolling(window=200).mean().iloc[-1]
            sma_50 = closes.rolling(window=50).mean().iloc[-1]
            
            if current_price >= sma_200 * 0.95 and current_price <= sma_200 * 1.05:
                stability = "Stable"
            else:
                stability = "Volatile"
            
            if sma_50 > sma_200 * 1.02 and current_price > sma_50:
                direction = "Increasing"
            elif sma_50 < sma_200 * 0.98 and current_price < sma_50:
                direction = "Declining"
            else:
                direction = "Flat/Consolidating"
            
            screened_data.append({
                "Master Rank": rank_lookup.get(ticker, "N/A"),
                "Ticker": ticker,
                "Current Price ($)": round(current_price, 2),
                "TTM Regular Dividends ($)": round(ttm_regular_total, 2),
                "Special Dividends ($)": round(ttm_special_total, 2),
                "Annual Yield (With Special %)": round(annual_yield_w_special, 2),
                "Annual Yield (Without Special %):": round(annual_yield_wo_special, 2),
                "Stability (Long-Term)": stability,
                "Price Direction": direction,
                "Combined Score": score_lookup.get(ticker, "N/A")
            })
            
        except Exception:
            continue
            
        if (idx + 1) % 50 == 0 or (idx + 1) == total:
            print(f"            → Processed {idx + 1}/{total} stocks...")

    if screened_data:
        df_results = pd.DataFrame(screened_data)
        df_results = df_results.sort_values(by="Annual Yield (Without Special %):", ascending=False).reset_index(drop=True)
        
        col_order = [
            "Master Rank", "Ticker", "Current Price ($)", 
            "TTM Regular Dividends ($)", "Special Dividends ($)", 
            "Annual Yield (With Special %)", "Annual Yield (Without Special %):", 
            "Stability (Long-Term)", "Price Direction", "Combined Score"
        ]
        df_results = df_results[col_order]
        
        os.makedirs(os.path.dirname(output_xlsx), exist_ok=True)
        
        df_results.to_csv(output_csv, index=False)
        
        with pd.ExcelWriter(output_xlsx, engine='openpyxl') as writer:
            df_results.to_excel(writer, sheet_name='Dividend Analysis', index=False)
            workbook = writer.book
            worksheet = writer.sheets['Dividend Analysis']
            max_row = len(df_results) + 1
            max_col_letter = chr(64 + len(col_order))
            worksheet.auto_filter.ref = f"A1:{max_col_letter}{max_row}"
            
        print(f"\n   [Python] Success! Recalculated lookback window to prevent quarter-doubling.")
    else:
        print("\n   [Warning] No dividend paying stocks identified in target set.")

if __name__ == "__main__":
    main()
