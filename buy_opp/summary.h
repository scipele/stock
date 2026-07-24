#pragma once

#include <vector>
#include "yahoo.h"
#include "scoring.h"


struct StockResult
{
    std::string ticker;

    YahooStockData data;

    ScoreResult score;
};



void generate_summary(
    const std::vector<StockResult>& stocks,
    const std::string& filename
);