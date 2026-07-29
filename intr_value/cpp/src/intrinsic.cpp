#include "intrinsic.h"

#include <algorithm>
#include <cmath>
#include <fstream>
#include <iostream>
#include <sstream>
#include <iomanip>

// ------------------------------------------------------------------
// Simple CSV helpers
// ------------------------------------------------------------------
static std::vector<std::string> splitCSV(const std::string& line) {
    std::vector<std::string> result;
    std::string field;
    bool inQuotes = false;

    for (char c : line) {
        if (c == '"') {
            inQuotes = !inQuotes;
        } else if (c == ',' && !inQuotes) {
            result.push_back(field);
            field.clear();
        } else {
            field += c;
        }
    }
    result.push_back(field);
    return result;
}

static double toDouble(const std::string& s) {
    try {
        if (s.empty()) return 0.0;
        return std::stod(s);
    } catch (...) {
        return 0.0;
    }
}

// ------------------------------------------------------------------
// Load the Python-generated CSV
// ------------------------------------------------------------------
std::vector<StockData> loadFundamentals(const std::string& path) {
    std::vector<StockData> stocks;
    std::ifstream file(path);
    if (!file.is_open()) {
        std::cerr << "ERROR: Cannot open " << path << "\n";
        return stocks;
    }

    std::string line;
    std::getline(file, line);          // skip header

    while (std::getline(file, line)) {
        if (line.empty()) continue;
        auto cols = splitCSV(line);
        if (cols.size() < 24) continue;

        StockData s;
        s.ticker        = cols[0];
        s.company       = cols[1];
        s.sector        = cols[2];
        s.price         = toDouble(cols[3]);
        s.shares        = toDouble(cols[4]);
        s.marketCap     = toDouble(cols[5]);
        s.totalDebt     = toDouble(cols[6]);
        s.totalCash     = toDouble(cols[7]);
        s.beta          = toDouble(cols[8]);
        s.forwardPE     = toDouble(cols[9]);
        s.trailingPE    = toDouble(cols[10]);
        s.fcfTTM        = toDouble(cols[11]);

        for (int i = 0; i < 5; ++i) s.fcf[i] = toDouble(cols[12 + i]);
        for (int i = 0; i < 5; ++i) s.rev[i] = toDouble(cols[17 + i]);

        s.dataQuality   = cols[22];
        s.fetchedAt     = cols[23];

        stocks.push_back(s);
    }
    return stocks;
}

// ------------------------------------------------------------------
// CAGR with safety
// ------------------------------------------------------------------
static double calculateCAGR(const double* series, int n) {
    // series[0] = newest, series[n-1] = oldest
    int first = -1, last = -1;
    for (int i = 0; i < n; ++i) {
        if (series[i] > 1.0) {          // ignore tiny/negative
            if (first == -1) first = i;
            last = i;
        }
    }
    if (first == -1 || last == -1 || first == last) return 0.0;

    double newest = series[first];
    double oldest = series[last];
    int years = last - first;
    if (years <= 0 || oldest <= 0.0) return 0.0;

    double cagr = std::pow(newest / oldest, 1.0 / years) - 1.0;
    return cagr;
}

// ------------------------------------------------------------------
// Core valuation
// ------------------------------------------------------------------
void calculateIntrinsicValues(std::vector<StockData>& stocks) {
    const double TERMINAL_GROWTH = 0.025;
    const double RISK_FREE = 0.04;
    const double EQUITY_RISK_PREMIUM = 0.05;
    const double MAX_GROWTH = 0.10;          // tightened from 0.18
    const double MIN_GROWTH = -0.05;
    const double MIN_WACC = 0.06;
    const double MAX_WACC = 0.15;
    const int HIGH_GROWTH_YEARS = 5;

    for (auto& s : stocks) {
        // Basic validity
        if (s.price <= 0.0 || s.shares <= 0.0 ||
            s.dataQuality == "fetch_failed" ||
            s.dataQuality == "missing_price_or_shares") {
            s.valid = false;
            continue;
        }

        s.netDebt = s.totalDebt - s.totalCash;

        // --- Growth rate ---
        double g = calculateCAGR(s.fcf, 5);

        // Fallback to revenue CAGR if FCF is unusable
        if (std::abs(g) < 0.001 || !std::isfinite(g)) {
            g = calculateCAGR(s.rev, 5);
        }

        // Cap growth
        g = std::clamp(g, MIN_GROWTH, MAX_GROWTH);
        s.growthRate = g;

        // --- WACC ---
        double beta = s.beta;
        if (beta <= 0.0) beta = 1.0;
        beta = std::clamp(beta, 0.5, 2.0);

        double wacc = RISK_FREE + beta * EQUITY_RISK_PREMIUM;
        wacc = std::clamp(wacc, MIN_WACC, MAX_WACC);
        s.wacc = wacc;

        // --- Starting FCF (stricter filter) ---
        double fcf0 = s.fcfTTM;
        if (fcf0 <= 0.0) fcf0 = s.fcf[0];          // most recent annual

        // If still not positive, try average of positive historical FCFs
        if (fcf0 <= 0.0) {
            double sum = 0.0;
            int cnt = 0;
            for (int i = 0; i < 5; ++i) {
                if (s.fcf[i] > 0.0) {
                    sum += s.fcf[i];
                    ++cnt;
                }
            }
            if (cnt > 0) fcf0 = sum / cnt;
        }

        // Final gate: require meaningful positive FCF
        if (fcf0 <= 0.0) {
            s.valid = false;
            continue;
        }

        // --- Two-stage DCF with growth fade ---
        double pv = 0.0;
        double fcf = fcf0;

        for (int t = 1; t <= HIGH_GROWTH_YEARS; ++t) {
            double growth_t;

            if (t <= 3) {
                // Years 1-3: full (capped) historical growth
                growth_t = g;
            } else if (t == 4) {
                // Year 4: 2/3 historical + 1/3 terminal
                growth_t = (2.0/3.0) * g + (1.0/3.0) * TERMINAL_GROWTH;
            } else { // t == 5
                // Year 5: 1/3 historical + 2/3 terminal
                growth_t = (1.0/3.0) * g + (2.0/3.0) * TERMINAL_GROWTH;
            }

            fcf *= (1.0 + growth_t);
            pv += fcf / std::pow(1.0 + wacc, t);
        }

        // Terminal value
        double terminalFCF = fcf * (1.0 + TERMINAL_GROWTH);
        double terminalValue = terminalFCF / (wacc - TERMINAL_GROWTH);
        pv += terminalValue / std::pow(1.0 + wacc, HIGH_GROWTH_YEARS);

        // Equity value
        double equityValue = pv - s.netDebt;
        if (equityValue <= 0.0) {
            s.valid = false;
            continue;
        }

        s.intrinsicValue = equityValue / s.shares;
        s.marginOfSafety = (s.intrinsicValue - s.price) / s.intrinsicValue * 100.0;
        s.valid = true;
    }
}
// ------------------------------------------------------------------
// Write ranked summary
// ------------------------------------------------------------------
void writeSummary(const std::vector<StockData>& stocks, const std::string& path) {
    // Sort by margin of safety (descending) – only valid ones first
    std::vector<StockData> sorted = stocks;
    std::sort(sorted.begin(), sorted.end(), [](const StockData& a, const StockData& b) {
        if (a.valid != b.valid) return a.valid > b.valid;
        return a.marginOfSafety > b.marginOfSafety;
    });

    std::ofstream out(path);
    if (!out.is_open()) {
        std::cerr << "ERROR: Cannot write " << path << "\n";
        return;
    }

    out << "Rank,Ticker,Company,Sector,Price,IntrinsicValue,MarginOfSafety_pct,Upside_pct,"
        << "GrowthRate,WACC,FCF_TTM,NetDebt,Shares,MarketCap,"
        << "ForwardPE,TrailingPE,DataQuality\n";

    int rank = 0;
    for (const auto& s : sorted) {
        if (!s.valid) continue;
        ++rank;

        double upside = 0.0;
        if (s.price > 0.0) {
            upside = (s.intrinsicValue - s.price) / s.price * 100.0;
        }

        out << rank << ","
            << s.ticker << ","
            << "\"" << s.company << "\","
            << s.sector << ","
            << std::fixed << std::setprecision(2) << s.price << ","
            << std::setprecision(2) << s.intrinsicValue << ","
            << std::setprecision(1) << s.marginOfSafety << ","
            << std::setprecision(1) << upside << ","
            << std::setprecision(4) << s.growthRate << ","
            << std::setprecision(4) << s.wacc << ","
            << std::setprecision(0) << s.fcfTTM << ","
            << std::setprecision(0) << s.netDebt << ","
            << std::setprecision(0) << s.shares << ","
            << std::setprecision(0) << s.marketCap << ","
            << std::setprecision(2) << s.forwardPE << ","
            << std::setprecision(2) << s.trailingPE << ","
            << s.dataQuality << "\n";
    }

    std::cout << "Wrote " << rank << " valid stocks → " << path << "\n";
}