/*
Compile in linux with 
g++ -std=c++17 sect_owned.cpp -o sect_owned
*/
#include <iostream>
#include <filesystem>
#include <string>
#include <map>
#include <fstream>
#include <vector>
#include <sstream>

// Properly initialized map with curly braces and assignment operator
std::map<int, std::string> sectorMap = {
    {1, "Basic Materials"},
    {2, "Communication Services"},
    {3, "Consumer Cyclical"},
    {4, "Consumer Defensive"},
    {5, "Energy"},
    {6, "Financial Services"},
    {7, "Healthcare"},
    {8, "Industrials"},
    {9, "Real Estate"},
    {10, "Technology"},
    {11, "Utilities"}
};

int main() {

    std::filesystem::path csv_path = "/home/dev/stock/intr_buy/output/combined_report.csv";
    std::ifstream csv_file(csv_path);
    
    if (!csv_file.is_open()) {
        std::cerr << "Failed to open file " << csv_path << std::endl;
        return 1;
    }

    std::vector<int> sectors_owned(13, 0); 
    std::string line;

    while (std::getline(csv_file, line)) {
        std::stringstream ss(line);
        std::string cell;
        int column_index = 0;
        int sector = 0;
        bool is_cp = false;

        // skip the header row
        if (line.find("Rank") != std::string::npos) {
            continue;
        }

        // Added the ',' delimiter to read individual CSV cells
        while (std::getline(ss, cell, ',')) {
            column_index++;
            
            // Replaced single assignments (=) with comparison operators (==)
            if (column_index == 4) {
                // Wrapped std::stoi in a try-catch if your CSV header contains text
                try {
                    sector = std::stoi(cell);
                } catch (...) {
                    sector = 0; // Skip header row or invalid numbers
                }
            }
            if (column_index == 5 && cell == "CP") {
                is_cp = true;
            }
        }
        
        // Fixed the array assignment to increment the count
        if (is_cp && sector >= 1 && sector <= 12) {
            sectors_owned[sector]++;
        }
    }

    // Fixed loop termination and added clean formatting

    std::cout << "+-------------------------------+-------+\n"
              << "| Sectors Owned                 | Count |\n"
              << "+-------------------------------+-------+\n";

    for (int i = 1; i <= 12; i++) {
        //how can i format the output to align the text in the first column and the numbers in the second column?
        std::cout << "| " << std::left << std::setw(30) << sectorMap[i]
                  << "| " << std::right << std::setw(5) << sectors_owned[i] << " |\n";  
    }
    std::cout << "+-------------------------------+-------+" << std::endl;

    return 0;
}
