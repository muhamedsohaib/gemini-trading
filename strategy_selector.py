import pandas as pd
import numpy as np

def select_trading_strategy(regime: str, close_price: float, rsi: float, bb_upper: float, bb_lower: float, ema_9: float, ema_21: float):
    """
    Layer 4: Rule-Based Strategy Selector
    Takes the XGBoost market regime and live technical indicators to lock in a tactical trade plan.
    """
    
    # Clean the regime string in case it contains confidence percentages (e.g., "Ranging (67.4%)")
    regime_clean = regime.split(" ")[0].strip()
    
    strategy_plan = {
        "strategy_name": "No Strategy Selected",
        "action": "HOLD",
        "target_entry": close_price,
        "take_profit": close_price,
        "stop_loss": close_price,
        "risk_reward_ratio": "0:0",
        "reasoning": "Awaiting clear market structure."
    }
    
    # ==========================================
    # 1. SIDEWAYS / RANGING PLAYBOOK (Mean Reversion)
    # ==========================================
    if regime_clean == "Ranging":
        # In a ranging market, we buy the dip at the lower Bollinger Band and sell at the upper band
        target_entry = bb_lower
        take_profit = bb_upper
        
        # Stop loss is placed 0.5% below the lower band in case the range breaks down
        stop_loss = bb_lower * 0.995
        
        # Calculate risk/reward
        potential_reward = take_profit - target_entry
        potential_risk = target_entry - stop_loss
        rr_ratio = potential_reward / potential_risk if potential_risk > 0 else 1.0
        
        # Decide action based on current price proximity to support
        if close_price <= (bb_lower * 1.003):  # Price is within 0.3% of lower support
            action = "BUY_DIP"
            reasoning = f"Price (${close_price:,.2f}) is near Lower Bollinger Band support. Triggering Mean Reversion buy."
        elif close_price >= (bb_upper * 0.997): # Price is near upper resistance
            action = "SELL_PEAK"
            reasoning = f"Price (${close_price:,.2f}) is testing Upper Bollinger Band resistance. Take profit zone."
        else:
            action = "HOLD_WAIT"
            reasoning = f"Price is mid-range (RSI {rsi:.1f}). Waiting for pullback to entry target (${target_entry:,.2f})."
            
        strategy_plan = {
            "strategy_name": "Mean Reversion (Bollinger Bounce)",
            "action": action,
            "target_entry": round(target_entry, 4),
            "take_profit": round(take_profit, 4),
            "stop_loss": round(stop_loss, 4),
            "risk_reward_ratio": f"1:{rr_ratio:.1f}",
            "reasoning": reasoning
        }
        
    # ==========================================
    # 2. UPTREND PLAYBOOK (Momentum Breakout)
    # ==========================================
    elif regime_clean == "Trending" or regime_clean == "Trending Up":
        # In an uptrend, we ride momentum using the 9-period EMA as dynamic support
        target_entry = ema_9
        take_profit = close_price * 1.015  # Aim for a 1.5% intraday momentum push
        stop_loss = ema_21 * 0.998         # Stop out if price breaks below the 21-period EMA trendline
        
        potential_reward = take_profit - close_price
        potential_risk = close_price - stop_loss
        rr_ratio = potential_reward / potential_risk if potential_risk > 0 else 1.0
        
        if rsi < 68.0: # Ensure we aren't buying at the exact top of an exhausted spike
            action = "BUY_MOMENTUM"
            reasoning = f"Uptrend confirmed (EMA Crossover positive). Buying breakout momentum with trail stop at EMA 21."
        else:
            action = "HOLD_WAIT"
            reasoning = f"Uptrend strong but RSI ({rsi:.1f}) is overbought. Waiting for minor consolidation before entry."
            
        strategy_plan = {
            "strategy_name": "Momentum Breakout (Trend Rider)",
            "action": action,
            "target_entry": round(close_price, 4), # Immediate market entry on trend confirmation
            "take_profit": round(take_profit, 4),
            "stop_loss": round(stop_loss, 4),
            "risk_reward_ratio": f"1:{rr_ratio:.1f}",
            "reasoning": reasoning
        }
        
    # ==========================================
    # 3. DOWNTREND PLAYBOOK (Capital Preservation)
    # ==========================================
    elif regime_clean == "Trending Down":
        strategy_plan = {
            "strategy_name": "Capital Preservation (Defensive)",
            "action": "HOLD_CASH",
            "target_entry": 0.0,
            "take_profit": 0.0,
            "stop_loss": 0.0,
            "risk_reward_ratio": "0:0",
            "reasoning": "Market classified as Trending Down. Guardrail activated: 100 AED capital protected in cash."
        }
        
    print(f"\n📋 --- Layer 4 Strategy Playbook Selected ---")
    print(f"   • Strategy Name : {strategy_plan['strategy_name']}")
    print(f"   • Action Signal : [{strategy_plan['action']}]")
    print(f"   • Entry Target  : ${strategy_plan['target_entry']:,.4f}")
    print(f"   • Profit / Stop : ${strategy_plan['take_profit']:,.4f} / ${strategy_plan['stop_loss']:,.4f} ({strategy_plan['risk_reward_ratio']} R:R)")
    print(f"   • Logic         : {strategy_plan['reasoning']}")
    
    return strategy_plan

if __name__ == "__main__":
    # Test simulation with your exact live Bitcoin data from Row ID 4!
    select_trading_strategy(
        regime="Ranging", 
        close_price=64471.0000, 
        rsi=51.98, 
        bb_upper=64850.0000, 
        bb_lower=64090.0000, 
        ema_9=64450.0000, 
        ema_21=64400.0000
    )