#pragma once
#include <vector>
#include "yahoo.hpp"
#include "scoring.hpp"
#include <string>

struct StockResult {
    std::string ticker;
    std::string company;
    int sector = 0; // Changed to int to preserve processing speed and pipeline consistency
    int exch = 4;
    int index = 0;
    bool owned = false;
    YahooStockData data;
    ScoreResult score;
};

void generate_summary(
    const std::vector<StockResult>& stocks,
    const std::string& filename
);
