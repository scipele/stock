/*
Compile ubuntu
g++ -std=c++17 -O2 gain_loss.cpp -o ../bin/gain_loss
*/

#include <algorithm>
#include <cctype>
#include <chrono>
#include <cmath>
#include <ctime>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <map>
#include <set>
#include <sstream>
#include <string>
#include <vector>

namespace fs = std::filesystem;

const std::string DOWNLOAD_DIR = "/home/ts/Downloads";
const std::string OUTPUT_DIR = "/home/dev/stock/gain_loss/output";
const double EPSILON = 0.00001;

std::string trim(const std::string& s)
{
    size_t first = s.find_first_not_of(" \t\r\n");
    if (first == std::string::npos)
        return "";

    size_t last = s.find_last_not_of(" \t\r\n");
    return s.substr(first, last - first + 1);
}

std::string remove_quotes(const std::string& s)
{
    std::string result = trim(s);
    if (result.size() >= 2 && result.front() == '"' && result.back() == '"')
        result = result.substr(1, result.size() - 2);

    if (result.size() >= 3 &&
        static_cast<unsigned char>(result[0]) == 0xEF &&
        static_cast<unsigned char>(result[1]) == 0xBB &&
        static_cast<unsigned char>(result[2]) == 0xBF)
    {
        result.erase(0, 3);
    }

    return result;
}

std::string remove_commas(const std::string& s)
{
    std::string result;
    for (char c : s)
    {
        if (c != ',')
            result += c;
    }
    return result;
}

double to_double(const std::string& value)
{
    std::string s = remove_quotes(value);
    s = trim(s);
    s = remove_commas(s);

    if (s.empty())
        return 0.0;

    if (!s.empty() && s.front() == '$')
        s.erase(0, 1);

    if (!s.empty() && s.front() == '(' && !s.empty() && s.back() == ')')
    {
        s = "-" + s.substr(1, s.size() - 2);
    }

    try
    {
        return std::stod(s);
    }
    catch (...)
    {
        return 0.0;
    }
}

std::vector<std::string> parse_csv_line(const std::string& line)
{
    std::vector<std::string> fields;
    std::string field;
    bool in_quotes = false;

    for (size_t i = 0; i < line.size(); ++i)
    {
        char c = line[i];
        if (c == '"')
        {
            if (in_quotes && i + 1 < line.size() && line[i + 1] == '"')
            {
                field += '"';
                ++i;
            }
            else
            {
                in_quotes = !in_quotes;
            }
        }
        else if (c == ',' && !in_quotes)
        {
            fields.push_back(field);
            field.clear();
        }
        else
        {
            field += c;
        }
    }

    fields.push_back(field);
    return fields;
}

struct Date
{
    int year = 0;
    int month = 0;
    int day = 0;

    bool valid() const
    {
        return year > 0 && month > 0 && day > 0;
    }
};

Date parse_date(const std::string& value)
{
    Date d;
    std::string s = trim(remove_quotes(value));
    if (s.empty())
        return d;

    try
    {
        if (s.find('/') != std::string::npos)
        {
            d.month = std::stoi(s.substr(0, 2));
            d.day = std::stoi(s.substr(3, 2));
            d.year = std::stoi(s.substr(6, 4));
        }
        else if (s.find('-') != std::string::npos)
        {
            d.year = std::stoi(s.substr(0, 4));
            d.month = std::stoi(s.substr(5, 2));
            d.day = std::stoi(s.substr(8, 2));
        }
    }
    catch (...)
    {
        d = {};
    }

    return d;
}

std::string date_to_string(const Date& d)
{
    if (!d.valid())
        return "";

    std::ostringstream out;
    out << std::setfill('0')
        << std::setw(4) << d.year << "-"
        << std::setw(2) << d.month << "-"
        << std::setw(2) << d.day;
    return out.str();
}

std::time_t date_to_time(const Date& d)
{
    std::tm tm{};
    tm.tm_year = d.year - 1900;
    tm.tm_mon = d.month - 1;
    tm.tm_mday = d.day;
    tm.tm_hour = 12;
    return std::mktime(&tm);
}

bool date_less_than(const Date& a, const Date& b)
{
    return date_to_time(a) < date_to_time(b);
}

bool date_less_than_or_equal(const Date& a, const Date& b)
{
    return date_to_time(a) <= date_to_time(b);
}

bool date_greater_than_or_equal(const Date& a, const Date& b)
{
    return date_to_time(a) >= date_to_time(b);
}

int days_between(const Date& older, const Date& newer)
{
    if (!older.valid() || !newer.valid())
        return 0;

    std::time_t t1 = date_to_time(older);
    std::time_t t2 = date_to_time(newer);
    return static_cast<int>(std::round(std::difftime(t2, t1) / (60.0 * 60.0 * 24.0)));
}

bool contains(const std::string& value, const std::string& search)
{
    return value.find(search) != std::string::npos;
}

fs::path find_newest_positions_file()
{
    fs::path newest;
    fs::file_time_type newest_time{};

    for (const auto& entry : fs::directory_iterator(DOWNLOAD_DIR))
    {
        if (!entry.is_regular_file())
            continue;

        std::string name = entry.path().filename().string();
        if (!contains(name, "Fund-Positions-"))
            continue;

        if (entry.path().extension() != ".csv")
            continue;

        auto time = fs::last_write_time(entry);
        if (newest.empty() || time > newest_time)
        {
            newest = entry.path();
            newest_time = time;
        }
    }

    return newest;
}

fs::path find_newest_transactions_file()
{
    fs::path newest;
    fs::file_time_type newest_time{};

    for (const auto& entry : fs::directory_iterator(DOWNLOAD_DIR))
    {
        if (!entry.is_regular_file())
            continue;

        std::string name = entry.path().filename().string();
        if (!contains(name, "Transactions"))
            continue;

        if (entry.path().extension() != ".csv")
            continue;

        auto time = fs::last_write_time(entry.path());
        if (newest.empty() || time > newest_time)
        {
            newest = entry.path();
            newest_time = time;
        }
    }

    return newest;
}

struct Position
{
    std::string symbol;
    std::string description;
    std::string asset_type;
    double quantity = 0.0;
};

struct Transaction
{
    Date date;
    std::string action;
    std::string symbol;
    std::string description;
    double quantity = 0.0;
    double price = 0.0;
    size_t original_order = 0;
};

std::vector<Position> read_positions(const fs::path& filename)
{
    std::vector<Position> positions;
    std::ifstream file(filename);
    if (!file)
    {
        std::cerr << "ERROR: Cannot open positions file:\n" << filename << "\n";
        return positions;
    }

    std::string line;
    int symbol_col = -1;
    int desc_col = -1;
    int qty_col = -1;
    int asset_type_col = -1;

    while (std::getline(file, line))
    {
        if (trim(line).empty())
            continue;

        auto fields = parse_csv_line(line);
        for (size_t i = 0; i < fields.size(); ++i)
        {
            std::string h = remove_quotes(fields[i]);
            if (h == "Symbol")
                symbol_col = static_cast<int>(i);
            else if (h == "Description")
                desc_col = static_cast<int>(i);
            else if (h == "Qty (Quantity)")
                qty_col = static_cast<int>(i);
            else if (h == "Asset Type")
                asset_type_col = static_cast<int>(i);
        }

        if (symbol_col >= 0 && qty_col >= 0)
            break;
    }

    if (symbol_col < 0 || qty_col < 0 || asset_type_col < 0)
    {
        std::cerr << "ERROR: Could not find required columns in positions file.\n";
        return positions;
    }

    while (std::getline(file, line))
    {
        if (trim(line).empty())
            continue;

        auto fields = parse_csv_line(line);
        if (static_cast<int>(fields.size()) <= std::max(symbol_col, qty_col))
            continue;

        Position p;
        p.symbol = remove_quotes(fields[symbol_col]);
        if (desc_col >= 0 && desc_col < static_cast<int>(fields.size()))
            p.description = remove_quotes(fields[desc_col]);

        p.quantity = to_double(fields[qty_col]);
        p.asset_type = remove_quotes(fields[asset_type_col]);

        if (p.symbol.empty() || std::fabs(p.quantity) < EPSILON || p.asset_type != "Equity")
            continue;

        positions.push_back(p);
    }

    return positions;
}

std::vector<Transaction> read_transactions(const fs::path& filename)
{
    std::vector<Transaction> transactions;
    std::ifstream file(filename);
    if (!file)
    {
        std::cerr << "ERROR: Cannot open transactions file:\n" << filename << "\n";
        return transactions;
    }

    std::string line;
    if (!std::getline(file, line))
        return transactions;

    auto header = parse_csv_line(line);
    int date_col = -1;
    int action_col = -1;
    int symbol_col = -1;
    int qty_col = -1;
    int price_col = -1;

    for (size_t i = 0; i < header.size(); ++i)
    {
        std::string h = remove_quotes(header[i]);
        if (h == "Date")
            date_col = static_cast<int>(i);
        else if (h == "Action")
            action_col = static_cast<int>(i);
        else if (h == "Symbol")
            symbol_col = static_cast<int>(i);
        else if (h == "Quantity")
            qty_col = static_cast<int>(i);
        else if (h == "Price")
            price_col = static_cast<int>(i);
    }

    if (date_col < 0 || action_col < 0 || symbol_col < 0 || qty_col < 0)
    {
        std::cerr << "ERROR: Missing required transaction columns.\n";
        return transactions;
    }

    size_t order = 0;
    while (std::getline(file, line))
    {
        if (trim(line).empty())
            continue;

        auto fields = parse_csv_line(line);
        int max_col = std::max({date_col, action_col, symbol_col, qty_col});
        if (static_cast<int>(fields.size()) <= max_col)
            continue;

        Transaction t;
        t.date = parse_date(fields[date_col]);
        t.action = remove_quotes(fields[action_col]);
        std::transform(t.action.begin(), t.action.end(), t.action.begin(), [](unsigned char ch) { return static_cast<char>(std::toupper(ch)); });
        t.symbol = remove_quotes(fields[symbol_col]);
        t.quantity = std::fabs(to_double(fields[qty_col]));

        if (price_col >= 0 && price_col < static_cast<int>(fields.size()))
            t.price = std::fabs(to_double(fields[price_col]));

        t.original_order = order++;

        if (!t.date.valid() || t.symbol.empty() || t.quantity < EPSILON)
            continue;

        transactions.push_back(t);
    }

    return transactions;
}

struct BuyLot
{
    Date date;
    double quantity = 0.0;
    double price = 0.0;
};

struct DailySymbolSummary
{
    double gain = 0.0;
    double weighted_days = 0.0;
    double matched_quantity = 0.0;
};

std::map<std::string, std::map<std::string, DailySymbolSummary>> compute_daily_gain_results(
    const std::vector<Transaction>& transactions,
    const Date& start,
    const Date& end)
{
    std::map<std::string, std::vector<BuyLot>> lots_by_symbol;
    std::map<std::string, std::map<std::string, DailySymbolSummary>> daily_results;

    std::vector<Transaction> sorted = transactions;
    std::sort(sorted.begin(), sorted.end(),
        [](const Transaction& a, const Transaction& b)
        {
            std::time_t ta = date_to_time(a.date);
            std::time_t tb = date_to_time(b.date);
            if (ta != tb)
                return ta < tb;

            // Schwab exports can list a later same-day BUY after an earlier same-day SELL.
            // To avoid matching a future lot against an older position, same-day buys must
            // be processed before sells so contemporaneous lots are settled first.
            auto action_priority = [](const Transaction& tx)
            {
                if (tx.action == "BUY")
                    return 0;
                if (tx.action == "SELL")
                    return 1;
                return 2;
            };

            if (action_priority(a) != action_priority(b))
                return action_priority(a) < action_priority(b);

            return a.original_order < b.original_order;
        });

    for (const auto& tx : sorted)
    {
        if (!tx.date.valid())
            continue;

        if (tx.action == "BUY")
        {
            lots_by_symbol[tx.symbol].push_back({tx.date, tx.quantity, tx.price});
            continue;
        }

        if (tx.action != "SELL")
            continue;

        double remaining = tx.quantity;
        auto& lots = lots_by_symbol[tx.symbol];
        size_t idx = 0;

        while (remaining > EPSILON && idx < lots.size())
        {
            auto& lot = lots[idx];
            if (lot.quantity <= EPSILON)
            {
                lots.erase(lots.begin() + static_cast<std::ptrdiff_t>(idx));
                continue;
            }

            double matched = std::min(remaining, lot.quantity);
            if (date_greater_than_or_equal(tx.date, start) && date_less_than_or_equal(tx.date, end))
            {
                int held_days = days_between(lot.date, tx.date);
                std::string day_key = date_to_string(tx.date);
                auto& summary = daily_results[day_key][tx.symbol];
                summary.gain += matched * (tx.price - lot.price);
                summary.weighted_days += static_cast<double>(held_days) * matched;
                summary.matched_quantity += matched;
            }

            lot.quantity -= matched;
            remaining -= matched;

            if (lot.quantity <= EPSILON)
            {
                lots.erase(lots.begin() + static_cast<std::ptrdiff_t>(idx));
            }
            else
            {
                ++idx;
            }
        }
    }

    return daily_results;
}

bool copy_source_file(const fs::path& source, const std::string& output_name)
{
    try
    {
        fs::copy_file(source, fs::path(OUTPUT_DIR) / output_name, fs::copy_options::overwrite_existing);
        return true;
    }
    catch (const std::exception& e)
    {
        std::cerr << "WARNING: Could not copy " << source << ": " << e.what() << "\n";
        return false;
    }
}

void write_gain_loss_csv(const std::map<std::string, std::map<std::string, DailySymbolSummary>>& daily_results)
{
    fs::create_directories(OUTPUT_DIR);
    fs::path filename = fs::path(OUTPUT_DIR) / "gain_loss.csv";

    std::ofstream file(filename);
    if (!file)
    {
        std::cerr << "ERROR: Cannot create report: " << filename << "\n";
        return;
    }

    file << "Date,Symbol,Avg_Days_Held,Gain_Loss\n";
    for (const auto& [date_key, symbols] : daily_results)
    {
        for (const auto& [symbol, result] : symbols)
        {
            int avg_days = result.matched_quantity > EPSILON
                ? static_cast<int>(std::round(result.weighted_days / result.matched_quantity))
                : 0;

            file << date_key << "," << symbol << "," << avg_days << "," << std::fixed << std::setprecision(2) << result.gain << "\n";
        }
    }

    file.close();
    std::cout << "\nGain/Loss CSV written to:\n" << filename << "\n";
}

void print_usage(const char* program)
{
    std::cerr << "Usage: " << program << " MM/DD/YYYY MM/DD/YYYY\n";
    std::cerr << "Example: " << program << " 08/25/2026 08/26/2026\n";
}

int main(int argc, char* argv[])
{
    Date start, end;

    if (argc >= 3)
    {
        start = parse_date(argv[1]);
        end = parse_date(argv[2]);
    }
    else
    {
        std::cout << "Enter start date (MM/DD/YYYY): ";
        std::string start_input;
        std::getline(std::cin, start_input);
        start = parse_date(start_input);

        std::cout << "Enter end date (MM/DD/YYYY): ";
        std::string end_input;
        std::getline(std::cin, end_input);
        end = parse_date(end_input);
    }

    if (!start.valid() || !end.valid())
    {
        print_usage(argv[0]);
        return 1;
    }

    if (date_to_time(start) > date_to_time(end))
    {
        std::cerr << "ERROR: Start date must be on or before the end date.\n";
        return 1;
    }

    fs::create_directories(OUTPUT_DIR);

    fs::path positions_file = find_newest_positions_file();
    fs::path transactions_file = find_newest_transactions_file();

    if (positions_file.empty())
    {
        std::cerr << "ERROR: No Schwab Positions file found in: " << DOWNLOAD_DIR << "\n";
        return 1;
    }

    if (transactions_file.empty())
    {
        std::cerr << "ERROR: No Schwab Transactions file found in: " << DOWNLOAD_DIR << "\n";
        return 1;
    }

    auto positions = read_positions(positions_file);
    auto transactions = read_transactions(transactions_file);

    if (positions.empty())
    {
        std::cerr << "ERROR: No positions were loaded.\n";
        return 1;
    }

    if (transactions.empty())
    {
        std::cerr << "ERROR: No transactions were loaded.\n";
        return 1;
    }

    copy_source_file(positions_file, "positions.csv");
    copy_source_file(transactions_file, "transactions.csv");

    auto daily = compute_daily_gain_results(transactions, start, end);
    write_gain_loss_csv(daily);

    double total_gain = 0.0;
    for (const auto& [date_key, symbols] : daily)
    {
        for (const auto& [symbol, result] : symbols)
            total_gain += result.gain;
    }

    std::cout << "\nPeriod start: " << date_to_string(start) << "\n";
    std::cout << "Period end:   " << date_to_string(end) << "\n";
    std::cout << "Total gain for period: " << std::fixed << std::setprecision(2) << total_gain << "\n";

    return 0;
}
