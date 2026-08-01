#include "metadata.hpp"
#include <fstream>
#include <sstream>
#include <algorithm>
#include <string>

std::string get_csv_field(std::stringstream& ss) {
    std::string field;
    if(ss.peek() == '"') {
        ss.get(); // Skip opening quote
        std::getline(ss,field,'"');
        if(ss.peek() == ',') ss.get(); // Skip comma after closing quote
    } else {
        std::getline(ss,field,',');
    }
    field.erase( std::remove(field.begin(),field.end(),'\r'), field.end() );
    field.erase( std::remove(field.begin(),field.end(),'\n'), field.end() );
    return field;
}

std::unordered_map<std::string,Metadata> load_metadata(const std::string& file) {
    std::ifstream in(file);
    if(!in) return {};
    
    // Count data rows (skip header)
    size_t count = 0;
    std::string line;
    getline(in,line);
    while(getline(in,line)) {
        if(!line.empty()) count++;
    }
    in.clear();
    in.seekg(0);
    
    std::unordered_map<std::string,Metadata> data;
    // Reserve space in the unordered_map to avoid rehashing
    data.reserve(count);
    
    getline(in,line); // header
    while(getline(in,line)) {
        std::stringstream ss(line);
        std::string ticker = get_csv_field(ss);
        std::string company = get_csv_field(ss);
        std::string sector_str = get_csv_field(ss);
        
        if(!ticker.empty()) {
            int sector_code = 0;
            try {
                if(!sector_str.empty()) {
                    sector_code = std::stoi(sector_str);
                }
            } catch (...) {
                sector_code = 0; // Fallback for invalid or missing values
            }
            
            data[ticker] = {company, sector_code};
        }
    }
    return data;
}
