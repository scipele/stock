#include "scoring.hpp"

#include <algorithm>



double clamp_score(double value)
{
    return std::max(0.0,
           std::min(100.0,value));
}



//
// Price near previous day low
//
double score_support_distance(
    double distance)
{

    if(distance <= 0)
        return 100;


    if(distance <= 1)
        return 95;


    if(distance <= 2)
        return 85;


    if(distance <= 3)
        return 70;


    if(distance <= 5)
        return 45;


    if(distance <= 10)
        return 15;


    return 0;
}



//
// PE valuation
//
double score_pe(
    double pe)
{

    if(pe <= 0)
        return 0;


    if(pe >= 8 && pe <= 15)
        return 100;


    if(pe <= 20)
        return 90;


    if(pe <= 25)
        return 75;


    if(pe <= 35)
        return 55;


    if(pe <= 50)
        return 25;


    return 0;
}



//
// Oversold RSI is desirable
//
double score_rsi(
    double rsi)
{

    if(rsi >=20 && rsi <=30)
        return 100;


    if(rsi <=35)
        return 90;


    if(rsi <=45)
        return 70;


    if(rsi <=60)
        return 50;


    if(rsi <=70)
        return 25;


    return 0;
}



//
// Moderate positive momentum preferred
//
double score_momentum(
    double momentum)
{

    if(momentum >=5 &&
       momentum <=40)
        return 100;


    if(momentum >0 &&
       momentum <5)
        return 70;


    if(momentum >40 &&
       momentum <=80)
        return 50;


    if(momentum <0 &&
       momentum >=-15)
        return 40;


    return 10;
}



//
// Avoid extreme volatility
//
double score_volatility(
    double volatility)
{

    if(volatility >=10 &&
       volatility <=20)
        return 100;


    if(volatility <=30)
        return 75;


    if(volatility <=45)
        return 40;


    return 10;
}



ScoreResult calculate_score(
    const TechnicalData& t,
    const FundamentalData& f)
{

    ScoreResult result;



    //
    // Technical components
    //

    result.support_score =
        score_support_distance(
            t.distance_previous_low);



    result.swing_score =
        score_support_distance(
            t.distance_swing_low);



    result.rsi_score =
        score_rsi(
            t.rsi);



    result.momentum_score =
        score_momentum(
            t.momentum_3m);



    result.volatility_score =
        score_volatility(
            t.volatility);



    //
    // Use forward PE if available
    //
    double pe =
        f.forward_pe > 0 ?
        f.forward_pe :
        f.trailing_pe;


    result.pe_score =
        score_pe(pe);



    //
    // Technical subtotal
    //
    result.technical_score =
          result.swing_score      * 0.30
        + result.support_score    * 0.20
        + result.rsi_score        * 0.15
        + result.momentum_score   * 0.10
        + result.volatility_score * 0.05;



    //
    // Fundamental subtotal
    //
    result.fundamental_score =
        result.pe_score;



    //
    // Final score
    //
    result.overall_score =
          result.swing_score      * 0.30
        + result.support_score    * 0.20
        + result.pe_score         * 0.20
        + result.rsi_score        * 0.15
        + result.momentum_score   * 0.10
        + result.volatility_score * 0.05;



    return result;
}