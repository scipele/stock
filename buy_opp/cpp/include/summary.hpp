#pragma once

#include <vector>
#include "yahoo.hpp"
#include "scoring.hpp"
#include <string>

struct StockResult
{
    std::string ticker;
    std::string company;
    std::string sector;
    bool owned=false;
    YahooStockData data;
    ScoreResult score;
};


void generate_summary(
    const std::vector<StockResult>& stocks,
    const std::string& filename
);