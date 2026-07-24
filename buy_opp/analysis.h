#pragma once

#include <vector>


struct TechnicalData
{
    double price = 0.0;

    double previous_low = 0.0;
    double previous_high = 0.0;

    double swing_low = 0.0;
    double swing_high = 0.0;

    double distance_previous_low = 0.0;
    double distance_swing_low = 0.0;

    double rsi = 50.0;

    double momentum_3m = 0.0;

    double volatility = 0.0;
};


// Main analysis function
TechnicalData analyze_prices(
    const std::vector<double>& closes,
    const std::vector<double>& highs,
    const std::vector<double>& lows
);


// Individual calculations

double calculate_rsi(
    const std::vector<double>& closes,
    int period = 14
);


double calculate_momentum(
    const std::vector<double>& closes,
    int days = 63
);


double calculate_volatility(
    const std::vector<double>& closes,
    int period = 20
);


double find_swing_low(
    const std::vector<double>& lows
);


double find_swing_high(
    const std::vector<double>& highs
);