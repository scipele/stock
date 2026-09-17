/* Compile in Ubuntu with:
g++ -std=c++17 -O2 intr_buy.cpp -o ../bin/intr_buy
*/

#include <iostream>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>
#include <unordered_map>
#include <algorithm>
#include <iomanip>
#include <cmath>
#include <filesystem>
#include <cctype>

using namespace std;


// ============================================================
// Configuration
// ============================================================

struct Config
{
    string buyFile;
    string intrinsicFile;
    string outputFile;
    string analystFile = "auto";

    double buyWeight = 0.55;
    double intrinsicWeight = 0.20;
    double analystWeight = 0.25;

    double consensusMax = 10.0;
    double consensusPenalty = 0.50;
};


// ============================================================
// Stock data
// ============================================================

struct Stock
{
    string ticker;
    string company;

    int sector = 0;
    int exch = 4;
    int index = 0;

    bool owned = false;


    // Final scores
    double combinedScore = 0;
    double buyScore = 0;
    double intrinsicScore = 0;
    double analystScore = 0;
    double consensusBonus = 0;

    double marketEdgePoints = 0;
    double schwabPoints = 0;
    double morningstarStarsPoints = 0;
    double moatPoints = 0;

    string marketEdgeRating;
    string schwabRating;
    string morningstarRating;
    string moatRating;


    // Price / valuation
    double price = 0;
    double intrinsicValue = 0;

    double marginSafety = 0;
    double upside = 0;


    // Market metrics
    double rsi = 0;
    double momentum = 0;
    double volatility = 0;


    // Valuation metrics
    double forwardPE = 0;
    double trailingPE = 0;


    // Buy opportunity components
    double swingScore = 0;
    double supportScore = 0;
    double peScore = 0;
    double rsiScore = 0;
    double momentumScore = 0;
    double volatilityScore = 0;


    // Intrinsic components
    double growthRate = 0;
    double wacc = 0;

    string dataQuality;
};


// ============================================================
// CSV Helpers
// ============================================================

vector<string> splitCSV(const string& line)
{
    vector<string> result;

    string field;
    bool inQuotes = false;


    for(char c : line)
    {
        if(c == '"')
        {
            inQuotes = !inQuotes;
        }
        else if(c == ',' && !inQuotes)
        {
            result.push_back(field);
            field.clear();
        }
        else
        {
            field += c;
        }
    }

    result.push_back(field);

    return result;
}

string trim(const string& value)
{
    const size_t start = value.find_first_not_of(" \t\r\n");

    if(start == string::npos)
        return "";

    const size_t end = value.find_last_not_of(" \t\r\n");
    return value.substr(start, end - start + 1);
}

string toUpper(string value)
{
    transform(
        value.begin(),
        value.end(),
        value.begin(),
        [](unsigned char c)
        {
            return static_cast<char>(toupper(c));
        });

    return value;
}

string normalizeHeaderKey(string value)
{
    string out;

    for(unsigned char c : value)
    {
        if(isalnum(c))
            out += static_cast<char>(tolower(c));
    }

    return out;
}

bool readCSVRecord(ifstream& file, string& record)
{
    record.clear();

    string line;
    bool sawLine = false;
    bool inQuotes = false;

    while(getline(file, line))
    {
        if(sawLine)
            record += "\n";

        record += line;
        sawLine = true;

        for(char c : line)
        {
            if(c == '"')
                inQuotes = !inQuotes;
        }

        if(!inQuotes)
            break;
    }

    return sawLine;
}

int findColumn(
    const vector<string>& headers,
    const string& expectedKey)
{
    for(size_t i = 0; i < headers.size(); ++i)
    {
        if(normalizeHeaderKey(headers[i]) == expectedKey)
            return static_cast<int>(i);
    }

    return -1;
}

double clampRange(
    double value,
    double minValue,
    double maxValue)
{
    return max(minValue, min(maxValue, value));
}

void normalizeWeights(Config& config)
{
    if(config.buyWeight < 0.0)
        config.buyWeight = 0.0;

    if(config.intrinsicWeight < 0.0)
        config.intrinsicWeight = 0.0;

    if(config.analystWeight < 0.0)
        config.analystWeight = 0.0;

    const double totalWeight =
        config.buyWeight +
        config.intrinsicWeight +
        config.analystWeight;

    if(totalWeight <= 0.0)
    {
        config.buyWeight = 0.55;
        config.intrinsicWeight = 0.20;
        config.analystWeight = 0.25;
        return;
    }

    config.buyWeight /= totalWeight;
    config.intrinsicWeight /= totalWeight;
    config.analystWeight /= totalWeight;
}



double toDouble(const string& value)
{
    try
    {
        if(value.empty())
            return 0.0;

        return stod(value);
    }
    catch(...)
    {
        return 0.0;
    }
}



int toInt(const string& value)
{
    try
    {
        if(value.empty())
            return 0;

        return stoi(value);
    }
    catch(...)
    {
        return 0;
    }
}


// ============================================================
// Load Paths CSV
// ============================================================

void loadPaths(
    const string& filename,
    Config& config)
{

    ifstream file(filename);

    if(!file)
    {
        cerr << "ERROR: Cannot open "
             << filename
             << endl;

        exit(1);
    }


    string line;

    getline(file,line);   // header


    while(getline(file,line))
    {
        auto cols = splitCSV(line);

        if(cols.size() < 2)
            continue;


        if(cols[0] == "BuyFile")
            config.buyFile = cols[1];

        else if(cols[0] == "IntrinsicFile")
            config.intrinsicFile = cols[1];

        else if(cols[0] == "OutputFile")
            config.outputFile = cols[1];

        else if(cols[0] == "AnalystFile")
            config.analystFile = cols[1];
    }
}



// ============================================================
// Load Weight CSV
// ============================================================

void loadWeights(
    const string& filename,
    Config& config)
{

    ifstream file(filename);

    if(!file)
    {
        cerr << "ERROR: Cannot open "
             << filename
             << endl;

        exit(1);
    }


    string line;

    getline(file,line);


    while(getline(file,line))
    {

        auto cols = splitCSV(line);


        if(cols.size() < 2)
            continue;


        double value = toDouble(cols[1]);


        if(cols[0] == "BuyScoreWeight" ||
           cols[0] == "BuyOpportunityWeight")
            config.buyWeight = value;


        else if(cols[0] == "IntrinsicScoreWeight" ||
                cols[0] == "IntrinsicWeight")
            config.intrinsicWeight = value;


        else if(cols[0] == "AnalystScoreWeight" ||
                cols[0] == "AnalystWeight")
            config.analystWeight = value;


        else if(cols[0] == "ConsensusBonusMax")
            config.consensusMax = value;


        else if(cols[0] == "ConsensusPenaltyPerDifference")
            config.consensusPenalty = value;
    }
}

string resolveAnalystFile(const Config& config)
{
    namespace fs = std::filesystem;

    const string configured = trim(config.analystFile);

    if(!configured.empty() &&
       configured != "auto" &&
       configured != "AUTO")
    {
        if(fs::exists(configured))
            return configured;

        cerr << "WARNING: Analyst file not found: "
             << configured
             << endl;
    }

    const fs::path downloadsDir("/home/ts/Downloads");

    if(!fs::exists(downloadsDir))
        return "";

    fs::file_time_type newestTime;
    fs::path newestFile;
    bool hasAny = false;

    for(const auto& entry : fs::directory_iterator(downloadsDir))
    {
        if(!entry.is_regular_file())
            continue;

        const fs::path p = entry.path();
        const string filename = p.filename().string();

        if(filename.rfind("Results", 0) != 0)
            continue;

        if(p.extension() != ".csv")
            continue;

        const auto time = fs::last_write_time(p);

        if(!hasAny || time > newestTime)
        {
            newestTime = time;
            newestFile = p;
            hasAny = true;
        }
    }

    if(!hasAny)
        return "";

    return newestFile.string();
}

double scoreMarketEdge(const string& rating)
{
    const string key = toUpper(trim(rating));

    if(key.empty())
        return 0.0;

    if(key.find("LONG") != string::npos)
        return 30.0;

    if(key.find("NEUTRAL") != string::npos)
        return 16.0;

    if(key.find("AVOID") != string::npos)
        return 4.0;

    if(key.find("CAUTION") != string::npos)
        return 8.0;

    return 0.0;
}

double scoreSchwab(const string& rating)
{
    const string key = toUpper(trim(rating));

    if(key.empty())
        return 0.0;

    if(key == "A+") return 30.0;
    if(key == "A") return 29.0;
    if(key == "A-") return 27.0;

    if(key == "B+") return 25.0;
    if(key == "B") return 23.0;
    if(key == "B-") return 21.0;

    if(key == "C+") return 19.0;
    if(key == "C") return 17.0;
    if(key == "C-") return 15.0;

    if(key == "D+") return 12.0;
    if(key == "D") return 9.0;
    if(key == "D-") return 6.0;

    if(key == "F") return 2.0;

    return 0.0;
}

double scoreMorningstarStars(const string& rating)
{
    const string key = trim(rating);

    if(key.empty())
        return 0.0;

    if(!key.empty() && isdigit(static_cast<unsigned char>(key[0])))
    {
        const int stars = key[0] - '0';

        switch(stars)
        {
            case 5: return 20.0;
            case 4: return 16.0;
            case 3: return 12.0;
            case 2: return 6.0;
            case 1: return 2.0;
            default: break;
        }
    }

    return 0.0;
}

double scoreMoat(const string& rating)
{
    const string key = toUpper(trim(rating));

    if(key.empty())
        return 0.0;

    if(key.find("WIDE") != string::npos)
        return 20.0;

    if(key.find("NARROW") != string::npos)
        return 12.0;

    if(key.find("NONE") != string::npos)
        return 4.0;

    return 0.0;
}

void loadAnalystRatings(
    const Config& config,
    unordered_map<string, Stock>& stocks)
{
    for(auto& item : stocks)
    {
        Stock& s = item.second;
        s.analystScore = 0.0;
        s.marketEdgePoints = 0.0;
        s.schwabPoints = 0.0;
        s.morningstarStarsPoints = 0.0;
        s.moatPoints = 0.0;

        s.marketEdgeRating = "N/A";
        s.schwabRating = "N/A";
        s.morningstarRating = "N/A";
        s.moatRating = "N/A";
    }

    const string analystFile = resolveAnalystFile(config);

    if(analystFile.empty())
    {
        cout << "       Analyst rating file not found. "
             << "Using lowest analyst score = 0." << endl;
        return;
    }

    ifstream file(analystFile);

    if(!file)
    {
        cout << "       Unable to open analyst rating file. "
             << "Using lowest analyst score = 0." << endl;
        return;
    }

    string headerRecord;

    if(!readCSVRecord(file, headerRecord))
    {
        cout << "       Analyst rating file is empty. "
             << "Using lowest analyst score = 0." << endl;
        return;
    }

    const auto headers = splitCSV(headerRecord);

    const int symbolCol = findColumn(headers, "symbol");
    const int schwabCol = findColumn(headers, "schwabequityrating");
    const int starsCol = findColumn(headers, "morningstarrating");
    const int moatCol = findColumn(headers, "morningstareconomicmoat");

    int edgeCol = findColumn(headers, "marketedgesecondopinionweekly");

    if(edgeCol < 0)
        edgeCol = findColumn(headers, "marketedgesecondopinion");

    if(symbolCol < 0 ||
       schwabCol < 0 ||
       starsCol < 0 ||
       moatCol < 0 ||
       edgeCol < 0)
    {
        cout << "       Analyst file columns not recognized. "
             << "Using lowest analyst score = 0." << endl;
        return;
    }

    int loadedCount = 0;
    string record;

    while(readCSVRecord(file, record))
    {
        if(trim(record).empty())
            continue;

        const auto cols = splitCSV(record);

        const size_t minCols = static_cast<size_t>(
            max({symbolCol, schwabCol, starsCol, moatCol, edgeCol}) + 1);

        if(cols.size() < minCols)
            continue;

        const string ticker = toUpper(trim(cols[symbolCol]));

        auto it = stocks.find(ticker);

        if(it == stocks.end())
            continue;

        Stock& s = it->second;

        s.schwabRating = trim(cols[schwabCol]);
        s.morningstarRating = trim(cols[starsCol]);
        s.moatRating = trim(cols[moatCol]);
        s.marketEdgeRating = trim(cols[edgeCol]);

        s.marketEdgePoints =
            scoreMarketEdge(s.marketEdgeRating);

        s.schwabPoints =
            scoreSchwab(s.schwabRating);

        s.morningstarStarsPoints =
            scoreMorningstarStars(s.morningstarRating);

        s.moatPoints =
            scoreMoat(s.moatRating);

        s.analystScore =
            s.marketEdgePoints +
            s.schwabPoints +
            s.morningstarStarsPoints +
            s.moatPoints;

        s.analystScore = clampRange(s.analystScore, 0.0, 100.0);
        ++loadedCount;
    }

    cout << "       Loaded analyst ratings from: "
         << analystFile
         << endl;

    cout << "       Analyst ratings matched: "
         << loadedCount
         << " tickers"
         << endl;
}

// ============================================================
// Load Buy Opportunity CSV
// ============================================================

unordered_map<string, Stock> loadBuyOpportunity(
    const string& filename)
{
    unordered_map<string, Stock> stocks;


    ifstream file(filename);

    if(!file)
    {
        cerr << "ERROR: Cannot open "
             << filename
             << endl;

        exit(1);
    }


    string line;

    getline(file,line);   // header


    while(getline(file,line))
    {

        if(line.empty())
            continue;


        auto cols = splitCSV(line);


        /*
        Expected:

        0 Rank
        1 Owned
        2 Ticker
        3 Company
        4 Sector
        5 Overall_Score
        6 Price
        7 Previous_Low
        8 Swing_Low
        9 Dist_Previous_Low_pct
        10 Dist_Swing_Low_pct
        11 RSI
        12 Forward_PE
        13 Trailing_PE
        14 Momentum_3M
        15 Volatility
        16 Swing_Score
        17 Support_Score
        18 PE_Score
        19 RSI_Score
        20 Momentum_Score
        21 Volatility_Score
        */


        if(cols.size() < 22)
            continue;

        const bool hasExchIndex = cols.size() >= 24;
        const int offset = hasExchIndex ? 2 : 0;


        Stock s;


        s.ticker = cols[2];
        s.company = cols[3];

        s.sector = toInt(cols[4]);

        if(hasExchIndex)
        {
            s.exch = toInt(cols[5]);
            s.index = toInt(cols[6]);
        }


        // Owned column
        if(!cols[1].empty())
            s.owned = true;


        s.buyScore = toDouble(cols[5 + offset]);

        s.price = toDouble(cols[6 + offset]);


        s.rsi = toDouble(cols[11 + offset]);

        s.forwardPE = toDouble(cols[12 + offset]);
        s.trailingPE = toDouble(cols[13 + offset]);


        s.momentum = toDouble(cols[14 + offset]);
        s.volatility = toDouble(cols[15 + offset]);


        s.swingScore =
            toDouble(cols[16 + offset]);

        s.supportScore =
            toDouble(cols[17 + offset]);

        s.peScore =
            toDouble(cols[18 + offset]);

        s.rsiScore =
            toDouble(cols[19 + offset]);

        s.momentumScore =
            toDouble(cols[20 + offset]);

        s.volatilityScore =
            toDouble(cols[21 + offset]);


        stocks[s.ticker] = s;
    }


    return stocks;
}



// ============================================================
// Load Intrinsic Value CSV
// ============================================================

void loadIntrinsicValue(
    const string& filename,
    unordered_map<string, Stock>& stocks)
{

    ifstream file(filename);


    if(!file)
    {
        cerr << "ERROR: Cannot open "
             << filename
             << endl;

        exit(1);
    }


    string line;


    getline(file,line);   // header


    while(getline(file,line))
    {

        if(line.empty())
            continue;


        auto cols = splitCSV(line);


        /*
        Expected:

        0 Rank
        1 Ticker
        2 Company
        3 Sector
        4 Price
        5 IntrinsicValue
        6 MarginOfSafety_pct
        7 Upside_pct
        8 GrowthRate
        9 WACC
        10 FCF_TTM
        11 NetDebt
        12 Shares
        13 MarketCap
        14 ForwardPE
        15 TrailingPE
        16 DataQuality
        */


        if(cols.size() < 17)
            continue;

        const bool hasExchIndex = cols.size() >= 19;
        const int offset = hasExchIndex ? 2 : 0;


        string ticker = cols[1];


        // Creates a new record if ticker was
        // only found in intrinsic file
        Stock& s = stocks[ticker];


        s.ticker = ticker;


        s.company = cols[2];


        s.sector = toInt(cols[3]);

        if(hasExchIndex)
        {
            s.exch = toInt(cols[4]);
            s.index = toInt(cols[5]);
        }


        s.price =
            toDouble(cols[4 + offset]);


        s.intrinsicValue =
            toDouble(cols[5 + offset]);


        s.marginSafety =
            toDouble(cols[6 + offset]);


        s.upside =
            toDouble(cols[7 + offset]);


        s.growthRate =
            toDouble(cols[8 + offset]);


        s.wacc =
            toDouble(cols[9 + offset]);


        s.forwardPE =
            toDouble(cols[14 + offset]);


        s.trailingPE =
            toDouble(cols[15 + offset]);


        s.dataQuality =
            cols[16 + offset];
    }
}

// ============================================================
// Calculate Intrinsic Score
// ============================================================

double calculateIntrinsicScore(const Stock& s)
{
    double score = 0.0;


    // ----------------------------------------
    // Margin of Safety - 45%
    // ----------------------------------------

    double mosScore = s.marginSafety;

    if(mosScore > 100)
        mosScore = 100;

    if(mosScore < 0)
        mosScore = 0;


    score += mosScore * 0.45;



    // ----------------------------------------
    // Upside - 25%
    // ----------------------------------------

    double upsideScore =
        s.upside / 4.0;


    if(upsideScore > 100)
        upsideScore = 100;

    if(upsideScore < 0)
        upsideScore = 0;


    score += upsideScore * 0.25;



    // ----------------------------------------
    // Forward PE - 10%
    // ----------------------------------------

    double peScore = 50;


    if(s.forwardPE > 0)
    {
        if(s.forwardPE < 10)
            peScore = 100;

        else if(s.forwardPE < 20)
            peScore = 75;

        else if(s.forwardPE < 30)
            peScore = 50;

        else
            peScore = 25;
    }


    score += peScore * 0.10;



    // ----------------------------------------
    // Growth Rate - 10%
    // ----------------------------------------

    double growthScore = 50;


    if(s.growthRate > 0.10)
        growthScore = 100;

    else if(s.growthRate > 0.05)
        growthScore = 75;

    else if(s.growthRate > 0)
        growthScore = 50;

    else
        growthScore = 25;


    score += growthScore * 0.10;



    // ----------------------------------------
    // Data Quality - 10%
    // ----------------------------------------

    if(s.dataQuality == "ok")
        score += 100 * 0.10;


    return min(score,100.0);
}



// ============================================================
// Calculate Combined Scores
// ============================================================

void calculateScores(
    unordered_map<string,Stock>& stocks,
    const Config& config)
{

    for(auto& item : stocks)
    {

        Stock& s = item.second;


        s.intrinsicScore =
            calculateIntrinsicScore(s);



        // ----------------------------------------
        // Agreement bonus
        // ----------------------------------------

        double difference =
            abs(
                s.buyScore -
                s.intrinsicScore
            );


        s.consensusBonus =
            config.consensusMax -
            (difference *
             config.consensusPenalty);



        if(s.consensusBonus < 0)
            s.consensusBonus = 0;



        // ----------------------------------------
        // Final Score
        // ----------------------------------------

        s.combinedScore =
            (s.buyScore *
             config.buyWeight)

            +

            (s.intrinsicScore *
             config.intrinsicWeight)

            +

            (s.analystScore *
             config.analystWeight);



        if(s.combinedScore > 100)
            s.combinedScore = 100;
    }
}



// ============================================================
// Sort and Write Report
// ============================================================

void writeReport(
    const string& filename,
    unordered_map<string,Stock>& stocks)
{

    vector<Stock> list;


    for(auto& item : stocks)
        list.push_back(item.second);



    sort(
        list.begin(),
        list.end(),
        [](const Stock& a,const Stock& b)
        {
            return a.combinedScore >
                   b.combinedScore;
        });



    ofstream out(filename);


    if(!out)
    {
        cerr << "ERROR: Cannot write "
             << filename
             << endl;

        return;
    }



    out
    << "Rank,"
    << "Ticker,"
    << "Company,"
    << "Sector,"
    << "Exch,"
    << "Index,"
    << "Owned,"
    << "CombinedScore,"
    << "BuyScore,"
    << "IntrinsicScore,"
    << "AnalystScore,"
    << "MarketEdgePoints,"
    << "SchwabPoints,"
    << "MorningstarStarsPoints,"
    << "MoatPoints,"
    << "MarketEdgeRating,"
    << "SchwabRating,"
    << "MorningstarRating,"
    << "MorningstarMoat,"
    << "ConsensusBonus,"
    << "Price,"
    << "IntrinsicValue,"
    << "MarginSafety_pct,"
    << "Upside_pct,"
    << "RSI,"
    << "Momentum_3M,"
    << "Volatility,"
    << "ForwardPE,"
    << "TrailingPE,"
    << "SwingScore,"
    << "SupportScore,"
    << "PEScore,"
    << "RSIScore,"
    << "MomentumScore,"
    << "VolatilityScore,"
    << "GrowthRate,"
    << "WACC,"
    << "DataQuality"
    << "\n";



    out << fixed << setprecision(2);



    int rank = 1;


    for(const auto& s : list)
    {

        out
        << rank++ << ","
        << s.ticker << ","
        << "\"" << s.company << "\","
        << s.sector << ","
        << s.exch << ","
        << s.index << ","
        << (s.owned ? "CP" : "") << ","

        << s.combinedScore << ","
        << s.buyScore << ","
        << s.intrinsicScore << ","
        << s.analystScore << ","
        << s.marketEdgePoints << ","
        << s.schwabPoints << ","
        << s.morningstarStarsPoints << ","
        << s.moatPoints << ","
        << "\"" << s.marketEdgeRating << "\"" << ","
        << "\"" << s.schwabRating << "\"" << ","
        << "\"" << s.morningstarRating << "\"" << ","
        << "\"" << s.moatRating << "\"" << ","
        << s.consensusBonus << ","

        << s.price << ","
        << s.intrinsicValue << ","

        << s.marginSafety << ","
        << s.upside << ","

        << s.rsi << ","
        << s.momentum << ","
        << s.volatility << ","

        << s.forwardPE << ","
        << s.trailingPE << ","

        << s.swingScore << ","
        << s.supportScore << ","
        << s.peScore << ","
        << s.rsiScore << ","
        << s.momentumScore << ","
        << s.volatilityScore << ","

        << s.growthRate << ","
        << s.wacc << ","

        << s.dataQuality

        << "\n";
    }


    cout
    << "       Created "
    << filename
    << " ("
    << list.size()
    << " stocks)"
    << endl;
}


// ============================================================
// Main Program
// ============================================================

int main()
{

    cout << endl;
    cout << "       ==========================================" << endl;
    cout << "        Intrinsic + Buy Opportunity Analyzer" << endl;
    cout << "       ==========================================" << endl;
    cout << endl;


    Config config;


    // --------------------------------------------------------
    // Load configuration
    // --------------------------------------------------------

    cout << "       Loading paths..." << endl;

    loadPaths(
        "../data/paths.csv",
        config);



    cout << "       Loading scoring weights..." << endl;

    loadWeights(
        "../data/overall_weights.csv",
        config);

    normalizeWeights(config);



    cout << endl;

    cout << "       Configuration:" << endl;

    cout << "          Buy Weight:       "
         << config.buyWeight
         << endl;

    cout << "          Intrinsic Weight: "
         << config.intrinsicWeight
         << endl;

        cout << "          Analyst Weight:   "
            << config.analystWeight
            << endl;

    cout << "          Consensus Bonus:  "
         << config.consensusMax
         << endl;

    cout << endl;

    // --------------------------------------------------------
    // Load Buy Opportunity Data
    // --------------------------------------------------------

    cout
    << "       Loading Buy Opportunity file..."
    << endl;


    auto stocks =
        loadBuyOpportunity(
            config.buyFile);



    cout
    << "       Loaded "
    << stocks.size()
    << " buy opportunity stocks"
    << endl;



    // --------------------------------------------------------
    // Load Intrinsic Value Data
    // --------------------------------------------------------

    cout
    << "       Loading Intrinsic Value file..."
    << endl;


    loadIntrinsicValue(
        config.intrinsicFile,
        stocks);



    cout
    << "       Combined universe: "
    << stocks.size()
    << " stocks"
    << endl;


    // --------------------------------------------------------
    // Load Analyst Ratings
    // --------------------------------------------------------

    cout
    << "       Loading Analyst Ratings file..."
    << endl;

    loadAnalystRatings(
        config,
        stocks);



    // --------------------------------------------------------
    // Calculate Scores
    // --------------------------------------------------------

    cout << endl;

    cout
    << "       Calculating scores..."
    << endl;


    calculateScores(
        stocks,
        config);

    // --------------------------------------------------------
    // Write Output
    // --------------------------------------------------------

    cout
    << "       Writing report..."
    << endl;

    writeReport(
        config.outputFile,
        stocks);
    cout << endl;

    cout << "       ==========================================" 
         << endl;

    cout << "       Complete, "
         << " Output: "
         << config.outputFile
         << endl;

    cout << "       ==========================================" 
         << endl;
         return 0;
}