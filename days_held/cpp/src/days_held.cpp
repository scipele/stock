/*
g++ -std=c++17 -O2 days_held.cpp -o ../bin/days_held
*/

#include <algorithm>
#include <chrono>
#include <cmath>
#include <ctime>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <map>
#include <sstream>
#include <string>
#include <vector>

namespace fs = std::filesystem;

const std::string DOWNLOAD_DIR = "/home/ts/Downloads";
const std::string OUTPUT_DIR   = "/home/dev/stock/days_held/output";

const double EPSILON = 0.00001;

// ------------------------------------------------------------
// Utility
// ------------------------------------------------------------

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

    if (result.size() >= 2 &&
        result.front() == '"' &&
        result.back() == '"')
    {
        result = result.substr(1, result.size() - 2);
    }

    // Remove UTF-8 BOM if present.
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

double to_double(std::string value)
{
    value = remove_quotes(value);
    value = trim(value);
    value = remove_commas(value);

    if (value.empty())
        return 0.0;

    if (value.front() == '$')
        value.erase(0, 1);

    if (!value.empty() && value.front() == '(' &&
        value.back() == ')')
    {
        value = "-" + value.substr(1, value.size() - 2);
    }

    try
    {
        return std::stod(value);
    }
    catch (...)
    {
        return 0.0;
    }
}

// ------------------------------------------------------------
// CSV parser
//
// Handles quoted fields and commas inside quoted fields.
// ------------------------------------------------------------

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
            if (in_quotes &&
                i + 1 < line.size() &&
                line[i + 1] == '"')
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

// ------------------------------------------------------------
// Date
// ------------------------------------------------------------

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

    std::string s = remove_quotes(value);

    // MM/DD/YYYY
    if (s.size() >= 10)
    {
        try
        {
            d.month = std::stoi(s.substr(0, 2));
            d.day   = std::stoi(s.substr(3, 2));
            d.year  = std::stoi(s.substr(6, 4));
        }
        catch (...)
        {
            d = {};
        }
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
    tm.tm_mon  = d.month - 1;
    tm.tm_mday = d.day;
    tm.tm_hour = 12;

    return std::mktime(&tm);
}

int days_between(const Date& older, const Date& newer)
{
    if (!older.valid() || !newer.valid())
        return 0;

    std::time_t t1 = date_to_time(older);
    std::time_t t2 = date_to_time(newer);

    double seconds = std::difftime(t2, t1);

    return static_cast<int>(std::round(seconds / (60 * 60 * 24)));
}

// ------------------------------------------------------------
// File detection
// ------------------------------------------------------------

bool contains(const std::string& value, const std::string& search)
{
    return value.find(search) != std::string::npos;
}

fs::path find_newest_positions_file()
{
    fs::path newest;
    fs::file_time_type newest_time{};

    for (const auto& entry :
         fs::directory_iterator(DOWNLOAD_DIR))
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

    for (const auto& entry :
         fs::directory_iterator(DOWNLOAD_DIR))
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

// ------------------------------------------------------------
// Structures
// ------------------------------------------------------------

struct Position
{
    std::string symbol;
    std::string description;
    std::string asset_type;
    double quantity = 0.0;
};

enum class Action
{
    BUY,
    SELL,
    OTHER
};

struct Transaction
{
    Date date;

    Action action = Action::OTHER;

    std::string symbol;
    std::string description;

    double quantity = 0.0;
    double price = 0.0;

    size_t original_order = 0;
};

// ------------------------------------------------------------
// Read Positions
// ------------------------------------------------------------

std::vector<Position> read_positions(const fs::path& filename)
{
    std::vector<Position> positions;

    std::ifstream file(filename);

    if (!file)
    {
        std::cerr << "ERROR: Cannot open positions file:\n"
                  << filename << "\n";

        return positions;
    }

    std::string line;

    std::vector<std::string> header;

    int symbol_col = -1;
    int desc_col   = -1;
    int qty_col    = -1;
    int asset_type_col = -1;

    // Schwab places an account-information line before
    // the actual Positions CSV header.
    //
    // Search for the real header rather than assuming
    // that the first line is the header.

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

        // We found the real Schwab header.
        if (symbol_col >= 0 && qty_col >= 0)
        {
            header = fields;
            break;
        }
    }

    if (symbol_col < 0 ||
        qty_col < 0 ||
        asset_type_col < 0)
    {
        std::cerr
            << "ERROR: Could not find required columns in positions file.\n\n"
            << "Detected header columns:\n";

        for (size_t i = 0; i < header.size(); ++i)
        {
            std::cerr
                << "  [" << i << "] = <"
                << remove_quotes(header[i])
                << ">\n";
        }

        std::cerr
            << "\nDetected Symbol column: "
            << symbol_col
            << "\nDetected Qty column: "
            << qty_col
            << "\nDetected Asset Type column: "
            << asset_type_col
            << "\n";

        return positions;
    }

    while (std::getline(file, line))
    {
        if (trim(line).empty())
            continue;

        auto fields = parse_csv_line(line);

        if (static_cast<int>(fields.size()) <=
            std::max(symbol_col, qty_col))
        {
            continue;
        }

        Position p;

        p.symbol = remove_quotes(fields[symbol_col]);

        if (desc_col >= 0 &&
            desc_col < static_cast<int>(fields.size()))
        {
            p.description = remove_quotes(fields[desc_col]);
        }

        p.quantity = to_double(fields[qty_col]);
        p.asset_type = remove_quotes(fields[asset_type_col]);

        if (p.symbol.empty())
            continue;

        // Ignore zero positions.
        if (std::fabs(p.quantity) < EPSILON)
            continue;

        // Only process positions whose Schwab Asset Type
        // is exactly "Equity".
        if (p.asset_type != "Equity")
            continue;

        positions.push_back(p);
    }

    return positions;
}

// ------------------------------------------------------------
// Read Transactions
// ------------------------------------------------------------

std::vector<Transaction> read_transactions(const fs::path& filename)
{
    std::vector<Transaction> transactions;

    std::ifstream file(filename);

    if (!file)
    {
        std::cerr << "ERROR: Cannot open transactions file:\n"
                  << filename << "\n";

        return transactions;
    }

    std::string line;

    if (!std::getline(file, line))
        return transactions;

    auto header = parse_csv_line(line);

    int date_col   = -1;
    int action_col = -1;
    int symbol_col = -1;
    int desc_col   = -1;
    int qty_col    = -1;
    int price_col  = -1;

    for (size_t i = 0; i < header.size(); ++i)
    {
        std::string h = remove_quotes(header[i]);

        if (h == "Date")
            date_col = static_cast<int>(i);

        else if (h == "Action")
            action_col = static_cast<int>(i);

        else if (h == "Symbol")
            symbol_col = static_cast<int>(i);

        else if (h == "Description")
            desc_col = static_cast<int>(i);

        else if (h == "Quantity")
            qty_col = static_cast<int>(i);

        else if (h == "Price")
            price_col = static_cast<int>(i);
    }

    if (date_col < 0 ||
        action_col < 0 ||
        symbol_col < 0 ||
        qty_col < 0)
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

        int max_col = std::max(
            {date_col, action_col, symbol_col, qty_col});

        if (static_cast<int>(fields.size()) <= max_col)
            continue;

        Transaction t;

        t.date = parse_date(fields[date_col]);

        std::string action =
            remove_quotes(fields[action_col]);

        t.symbol =
            remove_quotes(fields[symbol_col]);

        if (desc_col >= 0 &&
            desc_col < static_cast<int>(fields.size()))
        {
            t.description =
                remove_quotes(fields[desc_col]);
        }

        t.quantity =
            std::fabs(to_double(fields[qty_col]));

        if (price_col >= 0 &&
            price_col < static_cast<int>(fields.size()))
        {
            t.price =
                std::fabs(to_double(fields[price_col]));
        }

        if (action == "Buy")
            t.action = Action::BUY;

        else if (action == "Sell")
            t.action = Action::SELL;

        else
            t.action = Action::OTHER;

        t.original_order = order++;

        if (!t.date.valid())
            continue;

        if (t.symbol.empty())
            continue;

        if (t.quantity < EPSILON)
            continue;

        transactions.push_back(t);
    }

    return transactions;
}

// ------------------------------------------------------------
// Buy lot used for reconstruction
// ------------------------------------------------------------

struct MatchedBuy
{
    Date date;
    double quantity = 0.0;
    double price = 0.0;
};

// ------------------------------------------------------------
// Result
// ------------------------------------------------------------

struct HoldingResult
{
    Position position;

    double matched_quantity = 0.0;
    double unmatched_quantity = 0.0;

    Date oldest_buy_date;

    double weighted_cost = 0.0;
    double weighted_quantity = 0.0;

    int buy_transactions = 0;

    std::string status;
};


// ------------------------------------------------------------
// Reconstruct current holding period
//
// The purpose of this function is NOT tax-lot accounting.
//
// It determines how long the CURRENT open position has been
// held.
//
// A completely sold position resets the holding period.
//
// Example:
//
//   BUY  100
//   SELL 100
//   BUY  100
//
// The final position has been held only since the second BUY.
//
// Partial sells do NOT reset the holding period unless the
// position reaches zero.
// ------------------------------------------------------------

HoldingResult reconstruct_position(
    const Position& position,
    const std::vector<Transaction>& all_transactions)
{
    HoldingResult result;

    result.position = position;

    // --------------------------------------------------------
    // Get transactions for this symbol
    // --------------------------------------------------------

    std::vector<Transaction> transactions;

    for (const auto& t : all_transactions)
    {
        if (t.symbol == position.symbol)
            transactions.push_back(t);
    }

    // --------------------------------------------------------
    // Sort oldest -> newest
    //
    // original_order preserves the order in the source file
    // for transactions occurring on the same date.
    // --------------------------------------------------------

    std::sort(
        transactions.begin(),
        transactions.end(),
        [](const Transaction& a, const Transaction& b)
        {
            std::time_t ta = date_to_time(a.date);
            std::time_t tb = date_to_time(b.date);

            if (ta != tb)
                return ta < tb;

            return a.original_order > b.original_order;
        }
    );

    // --------------------------------------------------------
    // Current reconstructed position
    // --------------------------------------------------------

    double current_quantity = 0.0;

    Date current_start_date;

    double current_cost = 0.0;

    int current_buy_transactions = 0;

    // --------------------------------------------------------
    // Process transactions chronologically
    // --------------------------------------------------------

    for (const auto& t : transactions)
    {
        // ----------------------------------------------------
        // BUY
        // ----------------------------------------------------

        if (t.action == Action::BUY)
        {
            // If we currently have no position, this BUY
            // starts a brand-new holding period.
            if (current_quantity <= EPSILON)
            {
                current_start_date = t.date;

                current_cost = 0.0;

                current_buy_transactions = 0;
            }

            current_quantity += t.quantity;

            current_cost +=
                t.quantity * t.price;

            ++current_buy_transactions;

            continue;
        }

        // ----------------------------------------------------
        // SELL
        // ----------------------------------------------------

        if (t.action == Action::SELL)
        {
            current_quantity -= t.quantity;

            // ------------------------------------------------
            // Position completely closed.
            //
            // This is the important part:
            //
            // Everything before this point is now irrelevant
            // to the current holding period.
            // ------------------------------------------------

            if (current_quantity <= EPSILON)
            {
                current_quantity = 0.0;

                current_start_date = {};

                current_cost = 0.0;

                current_buy_transactions = 0;
            }

            continue;
        }
    }

    // --------------------------------------------------------
    // Compare reconstructed position with actual position
    // --------------------------------------------------------

    if (current_quantity <= EPSILON)
    {
        result.status = "NO_OPEN_POSITION";
        return result;
    }

    result.matched_quantity =
        std::min(
            current_quantity,
            position.quantity);

    if (current_quantity <
        position.quantity - EPSILON)
    {
        result.unmatched_quantity =
            position.quantity -
            current_quantity;

        result.status = "PARTIAL";
    }
    else
    {
        result.unmatched_quantity = 0.0;
        result.status = "OK";
    }

    // --------------------------------------------------------
    // Current holding period
    // --------------------------------------------------------

    result.oldest_buy_date =
        current_start_date;

    // --------------------------------------------------------
    // Current position cost
    // --------------------------------------------------------

    result.weighted_quantity =
        current_quantity;

    result.weighted_cost =
        current_cost;

    result.buy_transactions =
        current_buy_transactions;

    return result;
}

// ------------------------------------------------------------
// Copy source files to output
// ------------------------------------------------------------

bool copy_source_file(
    const fs::path& source,
    const std::string& output_name)
{
    try
    {
        fs::copy_file(
            source,
            fs::path(OUTPUT_DIR) / output_name,
            fs::copy_options::overwrite_existing);

        return true;
    }
    catch (const std::exception& e)
    {
        std::cerr << "WARNING: Could not copy "
                  << source << ": "
                  << e.what() << "\n";

        return false;
    }
}

// ------------------------------------------------------------
// Write report
// ------------------------------------------------------------

void write_report(
    const std::vector<HoldingResult>& results)
{
    fs::create_directories(OUTPUT_DIR);

    fs::path filename =
        fs::path(OUTPUT_DIR) / "days_held.csv";

    std::ofstream file(filename);

    if (!file)
    {
        std::cerr << "ERROR: Cannot create report:\n"
                  << filename << "\n";
        return;
    }

    file << "Symbol,"
         << "Description,"
         << "CurrentQty,"
         << "MatchedQty,"
         << "UnmatchedQty,"
         << "OldestBuyDate,"
         << "DaysHeld,"
         << "AvgBuyPrice,"
         << "BuyTransactions,"
         << "Status\n";

    Date today;

    {
        auto now = std::chrono::system_clock::now();
        std::time_t t =
            std::chrono::system_clock::to_time_t(now);

        std::tm local{};

        localtime_r(&t, &local);

        today.year  = local.tm_year + 1900;
        today.month = local.tm_mon + 1;
        today.day   = local.tm_mday;
    }

    file << std::fixed;

    for (const auto& r : results)
    {
        double avg_price = 0.0;

        if (r.weighted_quantity > EPSILON)
        {
            avg_price =
                r.weighted_cost /
                r.weighted_quantity;
        }

        int held_days = 0;

        if (r.oldest_buy_date.valid())
        {
            held_days =
                days_between(
                    r.oldest_buy_date,
                    today);
        }

        file << r.position.symbol << ","
             << "\"" << r.position.description << "\","
             << std::setprecision(8)
             << r.position.quantity << ","
             << r.matched_quantity << ","
             << r.unmatched_quantity << ","
             << date_to_string(r.oldest_buy_date) << ","
             << held_days << ","
             << std::setprecision(4)
             << avg_price << ","
             << r.buy_transactions << ","
             << r.status
             << "\n";
    }

    file.close();

    std::cout << "\nReport written to:\n"
              << filename << "\n";
}

// ------------------------------------------------------------
// Main
// ------------------------------------------------------------

int main()
{
    std::cout
        << "=============================================\n"
        << " Schwab Days Held\n"
        << "=============================================\n\n";

    fs::create_directories(OUTPUT_DIR);

    // --------------------------------------------------------
    // Locate newest files
    // --------------------------------------------------------

    fs::path positions_file =
        find_newest_positions_file();

    fs::path transactions_file =
        find_newest_transactions_file();

    if (positions_file.empty())
    {
        std::cerr
            << "ERROR: No Schwab Positions file found in:\n"
            << DOWNLOAD_DIR << "\n";

        return 1;
    }

    if (transactions_file.empty())
    {
        std::cerr
            << "ERROR: No Schwab Transactions file found in:\n"
            << DOWNLOAD_DIR << "\n";

        return 1;
    }

    std::cout
        << "Positions file:\n  "
        << positions_file << "\n\n";

    std::cout
        << "Transactions file:\n  "
        << transactions_file << "\n\n";

    // --------------------------------------------------------
    // Read files
    // --------------------------------------------------------

    auto positions =
        read_positions(positions_file);

    auto transactions =
        read_transactions(transactions_file);

    std::cout
        << "Positions loaded:    "
        << positions.size() << "\n";

    std::cout
        << "Transactions loaded: "
        << transactions.size() << "\n\n";

    if (positions.empty())
    {
        std::cerr
            << "ERROR: No positions were loaded.\n";

        return 1;
    }

    if (transactions.empty())
    {
        std::cerr
            << "ERROR: No transactions were loaded.\n";

        return 1;
    }

    // --------------------------------------------------------
    // Reconstruct positions
    // --------------------------------------------------------

    std::vector<HoldingResult> results;

    for (const auto& position : positions)
    {
        HoldingResult result =
            reconstruct_position(
                position,
                transactions);

        results.push_back(result);

        std::cout
            << std::left
            << std::setw(8)
            << position.symbol
            << " Qty="
            << std::setw(12)
            << std::fixed
            << std::setprecision(4)
            << position.quantity
            << " Matched="
            << std::setw(12)
            << result.matched_quantity
            << " Status="
            << result.status;

        if (result.oldest_buy_date.valid())
        {
            std::cout
                << " OldestBuy="
                << date_to_string(
                       result.oldest_buy_date);
        }

        std::cout << "\n";
    }

    // --------------------------------------------------------
    // Copy source files
    // --------------------------------------------------------

    copy_source_file(
        positions_file,
        "positions.csv");

    copy_source_file(
        transactions_file,
        "transactions.csv");

    // --------------------------------------------------------
    // Write report
    // --------------------------------------------------------

    write_report(results);

    std::cout
        << "\nCompleted successfully.\n";

    return 0;
}