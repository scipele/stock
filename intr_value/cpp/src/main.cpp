/* Compile with Linux
g++ -std=c++17 -O2 -Wall -I../include main.cpp intrinsic.cpp -o ../bin/intr_value
*/

#include "../include/intrinsic.h"
#include <iostream>
#include <chrono>

int main() {
    const std::string inputPath  = "../../data/fundamentals_intrinsic.csv";
    const std::string outputPath = "../../output/summary_intrinsic.csv";

    std::cout << "=== Intrinsic Value – C++ Engine ===\n";

    auto t0 = std::chrono::steady_clock::now();

    auto stocks = loadFundamentals(inputPath);
    std::cout << "Loaded " << stocks.size() << " tickers\n";

    calculateIntrinsicValues(stocks);

    writeSummary(stocks, outputPath);

    auto t1 = std::chrono::steady_clock::now();
    double elapsed = std::chrono::duration<double>(t1 - t0).count();
    std::cout << "Finished in " << elapsed << " seconds\n";

    return 0;
}