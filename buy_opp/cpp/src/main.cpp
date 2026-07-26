/*
Compile Linux with the following from the cpp/src directory:
g++ main.cpp analysis.cpp fundamentals.cpp metadata.cpp scoring.cpp summary.cpp yahoo.cpp -o ../bin/buy_opp -I../include -std=c++17 -O3 -lcurl -pthread
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
#include <sstream>
#include <unordered_map>

#include "../include/fundamentals.hpp"
#include "../include/yahoo.hpp"
#include "../include/scoring.hpp"
#include "../include/summary.hpp"
#include "../include/metadata.hpp"

struct FailedTicker
{
  std::string ticker;
  std::string reason;
};

std::mutex failed_mutex;
std::vector<FailedTicker> failed_tickers;


namespace fs = std::filesystem;

std::mutex progress_mutex;
std::atomic<int> completed_count{0};
std::mutex results_mutex;

std::vector<StockResult> results;
FundamentalsDB fundamentals;
std::unordered_map<std::string,Metadata> metadata;
int total_tickers = 0;
std::chrono::steady_clock::time_point start_time;
std::unordered_map<std::string,bool> owned_map;

std::vector<std::string> load_tickers() {
    std::set<std::string> unique;
    std::ifstream file(
        "../../data/tickers_combined.csv"
    );

    if(!file.is_open())
    {
        std::cerr
            << "Unable to open ../../data/tickers_combined.csv\n";
        return {};
    }

    std::string line;
    // Skip header
    std::getline(file,line);

    while(std::getline(file,line))
    {
        if(line.empty())
            continue;

        std::stringstream ss(line);
        std::string ticker;
        std::string owned;

        std::getline(ss,ticker,',');
        std::getline(ss,owned,',');

        ticker.erase(
            0,
            ticker.find_first_not_of(" \t\"")
        );

        ticker.erase(
            ticker.find_last_not_of(" \t\"") + 1
        );

        if(!ticker.empty()) {
            unique.insert(ticker);
            if(owned=="Y") owned_map[ticker]=true;
        }
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

    std::cout << "   \r[";

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

    YahooStockData data = fetch_stock_data(ticker);

    if(!data.valid)
    {
        {
            std::lock_guard<std::mutex> lock(failed_mutex);

            failed_tickers.push_back(
                {
                    ticker,
                    "Insufficient history or invalid chart data"
                }
            );
        }

        return;
    }

    FundamentalData f = fundamentals.get(ticker);
    ScoreResult score =calculate_score(data.technical,f);
    data.fundamental = f;

    StockResult result;
    result.ticker = ticker;
    result.owned = owned_map[ticker];
    result.data = data;
    auto it=metadata.find(ticker);

    if(it!=metadata.end()){
        result.company=it->second.company;
        result.sector=it->second.sector;
    }

    result.score = score;

    {
        std::lock_guard<std::mutex> lock(results_mutex);
        results.emplace_back(std::move(result));
    }
    int done = ++completed_count;

    update_progress(
        done,
        total_tickers,
        start_time);
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
    
    // Use reserve to avoid multiple reallocations
    results.reserve(total_tickers);
   
    if(tickers.empty()) { std::cout << "   No tickers found\n";
        return 1;
    }

    fundamentals.load("../../data/fundamentals.csv");

    std::cout << "   Loaded "
              << tickers.size()
              << " tickers\n\n";

    metadata=load_metadata("../../data/stock_metadata.csv");

    std::cout << "   Loaded metadata "
              << metadata.size()
              << " entries\n";

    const int max_threads = 10;
    std::vector<std::thread> threads;
    threads.reserve(max_threads);

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
    if(!failed_tickers.empty())
    {
        std::cout
            << "\nSkipped "
            << failed_tickers.size()
            << " tickers:\n";

        for(const auto& failed : failed_tickers)
        {
            std::cout
                << "  "
                << failed.ticker
                << " - "
                << failed.reason
                << "\n";
        }
    }

    generate_summary(
        results,
        "../../output/summary_all.csv"
    );

    curl_global_cleanup();
 
    auto end_time = std::chrono::steady_clock::now();

    auto elapsed =
        std::chrono::duration<double>(end_time - start_time).count();

    std::cout << "\n   Completed in "
            << std::fixed
            << std::setprecision(2)
            << elapsed
            << " seconds\n";

    return 0;
}