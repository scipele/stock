#include "yahoo.hpp"
#include <curl/curl.h>
#include <nlohmann/json.hpp>

#include <iostream>
#include <sstream>
#include <vector>
#include <fstream>

using json = nlohmann::json;



size_t WriteCallback(
    void* contents,
    size_t size,
    size_t nmemb,
    void* userp)
{
    ((std::string*)userp)
        ->append(
            (char*)contents,
            size * nmemb
        );

    return size * nmemb;
}



std::string fetch_url(
    const std::string& url)
{
    CURL* curl = curl_easy_init();

    std::string response;


    if(curl)
    {

        curl_easy_setopt(
            curl,
            CURLOPT_URL,
            url.c_str()
        );


        curl_easy_setopt(
            curl,
            CURLOPT_WRITEFUNCTION,
            WriteCallback
        );


        curl_easy_setopt(
            curl,
            CURLOPT_WRITEDATA,
            &response
        );


        curl_easy_setopt(
            curl,
            CURLOPT_FOLLOWLOCATION,
            1L
        );


        curl_easy_setopt(
            curl,
            CURLOPT_COOKIEFILE,
            ""
        );


        curl_easy_setopt(
            curl,
            CURLOPT_USERAGENT,
            "Mozilla/5.0"
        );


        curl_easy_setopt(
            curl,
            CURLOPT_TIMEOUT,
            10L
        );


        curl_easy_perform(curl);

        curl_easy_cleanup(curl);
    }


    return response;
}




static bool parse_chart(
    const json& chart,
    std::vector<double>& closes,
    std::vector<double>& highs,
    std::vector<double>& lows)
{

    try
    {

        auto result =
            chart["chart"]["result"][0];


        auto quote =
            result["indicators"]["quote"][0];


        auto close =
            quote["close"];


        auto high =
            quote["high"];


        auto low =
            quote["low"];

        closes.reserve(close.size());
        highs.reserve(high.size());
        lows.reserve(low.size());

        for(size_t i=0;
            i<close.size();
            i++)
        {

            if(close[i].is_null() ||
               high[i].is_null() ||
               low[i].is_null())
                continue;


            closes.push_back(
                close[i].get<double>()
            );


            highs.push_back(
                high[i].get<double>()
            );


            lows.push_back(
                low[i].get<double>()
            );
        }


    }
    catch(...)
    {
        return false;
    }

    return closes.size() >= 30;
}


YahooStockData fetch_stock_data(const std::string& ticker) {

    YahooStockData result;
    result.ticker = ticker;

    std::string chart_url =
        "https://query1.finance.yahoo.com/v8/finance/chart/"
        + ticker +
        "?range=1y&interval=1d";

    std::string chart_raw = fetch_url(chart_url);

    if(chart_raw.size() < 1000)
    {
        return result;
    }

    try
    {
        json chart = json::parse(chart_raw);

        std::vector<double> closes;
        std::vector<double> highs;
        std::vector<double> lows;

        if(!parse_chart(chart,closes,highs,lows))
        {
            return result;
        }

        result.technical =
            analyze_prices(
                closes,
                highs,
                lows
            );

        result.valid=true;
    }
    catch(const std::exception& e)
    {
        std::cout
            << "\nFAIL "
            << ticker
            << ": "
            << e.what()
            << "\n";
    }

    return result;
}