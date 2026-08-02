#pragma once

#include <string>
#include <vector>

struct SectorParams {
    double maxGrowth;
    double minWacc;
    double terminalGrowth;
    double maxTerminalMultiple;
};

// Indexed by sector code 1..12 (index 0 = default)
extern const SectorParams SECTOR_PARAMS[13];

const SectorParams& getSectorParams(int sectorCode);


struct StockData {
    std::string ticker;
    std::string company;
    int sector = 0;
    double price = 0.0;
    double shares = 0.0;
    double marketCap = 0.0;
    double totalDebt = 0.0;
    double totalCash = 0.0;
    double beta = 0.0;
    double forwardPE = 0.0;         // forward Price/Earnings ratio (next 12 months).  how is that estimated?  
    double trailingPE = 0.0;        // trailing Price/Earnings ratio (last 12 months)
    double fcfTTM = 0.0;            // Free Cash Flow Trailing Twelve Months
    double fcf[5] = {0};            // Free Cash Flow (fcf) Year1 (newest) → Year5 (oldest)
    double rev[5] = {0};            // Revenue Year1 (newest) → Year5 (oldest)

    std::string dataQuality;
    std::string fetchedAt;

    // Calculated fields
    double netDebt = 0.0;
    double growthRate = 0.0;        // Compound Annual Growth Rate (CAGR) (end value / start value)^(1/years) - 1
    double wacc = 0.0;              // Weighted Average Cost of Capital
    double intrinsicValue = 0.0;    // Calculated intrinsic value
    double marginOfSafety = 0.0;
    bool   valid = false;
};

std::vector<StockData> loadFundamentals(const std::string& path);
void calculateIntrinsicValues(std::vector<StockData>& stocks);
void writeSummary(const std::vector<StockData>& stocks, const std::string& path);