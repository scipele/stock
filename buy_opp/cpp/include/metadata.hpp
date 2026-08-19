#ifndef METADATA_HPP
#define METADATA_HPP

#include <string>
#include <sstream>
#include <unordered_map>

struct Metadata {
    std::string company;
    int sector = 0;
    int exch = 4;
    int index = 0;
};

std::string get_csv_field(std::stringstream& ss);
std::unordered_map<std::string,Metadata> load_metadata(const std::string& file);

#endif
