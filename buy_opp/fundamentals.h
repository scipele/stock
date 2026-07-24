#pragma once

#include <string>
#include <unordered_map>


struct FundamentalData
{
    double forward_pe = 0.0;
    double trailing_pe = 0.0;
};



class FundamentalsDB
{

private:

    std::unordered_map<std::string, FundamentalData> data;


public:

    bool load(
        const std::string& filename
    );


    FundamentalData get(
        const std::string& ticker
    ) const;

};