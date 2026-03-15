def calculate_margin(client_budget: float) -> tuple[float, float]:
    """
    Calculates the 15% platform margin.
    Returns (editor_payout, platform_profit)
    """
    profit = client_budget * 0.15
    editor_payout = client_budget - profit
    return round(editor_payout, 2), round(profit, 2)
