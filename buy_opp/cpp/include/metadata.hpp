#pragma once

#include <string>
#include <unordered_map>


struct Metadata{
  std::string company;
  std::string sector;
};


std::unordered_map<std::string,Metadata> load_metadata(const std::string& file);