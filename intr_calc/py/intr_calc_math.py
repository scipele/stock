def calculate_alphaspread_exact_dcf(
    base_owner_earnings,
    discount_rate,
    start_growth_rate,
    end_growth_rate,
    terminal_growth_rate,
    shares_outstanding,
    total_cash,
    total_debt,
    margin_of_safety,
):
    """
    Warren Buffett owner-earnings model.
    """
    future_values = []
    growth_rates = []
    present_values = []

    projection_years = 10
    previous_value = base_owner_earnings

    for year in range(1, projection_years + 1):
        if year == 1:
            growth_rate = start_growth_rate
        else:
            growth_rate = start_growth_rate - ((year / projection_years) * (start_growth_rate - end_growth_rate))
        growth_rates.append(growth_rate)

        previous_value *= (1 + growth_rate)
        future_values.append(previous_value)

        pv = previous_value / ((1 + discount_rate) ** year)
        present_values.append(pv)

    terminal_value = future_values[-1] * (1 + terminal_growth_rate) / (discount_rate - terminal_growth_rate)
    pv_terminal_value = terminal_value / ((1 + discount_rate) ** projection_years)

    sum_pv_projections = sum(present_values)
    corporate_value = sum_pv_projections + pv_terminal_value
    debt_value = abs(total_debt)
    equity_value = corporate_value + total_cash - debt_value
    intrinsic_value_per_share = equity_value / shares_outstanding if shares_outstanding > 0 else 0.0
    max_buy_price = intrinsic_value_per_share * (1 - margin_of_safety)

    return (
        future_values,
        growth_rates,
        future_values,
        present_values,
        pv_terminal_value,
        intrinsic_value_per_share,
        max_buy_price,
        sum_pv_projections,
        equity_value,
        corporate_value,
        terminal_value,
    )
