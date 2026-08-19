#include "intrinsic.h"

#include <algorithm>
#include <cmath>
#include <fstream>
#include <iostream>
#include <sstream>
#include <iomanip>


// Text sector name → numeric code (must match Python SECTOR_MAP)
static int sectorNameToCode(const std::string& name) {
    if (name == "Basic Materials")        return 1;
    if (name == "Communication Services") return 2;
    if (name == "Consumer Cyclical")      return 3;
    if (name == "Consumer Defensive")     return 4;
    if (name == "Energy")                 return 5;
    if (name == "Financial Services")     return 6;
    if (name == "Healthcare")             return 7;
    if (name == "Industrials")            return 8;
    if (name == "Real Estate")            return 9;
    if (name == "Technology")             return 10;
    if (name == "Utilities")              return 11;
    return 0;   // unknown
}

// ------------------------------------------------------------------------
// Section parameters for growth, WACC, and terminal multiple respectively
// ------------------------------------------------------------------------
const SectorParams SECTOR_PARAMS[13] = {
    /* 0 */ {0.06, 0.085, 0.020, 15.0},   // default (safer)
    /* 1 */ {0.05, 0.090, 0.015, 12.0},   // Basic Materials
    /* 2 */ {0.08, 0.095, 0.020, 15.0},   // Communication Services
    /* 3 */ {0.06, 0.090, 0.020, 14.0},   // Consumer Cyclical
    /* 4 */ {0.04, 0.080, 0.020, 13.0},   // Consumer Defensive
    /* 5 */ {0.05, 0.095, 0.015, 12.0},   // Energy
    /* 6 */ {0.04, 0.090, 0.015, 11.0},   // Financial Services  ← tighter
    /* 7 */ {0.06, 0.085, 0.020, 14.0},   // Healthcare
    /* 8 */ {0.06, 0.085, 0.020, 14.0},   // Industrials
    /* 9 */ {0.04, 0.085, 0.015, 12.0},   // Real Estate
    /*10 */ {0.10, 0.095, 0.025, 16.0},   // Technology
    /*11 */ {0.03, 0.080, 0.015, 12.0}    // Utilities
};


const SectorParams& getSectorParams(int sectorCode) {
    if (sectorCode < 1 || sectorCode > 12)
        return SECTOR_PARAMS[0];
    return SECTOR_PARAMS[sectorCode];
}


// ------------------------------------------------------------------------
// Simple CSV helpers
// ------------------------------------------------------------------------
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

static int toInt(const std::string& s, int defaultValue = 0) {
    try {
        if (s.empty()) return defaultValue;
        return std::stoi(s);
    } catch (...) {
        return defaultValue;
    }
}


// ------------------------------------------------------------------------
// Load the Python-generated CSV
// ------------------------------------------------------------------------
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

        const bool hasExchIndex = cols.size() >= 26;
        const int offset = hasExchIndex ? 2 : 0;

        StockData s;
        s.ticker        = cols[0];
        s.company       = cols[1];
        s.sector        = sectorNameToCode(cols[2]);   // text → int
        if (hasExchIndex) {
            s.exch      = toInt(cols[3], 4);
            s.index     = toInt(cols[4], 0);
        }

        s.price         = toDouble(cols[3 + offset]);
        s.shares        = toDouble(cols[4 + offset]);
        s.marketCap     = toDouble(cols[5 + offset]);
        s.totalDebt     = toDouble(cols[6 + offset]);
        s.totalCash     = toDouble(cols[7 + offset]);
        s.beta          = toDouble(cols[8 + offset]);
        s.forwardPE     = toDouble(cols[9 + offset]);
        s.trailingPE    = toDouble(cols[10 + offset]);
        s.fcfTTM        = toDouble(cols[11 + offset]);

        for (int i = 0; i < 5; ++i) s.fcf[i] = toDouble(cols[12 + offset + i]);
        for (int i = 0; i < 5; ++i) s.rev[i] = toDouble(cols[17 + offset + i]);

        s.dataQuality   = cols[22 + offset];
        s.fetchedAt     = cols[23 + offset];

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
    constexpr double RISK_FREE          = 0.04;
    constexpr double EQUITY_RISK_PREMIUM = 0.05;
    constexpr double MIN_GROWTH         = -0.05;
    constexpr double MAX_WACC           = 0.15;
    constexpr int    HIGH_GROWTH_YEARS  = 5;

    for (auto& s : stocks) {
        // Basic validity
        if (s.price <= 0.0 || s.shares <= 0.0 ||
            s.dataQuality == "fetch_failed" ||
            s.dataQuality == "missing_price_or_shares") {
            s.valid = false;
            continue;
        }

        // -------------------------------------------------------
        // Data-quality filter (catches bad FCF numbers)
        // -------------------------------------------------------
        double fcf_for_check = s.fcfTTM;
        if (fcf_for_check <= 0.0) fcf_for_check = s.fcf[0];

        // Reject if FCF is absurdly high relative to market cap
        // (more than 40% of market cap is almost never sustainable)
        if (s.marketCap > 0.0 && fcf_for_check > 0.40 * s.marketCap) {
            s.valid = false;
            continue;
        }

        // Reject if FCF is many times larger than the largest
        // historical annual FCF (helps catch one-off garbage values)
        double max_hist_fcf = 0.0;
        for (int i = 0; i < 5; ++i) {
            if (s.fcf[i] > max_hist_fcf) max_hist_fcf = s.fcf[i];
        }
        if (max_hist_fcf > 0.0 && fcf_for_check > 4.0 * max_hist_fcf) {
            s.valid = false;
            continue;
        }

        // Optional extra safety: reject extremely negative FCF
        // that would make the whole DCF meaningless
        if (fcf_for_check < -0.5 * s.marketCap) {
            s.valid = false;
            continue;
        }
        // -------------------------------------------------------

        const SectorParams& p = getSectorParams(s.sector);

        s.netDebt = s.totalDebt - s.totalCash;

        // --- Growth rate ---
        double g = calculateCAGR(s.fcf, 5);
        if (std::abs(g) < 0.001 || !std::isfinite(g)) {
            g = calculateCAGR(s.rev, 5);
        }
        g = std::clamp(g, MIN_GROWTH, p.maxGrowth);
        s.growthRate = g;

        // --- WACC ---
        double beta = (s.beta <= 0.0) ? 1.0 : s.beta;
        beta = std::clamp(beta, 0.5, 2.0);

        double wacc = RISK_FREE + beta * EQUITY_RISK_PREMIUM;
        wacc = std::clamp(wacc, p.minWacc, MAX_WACC);
        s.wacc = wacc;

        // --- Starting FCF ---
        double fcf0 = s.fcfTTM;
        if (fcf0 <= 0.0) fcf0 = s.fcf[0];

        double avg_positive_fcf = 0.0;
        int cnt = 0;
        for (int i = 0; i < 5; ++i) {
            if (s.fcf[i] > 0.0) {
                avg_positive_fcf += s.fcf[i];
                ++cnt;
            }
        }
        if (cnt >= 3) {
            avg_positive_fcf /= cnt;
            // If TTM is less than 60% of the recent average, use the average
            if (fcf0 < 0.60 * avg_positive_fcf) {
                fcf0 = avg_positive_fcf;
            }
        }

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

        if (fcf0 <= 0.0) {
            s.valid = false;
            continue;
        }

        // --- Two-stage DCF with growth fade ---
        double pv  = 0.0;
        double fcf = fcf0;
        const double tg = p.terminalGrowth;

        for (int t = 1; t <= HIGH_GROWTH_YEARS; ++t) {
            double growth_t;
            if (t <= 3) {
                growth_t = g;
            } else if (t == 4) {
                growth_t = (2.0/3.0)*g + (1.0/3.0)*tg;
            } else { // t == 5
                growth_t = (1.0/3.0)*g + (2.0/3.0)*tg;
            }

            fcf *= (1.0 + growth_t);
            pv  += fcf / std::pow(1.0 + wacc, t);
        }

        // Terminal value with safety cap
        double terminalFCF   = fcf * (1.0 + tg);
        double terminalValue = terminalFCF / (wacc - tg);
        terminalValue = std::min(terminalValue, terminalFCF * p.maxTerminalMultiple);

        pv += terminalValue / std::pow(1.0 + wacc, HIGH_GROWTH_YEARS);

        // Equity value
        double equityValue = pv - s.netDebt;

        // Special net-debt treatment by sector
        if (s.sector == 6) {               // Financial Services
            equityValue = pv;              // ignore net debt
        }
        else if (s.sector == 4) {          // Consumer Defensive
            equityValue = pv - 0.5 * s.netDebt;   // only subtract half
        }

        if (equityValue <= 0.0) {
            s.valid = false;
            continue;
        }

        s.intrinsicValue  = equityValue / s.shares;
        s.marginOfSafety  = (s.intrinsicValue - s.price) / s.intrinsicValue * 100.0;
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

    out << "Rank,Ticker,Company,Sector,Exch,Index,Price,IntrinsicValue,MarginOfSafety_pct,Upside_pct,"
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
            << s.exch << ","
            << s.index << ","
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

    std::cout << "       Wrote " << rank << " valid stocks → " << path << "\n";
}