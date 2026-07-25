/*
Tree Structure, in order of workflow:

                                            Step 1: Download your current positions from Schwab

buy_opp
    /script
        buy_opp.sh                          Step 2: Main Script runs all other scripts and programs
        get_cur_pos_tickers.sh              Step 3: Bash Script to get current positions from Downloads Folder and saves to input/current_positions.csv
        combine_sort_tickers.sh             Step 6: Bash Script to combine current positions, S&P 500 tickers, and other tickers, sort and remove duplicates, saves to tickers_combined.csv

    /data
        tickers_current_positions.csv       Step 4: Current positions list is saved from step 3
        tickers_s_p_500.csv                 Step 5: S&P 500 Tickers list stays in data folder, used to combine with current positions
        tickers_other.csv                   Step 6: Other Tickers list stays in data folder, used to combine with current positions
        tickers_combined.csv                Step 7: Combined and sorted tickers list is saved from step 6
        fundamentals.csv                    Step 9: Fundamental data stored in CSV format

    /py
        get_financials.py                   Step 8: Optional (y/n) - Python Script to get fundamental data daily (uses yfinance library)

    /cpp
        /bin
            buy_opp                         Step 10: Compiled C++ program to process tickers, utilize fundamentals, get yahoo data, compute scores, and generate summary
        /include
            analysis.h
            fundamentals.h
            scoring.h
            yahoo.h
            summary.h
        /src
            analysis.cpp
            fundamentals.cpp
            scoring.cpp
            yahoo.cpp
            summary.cpp
            main.cpp
    /output                                 
        summary_all.csv                     Step 11: Output CSV files saved here


Compile Linux with the following from the cpp/src directory:
g++ main.cpp analysis.cpp fundamentals.cpp scoring.cpp summary.cpp yahoo.cpp -o ../bin/buy_opp -I../include -std=c++17 -O3 -lcurl -pthread
*/

#include <iostream>
#include <fstream>
#include <vector>
#include <string>
#include <thread>
#include <mutex>
#include <filesystem>
#include <chrono>
#include <atomic>
#include <iomanip>
#include <set>
#include <curl/curl.h>

#include "../include/fundamentals.hpp"
#include "../include/yahoo.hpp"
#include "../include/scoring.hpp"
#include "../include/summary.hpp"


namespace fs = std::filesystem;

std::mutex progress_mutex;
std::atomic<int> completed_count{0};
std::mutex results_mutex;
std::mutex failed_mutex;
std::vector<std::string> failed_tickers;

std::vector<StockResult> results;
FundamentalsDB fundamentals;
int total_tickers = 0;
std::chrono::steady_clock::time_point start_time;


std::vector<std::string> load_tickers() {
    std::set<std::string> unique;
    std::ifstream file(
        "../../data/tickers_combined.csv"
    );

    if(!file.is_open())
    {
        std::cerr
            << "Unable to open ../data/tickers_combined.csv\n";
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
    return std::vector<std::string>( 
            unique.begin(),
            unique.end()
        );
}


void update_progress(
    int completed,
    int total,
    const std::chrono::steady_clock::time_point& start_time)
{
    const int width = 30;
    double pct = static_cast<double>(completed) / total;
    int filled = static_cast<int>(pct * width);
    auto elapsed = std::chrono::duration<double> (
            std::chrono::steady_clock::now() - start_time
        ).count();

    double eta_seconds = 0.0;

    if (completed > 0)
    {
        eta_seconds = (elapsed / completed) * (total - completed);
    }

    int eta_min = static_cast<int>(eta_seconds) / 60;
    int eta_sec = static_cast<int>(eta_seconds) % 60;
    std::lock_guard<std::mutex> lock(progress_mutex);

    std::cout << "\r[";

    for (int i = 0; i < width; i++) {
        std::cout << (i < filled ? '#' : '-');
    }

    std::cout << "] "
              << std::setw(3)
              << static_cast<int>(pct * 100)
              << "%  "
              << completed
              << "/"
              << total
              << "  ETA "
              << eta_min
              << ":"
              << std::setfill('0')
              << std::setw(2)
              << eta_sec
              << std::setfill(' ')
              << std::flush;
}


void process_stock(const std::string& ticker) {
    // std::cout << "Processing " << ticker<< "\n";
    YahooStockData data = fetch_stock_data(ticker);

    if(!data.valid) {
        {
            std::lock_guard<std::mutex> lock(failed_mutex);
            failed_tickers.push_back(ticker);
        }
        return;
    }

    FundamentalData f = fundamentals.get(ticker);
    ScoreResult score =calculate_score(data.technical,f);
    data.fundamental = f;
    StockResult result;
    result.ticker = ticker;
    result.data = data;
    result.score = score;

    {
        std::lock_guard<std::mutex> lock(results_mutex);
        results.push_back(result);
    }
    int done = ++completed_count;

    update_progress(
        done,
        total_tickers,
        start_time);

    // std::cout << ticker
    //           << " Score: "
    //           << score.overall_score
    //           << "\n";
}


int main()
{
    start_time = std::chrono::steady_clock::now();

    curl_global_init(CURL_GLOBAL_DEFAULT);

    std::cout 
        << "\nStock Buy Opportunity Scanner\n"
        << "============================\n\n";

    fs::create_directories("output");

    auto tickers = load_tickers();
    total_tickers = tickers.size();

   
    if(tickers.empty()) { std::cout << "No tickers found\n";
        return 1;
    }

    fundamentals.load("../data/fundamentals.csv");

    std::cout << "Loaded "
              << tickers.size()
              << " tickers\n\n";

    const int max_threads = 10;
    std::vector<std::thread> threads;

    for(const auto& ticker : tickers) {
        threads.emplace_back(
            process_stock,
            ticker
        );

        if(threads.size() >= max_threads) {
            for(auto& t : threads) {
                t.join();
            }
            threads.clear();
        }
    }

    for(auto& t : threads)
        t.join();

    // Final flush of progress bar
    std::cout << std::endl;

    // Print failed tickers
    if (!failed_tickers.empty())
    {
        std::cout << "\nFailed to get data for the following (" << failed_tickers.size() << " ea) tickers: ";
        for (size_t i = 0; i < failed_tickers.size(); ++i)
        {
            if (i) std::cout << ", ";
            std::cout << failed_tickers[i];
        }
        std::cout << "\n";
    }

    generate_summary(
        results,
        "output/summary_all.csv"
    );

    curl_global_cleanup();
 
    auto end_time = std::chrono::steady_clock::now();

    auto elapsed =
        std::chrono::duration<double>(end_time - start_time).count();

    std::cout << "\nCompleted in "
            << std::fixed
            << std::setprecision(2)
            << elapsed
            << " seconds\n";

    return 0;
}