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

using namespace std;


// ============================================================
// Configuration
// ============================================================

struct Config
{
    string buyFile;
    string intrinsicFile;
    string outputFile;

    double buyWeight = 0.65;
    double intrinsicWeight = 0.35;

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

    bool owned = false;


    // Final scores
    double combinedScore = 0;
    double buyScore = 0;
    double intrinsicScore = 0;
    double consensusBonus = 0;


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


        if(cols[0] == "BuyOpportunityWeight")
            config.buyWeight = value;


        else if(cols[0] == "IntrinsicWeight")
            config.intrinsicWeight = value;


        else if(cols[0] == "ConsensusBonusMax")
            config.consensusMax = value;


        else if(cols[0] == "ConsensusPenaltyPerDifference")
            config.consensusPenalty = value;
    }
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


        Stock s;


        s.ticker = cols[2];
        s.company = cols[3];

        s.sector = toInt(cols[4]);


        // Owned column
        if(!cols[1].empty())
            s.owned = true;


        s.buyScore = toDouble(cols[5]);

        s.price = toDouble(cols[6]);


        s.rsi = toDouble(cols[11]);

        s.forwardPE = toDouble(cols[12]);
        s.trailingPE = toDouble(cols[13]);


        s.momentum = toDouble(cols[14]);
        s.volatility = toDouble(cols[15]);


        s.swingScore =
            toDouble(cols[16]);

        s.supportScore =
            toDouble(cols[17]);

        s.peScore =
            toDouble(cols[18]);

        s.rsiScore =
            toDouble(cols[19]);

        s.momentumScore =
            toDouble(cols[20]);

        s.volatilityScore =
            toDouble(cols[21]);


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


        string ticker = cols[1];


        // Creates a new record if ticker was
        // only found in intrinsic file
        Stock& s = stocks[ticker];


        s.ticker = ticker;


        s.company = cols[2];


        s.sector = toInt(cols[3]);


        s.price =
            toDouble(cols[4]);


        s.intrinsicValue =
            toDouble(cols[5]);


        s.marginSafety =
            toDouble(cols[6]);


        s.upside =
            toDouble(cols[7]);


        s.growthRate =
            toDouble(cols[8]);


        s.wacc =
            toDouble(cols[9]);


        s.forwardPE =
            toDouble(cols[14]);


        s.trailingPE =
            toDouble(cols[15]);


        s.dataQuality =
            cols[16];
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

            s.consensusBonus;



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
    << "Owned,"
    << "CombinedScore,"
    << "BuyScore,"
    << "IntrinsicScore,"
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
        << (s.owned ? "CP" : "") << ","

        << s.combinedScore << ","
        << s.buyScore << ","
        << s.intrinsicScore << ","
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
    << "   Created "
    << filename
    << " ("
    << list.size()
    << "    stocks)"
    << endl;
}


// ============================================================
// Main Program
// ============================================================

int main()
{

    cout << endl;
    cout << "   ==========================================" << endl;
    cout << "    Intrinsic + Buy Opportunity Analyzer" << endl;
    cout << "   ==========================================" << endl;
    cout << endl;


    Config config;


    // --------------------------------------------------------
    // Load configuration
    // --------------------------------------------------------

    cout << "   Loading paths..." << endl;

    loadPaths(
        "../data/paths.csv",
        config);



    cout << "   Loading scoring weights..." << endl;

    loadWeights(
        "../data/overall_weights.csv",
        config);



    cout << endl;

    cout << "Configuration:" << endl;

    cout << "  Buy Weight:       "
         << config.buyWeight
         << endl;

    cout << "  Intrinsic Weight: "
         << config.intrinsicWeight
         << endl;

    cout << "  Consensus Bonus:  "
         << config.consensusMax
         << endl;


    cout << endl;



    // --------------------------------------------------------
    // Load Buy Opportunity Data
    // --------------------------------------------------------

    cout
    << "   Loading Buy Opportunity file..."
    << endl;


    auto stocks =
        loadBuyOpportunity(
            config.buyFile);



    cout
    << "   Loaded "
    << stocks.size()
    << " buy opportunity stocks"
    << endl;



    // --------------------------------------------------------
    // Load Intrinsic Value Data
    // --------------------------------------------------------

    cout
    << "   Loading Intrinsic Value file..."
    << endl;


    loadIntrinsicValue(
        config.intrinsicFile,
        stocks);



    cout
    << "   Combined universe: "
    << stocks.size()
    << " stocks"
    << endl;



    // --------------------------------------------------------
    // Calculate Scores
    // --------------------------------------------------------

    cout << endl;

    cout
    << "   Calculating scores..."
    << endl;


    calculateScores(
        stocks,
        config);



    // --------------------------------------------------------
    // Write Output
    // --------------------------------------------------------

    cout
    << "   Writing report..."
    << endl;


    writeReport(
        config.outputFile,
        stocks);



    cout << endl;

    cout
    << "   ==========================================" 
    << endl;

    cout
    << "   Complete"
    << endl;

    cout
    << "    Output: "
    << config.outputFile
    << endl;

    cout
    << "   ==========================================" 
    << endl;


    return 0;
}