def select_trading_strategy(
    regime: str,
    close_price: float,
    rsi: float,
    bb_upper: float,
    bb_lower: float,
    ema_9: float,
    ema_21: float,
):
    """Historical Version 0 rules retained for regression analysis only."""
    regime_clean = regime.split(" ")[0].strip()

    strategy_plan = {
        "strategy_name": "No Strategy Selected",
        "action": "HOLD",
        "target_entry": close_price,
        "take_profit": close_price,
        "stop_loss": close_price,
        "risk_reward_ratio": "0:0",
        "reasoning": "Awaiting clear market structure.",
    }

    if regime_clean == "Ranging":
        target_entry = bb_lower
        take_profit = bb_upper
        stop_loss = bb_lower * 0.995
        potential_reward = take_profit - target_entry
        potential_risk = target_entry - stop_loss
        rr_ratio = potential_reward / potential_risk if potential_risk > 0 else 1.0

        if close_price <= bb_lower * 1.003:
            action = "BUY_DIP"
            reasoning = "Price is near Lower Bollinger Band support."
        elif close_price >= bb_upper * 0.997:
            action = "SELL_PEAK"
            reasoning = "Price is testing Upper Bollinger Band resistance."
        else:
            action = "HOLD_WAIT"
            reasoning = (
                f"Price is mid-range (RSI {rsi:.1f}). Waiting for pullback."
            )

        strategy_plan = {
            "strategy_name": "Mean Reversion (Bollinger Bounce)",
            "action": action,
            "target_entry": round(target_entry, 4),
            "take_profit": round(take_profit, 4),
            "stop_loss": round(stop_loss, 4),
            "risk_reward_ratio": f"1:{rr_ratio:.1f}",
            "reasoning": reasoning,
        }

    elif regime_clean == "Trending" or regime_clean == "Trending Up":
        take_profit = close_price * 1.015
        stop_loss = ema_21 * 0.998
        potential_reward = take_profit - close_price
        potential_risk = close_price - stop_loss
        rr_ratio = potential_reward / potential_risk if potential_risk > 0 else 1.0

        if rsi < 68.0:
            action = "BUY_MOMENTUM"
            reasoning = "Uptrend classified; buying momentum."
        else:
            action = "HOLD_WAIT"
            reasoning = f"RSI ({rsi:.1f}) is overbought."

        strategy_plan = {
            "strategy_name": "Momentum Breakout (Trend Rider)",
            "action": action,
            "target_entry": round(close_price, 4),
            "take_profit": round(take_profit, 4),
            "stop_loss": round(stop_loss, 4),
            "risk_reward_ratio": f"1:{rr_ratio:.1f}",
            "reasoning": reasoning,
        }

    elif regime_clean == "Trending Down":
        strategy_plan = {
            "strategy_name": "Capital Preservation (Defensive)",
            "action": "HOLD_CASH",
            "target_entry": 0.0,
            "take_profit": 0.0,
            "stop_loss": 0.0,
            "risk_reward_ratio": "0:0",
            "reasoning": "Market classified as Trending Down.",
        }

    return strategy_plan
