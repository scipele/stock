#include "metadata.hpp"
#include <fstream>
#include <sstream>
#include <algorithm>

std::string clean_csv_field(std::string value)
{
    value.erase(std::remove(value.begin(),value.end(),'\r'),value.end());
    value.erase(std::remove(value.begin(),value.end(),'\n'),value.end());
    while(!value.empty() && value.front()=='"') value.erase(0,1);
    while(!value.empty() && value.back()=='"') value.pop_back();

    value.erase(std::remove(value.begin(),value.end(),'"'),value.end());
    return value;
}


std::unordered_map<std::string,Metadata> load_metadata(const std::string& file){

    std::unordered_map<std::string,Metadata> data;
    std::ifstream in(file);

    if(!in) return data;

    std::string line;
    getline(in,line); // header

    while(getline(in,line)){
        std::stringstream ss(line);
        std::string ticker;
        std::string company;
        std::string sector;

        getline(ss,ticker,',');
        getline(ss,company,',');

        getline(ss,sector,',');
        company=clean_csv_field(company);
        sector=clean_csv_field(sector);

        // sector.erase(
        //     std::remove(sector.begin(),sector.end(),'\r'),
        //     sector.end()
        // );

        // sector.erase(
        //     std::remove(sector.begin(),sector.end(),'\n'),
        //     sector.end()
        // );

        if(!ticker.empty()){
            data[ticker]={company,sector};
        }
    } return data;
}