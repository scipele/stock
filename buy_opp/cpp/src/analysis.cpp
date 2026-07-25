#include "../include/analysis.hpp"

#include <cmath>
#include <algorithm>


double calculate_rsi(
    const std::vector<double>& closes,
    int period)
{
    if (closes.size() <= period)
        return 50.0;

    double gain = 0.0;
    double loss = 0.0;

    for(size_t i = closes.size() - period;
        i < closes.size();
        i++)
    {
        double change = closes[i] - closes[i-1];
        if(change > 0)
            gain += change;
        else
            loss -= change;
    }

    double avg_gain = gain / period;
    double avg_loss = loss / period;

    if(avg_loss == 0) return 100.0;

    double rs = avg_gain / avg_loss;

    return 100.0 - (100.0 / (1.0 + rs));
}


double calculate_momentum(
    const std::vector<double>& closes,
    int days) {
    if(closes.size() <= days)
        return 0.0;

    double old_price = closes[closes.size()-days-1];
    double current = closes.back();

    return ((current / old_price)-1.0)*100.0;
}


double calculate_volatility(
    const std::vector<double>& closes,
    int period) {
    if(closes.size() < period) return 0.0;

    double sum = 0.0;

    for(size_t i = closes.size()-period;
        i < closes.size();
        i++)  {
        sum += closes[i];
    }

    double avg = sum / period;
    double variance = 0.0;

    for(size_t i = closes.size()-period;
        i < closes.size();
        i++) {
        double diff = closes[i]-avg;
        variance += diff*diff;
    }

    double stddev = sqrt(variance/period);

    return (stddev/avg)*100.0;
}


double find_swing_low( const std::vector<double>& lows) {
    if(lows.size()<10) return lows.back();

    // Search backwards for latest pivot low
    for(int i=lows.size()-3; i>=2; i--) {
        if(
            lows[i] < lows[i-1] &&
            lows[i] < lows[i-2] &&
            lows[i] < lows[i+1] &&
            lows[i] < lows[i+2]
          )
        {
            return lows[i];
        }
    }
    return
        *std::min_element(
            lows.end()-20,
            lows.end());
}


double find_swing_high( const std::vector<double>& highs) {

    if(highs.size()<10) return highs.back();


    for(int i=highs.size()-3; i>=2; i--) {
        if(
            highs[i] > highs[i-1] &&
            highs[i] > highs[i-2] &&
            highs[i] > highs[i+1] &&
            highs[i] > highs[i+2]
          )
        {
            return highs[i];
        }
    }

    return
        *std::max_element(
            highs.end()-20,
            highs.end());
}


TechnicalData analyze_prices(
    const std::vector<double>& closes,
    const std::vector<double>& highs,
    const std::vector<double>& lows)
{

    TechnicalData data;
    if(closes.empty()) return data;
    data.price = closes.back();

    if(lows.size()>1) data.previous_low = lows[lows.size()-2];
    if(highs.size()>1) data.previous_high = highs[highs.size()-2];
    data.swing_low = find_swing_low(lows);
    data.swing_high = find_swing_high(highs);

    if(data.previous_low>0) {
        data.distance_previous_low =
            ((data.price-data.previous_low)
             /data.previous_low)*100.0;
    }

    if(data.swing_low>0) {
        data.distance_swing_low =
            ((data.price-data.swing_low)
             /data.swing_low)*100.0;
    }

    data.rsi = calculate_rsi(closes);
    data.momentum_3m = calculate_momentum(closes);
    data.volatility = calculate_volatility(closes);

    return data;
}