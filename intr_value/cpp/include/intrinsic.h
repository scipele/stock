#pragma once

#include <string>
#include <vector>

struct StockData {
    std::string ticker;
    std::string company;
    std::string sector;

    double price = 0.0;
    double shares = 0.0;
    double marketCap = 0.0;
    double totalDebt = 0.0;
    double totalCash = 0.0;
    double beta = 0.0;
    double forwardPE = 0.0;
    double trailingPE = 0.0;

    double fcfTTM = 0.0;
    double fcf[5] = {0};      // Y1 (newest) → Y5 (oldest)
    double rev[5] = {0};

    std::string dataQuality;
    std::string fetchedAt;

    // Calculated fields
    double netDebt = 0.0;
    double growthRate = 0.0;      // capped CAGR used
    double wacc = 0.0;
    double intrinsicValue = 0.0;
    double marginOfSafety = 0.0;  // %
    bool   valid = false;
};

std::vector<StockData> loadFundamentals(const std::string& path);
void calculateIntrinsicValues(std::vector<StockData>& stocks);
void writeSummary(const std::vector<StockData>& stocks, const std::string& path);