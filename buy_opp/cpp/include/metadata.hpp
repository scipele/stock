#ifndef METADATA_HPP
#define METADATA_HPP

#include <string>
#include <unordered_map>

struct Metadata {
    std::string company;
    int sector; // Changed from std::string to int
};

std::string get_csv_field(std::stringstream& ss);
std::unordered_map<std::string,Metadata> load_metadata(const std::string& file);

#endif
