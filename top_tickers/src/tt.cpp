/*
Compile with ubuntu with
g++ tt.cpp -o ../bin/tt
*/

#include <iostream>
#include <map>
#include <string>
#include <fstream>
#include <sstream>
#include <vector>

const std::string SP500_LIST_FILE_PTH     = "../../buy_opp/data/tickers_sp_500.csv";
const std::string RUSSEL_2K_LIST_FILE_PTH = "../../buy_opp/data/tickers_russel_2k.csv";
const std::string SCORE_FILE_PTH          = "../../buy_opp/output/summary_all.csv";
const std::string OUTPUT_FILE_PTH         = "../output/tickers_recent_top_scores.csv";

std::map<std::string, char> loadTickerMap(const std::string& path, char tag) {
    std::map<std::string, char> m;
    std::ifstream f(path);
    std::string line, tkr;
    std::getline(f, line);                       // skip header
    while (std::getline(f, line)) {
        std::stringstream ss(line);
        if (std::getline(ss, tkr, ',')) m[tkr] = tag;
    }
    return m;
}

std::vector<std::string> loadScoredTickers(const std::string& path) {
    std::vector<std::string> v;
    std::ifstream f(path);
    std::string line, tmp, tkr;
    while (std::getline(f, line)) {
        std::stringstream ss(line);
        std::getline(ss, tmp, ',');
        std::getline(ss, tmp, ',');
        if (std::getline(ss, tkr, ',')) v.push_back(tkr);
    }
    return v;
}

std::vector<std::string> selectTop(const std::vector<std::string>& scored,
                                   const std::map<std::string, char>& m,
                                   int n) {
    std::vector<std::string> out;
    for (const auto& t : scored) {
        if (m.count(t)) {
            // std::cout << label << t << '\n';
            out.push_back(t);
            if ((int)out.size() >= n) break;
        }
    }
    return out;
}

int main() {
    int top_s, top_r;
    std::cout << "Input the number of top scoring S&P Tickers to return? ";
    std::cin >> top_s;
    std::cout << "Input the number of top scoring RUSSEL 2K Tickers to return? ";
    std::cin >> top_r;

    auto sp   = loadTickerMap(SP500_LIST_FILE_PTH, 's');
    auto r2k  = loadTickerMap(RUSSEL_2K_LIST_FILE_PTH, 'r');
    auto ranked = loadScoredTickers(SCORE_FILE_PTH);

    std::vector<std::string>  top_sp  = selectTop(ranked, sp,  top_s);
    std::vector<std::string>  top_r2k = selectTop(ranked, r2k, top_r);

    std::map<std::string, char> combined;
    for (const auto& t : top_sp)  combined[t] = 's';
    for (const auto& t : top_r2k) combined[t] = 'r';

    std::ofstream out(OUTPUT_FILE_PTH);
    out << "ticker\n";
    int indx = 0;
    for (const auto& [t, _] : combined) {
        indx++;
        out << t << '\n';
    }
    std::cout << "\nWrote " << indx << " tickers to " << OUTPUT_FILE_PTH << '\n';

    std::cout << "\nPress any key to exit..." << '\n';
    std::cin.ignore();   // discards the leftover '\n'
    std::cin.get();
}