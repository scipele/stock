#include "summary.hpp"

#include <fstream>
#include <iostream>
#include <algorithm>
#include <iomanip>


std::string csv_escape(const std::string& value)
{
    std::string result = value;

    if(result.find(',') != std::string::npos ||
       result.find('"') != std::string::npos)
    {
        std::string escaped;

        for(char c : result)
        {
            if(c == '"')
                escaped += "\"\"";
            else
                escaped += c;
        }

        result = "\"" + escaped + "\"";
    }

    return result;
}


void generate_summary(
    const std::vector<StockResult>& stocks,
    const std::string& filename)
{

    std::vector<StockResult> sorted = stocks;

    std::sort(
        sorted.begin(),
        sorted.end(),
        [](const StockResult& a,
           const StockResult& b)
        {
            return a.score.overall_score >
                   b.score.overall_score;
        }
    );

    std::ofstream out(filename);

    if(!out.is_open())
    {
        std::cerr
            << "Unable to create "
            << filename
            << "\n";

        return;
    }

    out << "Rank,"
        << "Owned,"
        << "Ticker,"
        << "Company,"
        << "Sector,"
        << "Overall_Score,"
        << "Price,"
        << "Previous_Low,"
        << "Swing_Low,"
        << "Dist_Previous_Low_pct,"
        << "Dist_Swing_Low_pct,"
        << "RSI,"
        << "Forward_PE,"
        << "Trailing_PE,"
        << "Momentum_3M,"
        << "Volatility,"
        << "Swing_Score,"
        << "Support_Score,"
        << "PE_Score,"
        << "RSI_Score,"
        << "Momentum_Score,"
        << "Volatility_Score\n";

    int rank = 1;

    out << std::fixed
        << std::setprecision(2);

    for(const auto& stock : sorted)
    {
        const auto& t = stock.data.technical;
        const auto& f = stock.data.fundamental;
        const auto& s = stock.score;

        out << rank++ << ","
            << (stock.owned ? "Y" : "") << ","
            << stock.ticker << ","
            << csv_escape(stock.company) << ","
            << csv_escape(std::to_string(stock.sector)) << ","
            << s.overall_score << ","
            << t.price << ","
            << t.previous_low << ","
            << t.swing_low << ","
            << t.distance_previous_low << ","
            << t.distance_swing_low << ","
            << t.rsi << ","
            << f.forward_pe << ","
            << f.trailing_pe << ","
            << t.momentum_3m << ","
            << t.volatility << ","
            << s.swing_score << ","
            << s.support_score << ","
            << s.pe_score << ","
            << s.rsi_score << ","
            << s.momentum_score << ","
            << s.volatility_score
            << "\n";
    }


    out.close();



    std::cout
        << "   Created "
        << filename
        << "\n";
}