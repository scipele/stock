#include "metadata.hpp"
#include <fstream>
#include <sstream>
#include <algorithm>
#include <string>

namespace {
int parse_int_or_default(const std::string& value, int default_value)
{
    if(value.empty())
        return default_value;

    try
    {
        return std::stoi(value);
    }
    catch(...)
    {
        return default_value;
    }
}
}

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
        std::string exch_str = get_csv_field(ss);
        std::string index_str = get_csv_field(ss);
        
        if(!ticker.empty()) {
            int sector_code = parse_int_or_default(sector_str, 0);
            int exch_code = parse_int_or_default(exch_str, 4);
            int index_code = parse_int_or_default(index_str, 0);
            
            data[ticker] = {company, sector_code, exch_code, index_code};
        }
    }
    return data;
}
