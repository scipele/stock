/*============================================================
fetch_intraday.cpp
Downloads a tight current-session-only intraday dataset from
Yahoo Finance for a live dashboard view.

Build:
g++ fetch_intraday_live.cpp -o ../bin/fetch_intraday_live -lcurl -pthread -std=c++17 -O2
============================================================*/

#include <iostream>
#include <fstream>
#include <sstream>
#include <vector>
#include <string>
#include <filesystem>
#include <algorithm>
#include <mutex>
#include <thread>
#include <chrono>
#include <curl/curl.h>
#include <nlohmann/json.hpp>
#include <iomanip>
#include <ctime>

namespace fs = std::filesystem;
using json = nlohmann::json;

// This is deliberately reduced to the current session only to avoid
// rate limiting and to keep the live chart fast and lightweight.
constexpr char RANGE[]    = "1d";
constexpr char INTERVAL[] = "5m";

std::mutex cout_mutex;

fs::path resolve_project_root(const char* argv0)
{
    fs::path exec_path = fs::path(argv0);
    if (!exec_path.is_absolute())
        exec_path = fs::absolute(exec_path);

    fs::path p = exec_path.parent_path();
    if (!p.empty())
        p = p.parent_path();
    if (!p.empty())
        p = p.parent_path();

    if (!p.empty())
        return p;

    return fs::current_path();
}

size_t WriteCallback(void* contents,
                     size_t size,
                     size_t nmemb,
                     void* userp)
{
    auto* response = static_cast<std::string*>(userp);
    response->append(static_cast<char*>(contents), size * nmemb);
    return size * nmemb;
}

std::string trim(std::string s)
{
    const std::string ws = " \t\r\n\"";
    const auto first = s.find_first_not_of(ws);
    if (first == std::string::npos)
        return "";
    const auto last = s.find_last_not_of(ws);
    return s.substr(first, last - first + 1);
}

std::vector<std::string> load_tickers(const fs::path& input_file)
{
    std::vector<std::string> tickers;
    std::ifstream file(input_file);
    if (!file)
    {
        std::cerr << "Cannot open " << input_file << std::endl;
        return tickers;
    }

    std::string line;
    std::getline(file, line);

    while (std::getline(file, line))
    {
        line = trim(line);
        if (!line.empty())
            tickers.push_back(line);
    }

    return tickers;
}

std::string fetch_url(const std::string& url, int retries = 2)
{
    while (retries-- > 0)
    {
        CURL* curl = curl_easy_init();
        if (!curl)
            continue;

        std::string response;
        curl_easy_setopt(curl, CURLOPT_URL, url.c_str());
        curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, WriteCallback);
        curl_easy_setopt(curl, CURLOPT_WRITEDATA, &response);
        curl_easy_setopt(curl, CURLOPT_USERAGENT, "Mozilla/5.0");
        curl_easy_setopt(curl, CURLOPT_TIMEOUT, 12L);
        curl_easy_setopt(curl, CURLOPT_CONNECTTIMEOUT, 6L);
        curl_easy_setopt(curl, CURLOPT_FOLLOWLOCATION, 1L);

        CURLcode result = curl_easy_perform(curl);
        curl_easy_cleanup(curl);

        if (result == CURLE_OK && response.size() > 100)
            return response;

        std::this_thread::sleep_for(std::chrono::milliseconds(500));
    }

    return "";
}

std::string make_url(const std::string& ticker)
{
    return "https://query1.finance.yahoo.com/v8/finance/chart/" + ticker +
           "?range=" + RANGE +
           "&interval=" + INTERVAL +
           "&includeAdjustedClose=true" +
           "&includeAdjustedClose=true";
}

std::string format_timestamp(long timestamp)
{
    std::time_t t = timestamp;
    std::tm tm{};
    localtime_r(&t, &tm);

    char buffer[32];
    std::strftime(buffer, sizeof(buffer), "%Y-%m-%d %H:%M", &tm);
    return buffer;
}

bool save_csv(const std::string& ticker,
              const std::string& raw_json,
              const fs::path& output_folder)
{
    try
    {
        json j = json::parse(raw_json);
        const auto result = j["chart"]["result"][0];
        const auto timestamps = result["timestamp"];
        const auto quote = result["indicators"]["quote"][0];

        const auto opens = quote["open"];
        const auto highs = quote["high"];
        const auto lows = quote["low"];
        const auto closes = quote["close"];
        const auto volumes = quote["volume"];

        fs::path filename = output_folder / (ticker + ".csv");

        std::ofstream out(filename);
        if (!out)
        {
            std::cerr << "Cannot create " << filename << "\n";
            return false;
        }

        out << "Ticker,Timestamp,Datetime,Open,High,Low,Close,Volume\n";

        for (size_t i = 0; i < timestamps.size(); ++i)
        {
            if (opens[i].is_null() || closes[i].is_null())
                continue;

            const long ts = timestamps[i];
            out << ticker << "," << ts << "," << format_timestamp(ts)
                << "," << opens[i] << "," << highs[i] << "," << lows[i]
                << "," << closes[i] << "," << volumes[i] << "\n";
        }

        return true;
    }
    catch (const std::exception& e)
    {
        std::cerr << "JSON error for " << ticker << ": " << e.what() << "\n";
        return false;
    }
}

int progress_bar(int current, int total, int bar_width = 50)
{
    float progress = static_cast<float>(current) / total;
    int pos = static_cast<int>(bar_width * progress);

    std::cout << "   [";
    for (int i = 0; i < bar_width; ++i)
    {
        if (i < pos) std::cout << "=";
        else if (i == pos) std::cout << ">";
        else std::cout << " ";
    }
    std::cout << "] " << int(progress * 100.0) << " %\r";
    std::cout.flush();
    return 0;
}

int main(int argc, char* argv[])
{
    const fs::path PROJECT_ROOT = resolve_project_root(argc > 0 ? argv[0] : "");
    const fs::path OUTPUT_FOLDER = PROJECT_ROOT / "output";
    const fs::path INPUT_FILE = PROJECT_ROOT / "input" / "tickers.csv";

    std::filesystem::create_directories(OUTPUT_FOLDER);

    curl_global_init(CURL_GLOBAL_DEFAULT);

    const auto tickers = load_tickers(INPUT_FILE);

    std::cout << "   Loaded " << tickers.size() << " tickers\n";

    int index = 0;
    for (const auto& ticker : tickers)
    {
        std::string url = make_url(ticker);
        std::string raw = fetch_url(url);

        if (raw.empty())
        {
            std::cout << "FAILED " << ticker << "\n";
            if (index + 1 < static_cast<int>(tickers.size()))
                std::this_thread::sleep_for(std::chrono::milliseconds(2000));
            continue;
        }

        save_csv(ticker, raw, OUTPUT_FOLDER);
        ++index;
        progress_bar(index, static_cast<int>(tickers.size()));

        if (index < static_cast<int>(tickers.size()))
            std::this_thread::sleep_for(std::chrono::milliseconds(1500));
    }

    std::cout << std::endl;
    curl_global_cleanup();
    return 0;
}