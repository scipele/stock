#pragma once

#include <string>
#include "analysis.hpp"
#include "fundamentals.hpp"


struct YahooStockData
{
    std::string ticker;
    TechnicalData technical;
    FundamentalData fundamental;
    bool valid = false;
};


std::string fetch_url(
    const std::string& url
);


YahooStockData fetch_stock_data(
    const std::string& ticker
);