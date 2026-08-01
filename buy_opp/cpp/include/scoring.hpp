#pragma once

#include "analysis.hpp"
#include "fundamentals.hpp"




struct ScoreResult
{
    double support_score = 0.0;
    double swing_score = 0.0;
    double pe_score = 0.0;
    double rsi_score = 0.0;
    double momentum_score = 0.0;
    double volatility_score = 0.0;
    double technical_score = 0.0;
    double fundamental_score = 0.0;
    double overall_score = 0.0;
};


ScoreResult calculate_score(
    const TechnicalData& technical,
    const FundamentalData& fundamental
);


// Individual scoring functions

double score_support_distance(
    double percent_distance
);


double score_pe(
    double pe
);


double score_rsi(
    double rsi
);


double score_momentum(
    double momentum
);


double score_volatility(
    double volatility
);