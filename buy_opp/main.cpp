/*
Compile Linux with:
g++ main.cpp \
analysis.cpp \
scoring.cpp \
yahoo.cpp \
summary.cpp \
fundamentals.cpp \
-o stock_scanner \
-std=c++17 \
-O3 \
-lcurl \
-pthread
*/

#include <iostream>
#include <fstream>
#include <vector>
#include <string>
#include <thread>
#include <mutex>
#include <filesystem>
#include <set>
#include <curl/curl.h>

#include "fundamentals.h"
#include "yahoo.h"
#include "scoring.h"
#include "summary.h"


namespace fs = std::filesystem;



std::mutex results_mutex;

std::vector<StockResult> results;
FundamentalsDB fundamentals;


std::vector<std::string> load_tickers()
{
    std::set<std::string> unique;


    std::ifstream file(
        "input/tickers.csv"
    );


    if(!file.is_open())
    {
        std::cerr
            << "Unable to open input/tickers.csv\n";

        return {};
    }



    std::string line;


    // Skip header
    std::getline(file,line);



    while(std::getline(file,line))
    {
        if(line.empty())
            continue;


        // remove spaces/quotes
        line.erase(
            0,
            line.find_first_not_of(
                " \t\""
            )
        );


        line.erase(
            line.find_last_not_of(
                " \t\""
            ) + 1
        );



        if(!line.empty())
            unique.insert(line);
    }



    return
        std::vector<std::string>(
            unique.begin(),
            unique.end()
        );
}





void process_stock(
    const std::string& ticker)
{

    std::cout
        << "Processing "
        << ticker
        << "\n";



    YahooStockData data =
        fetch_stock_data(
            ticker
        );



    if(!data.valid)
    {
        std::cout
            << "FAILED "
            << ticker
            << "\n";

        return;
    }



    FundamentalData f =
        fundamentals.get(ticker);


    ScoreResult score =
        calculate_score(
            data.technical,
            f
        );


    data.fundamental = f;



    StockResult result;

    result.ticker =
        ticker;

    result.data =
        data;

    result.score =
        score;



    {

        std::lock_guard<std::mutex> lock(
            results_mutex
        );


        results.push_back(
            result
        );
    }



    std::cout
        << ticker
        << " Score: "
        << score.overall_score
        << "\n";
}






int main()
{

    curl_global_init(
        CURL_GLOBAL_DEFAULT
    );



    std::cout
        << "\nStock Buy Opportunity Scanner\n"
        << "============================\n\n";



    fs::create_directories(
        "output"
    );



    auto tickers =
        load_tickers();
   

    if(tickers.empty())
    {
        std::cout
            << "No tickers found\n";

        return 1;
    }

    fundamentals.load(
        "input/fundamentals.csv"
    );



    std::cout
        << "Loaded "
        << tickers.size()
        << " tickers\n\n";



    const int max_threads = 10;


    std::vector<std::thread> threads;



    for(const auto& ticker : tickers)
    {

        threads.emplace_back(
            process_stock,
            ticker
        );



        if(threads.size() >= max_threads)
        {

            for(auto& t : threads)
                t.join();


            threads.clear();
        }
    }



    for(auto& t : threads)
        t.join();





    std::cout
        << "\nProcessed "
        << results.size()
        << " stocks\n";



    generate_summary(
        results,
        "output/summary_all.csv"
    );



    curl_global_cleanup();



    std::cout
        << "\nFinished\n";


    return 0;
}