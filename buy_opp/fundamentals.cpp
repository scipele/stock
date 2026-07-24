#include "fundamentals.h"

#include <fstream>
#include <sstream>
#include <iostream>



bool FundamentalsDB::load(
    const std::string& filename)
{

    std::ifstream file(filename);


    if(!file.is_open())
    {
        std::cerr
            << "Unable to open "
            << filename
            << "\n";

        return false;
    }



    std::string line;


    // Skip header
    std::getline(
        file,
        line
    );



    while(std::getline(file,line))
    {

        if(line.empty())
            continue;


        std::stringstream ss(line);


        std::string ticker;
        std::string forward;
        std::string trailing;



        std::getline(
            ss,
            ticker,
            ','
        );


        std::getline(
            ss,
            forward,
            ','
        );


        std::getline(
            ss,
            trailing,
            ','
        );



        FundamentalData f;


        try
        {
            f.forward_pe =
                std::stod(forward);


            f.trailing_pe =
                std::stod(trailing);
        }
        catch(...)
        {
            continue;
        }



        data[ticker] = f;
    }



    std::cout
        << "Loaded "
        << data.size()
        << " fundamentals\n";


    return true;
}





FundamentalData FundamentalsDB::get(
    const std::string& ticker) const
{

    auto it =
        data.find(ticker);



    if(it != data.end())
        return it->second;



    return FundamentalData{};
}