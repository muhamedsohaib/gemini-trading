import os
from datetime import datetime, timezone
from dotenv import load_dotenv
from okx.MarketData import MarketAPI
from supabase import create_client, Client
import pandas as pd
import numpy as np

# 1. IMPORT YOUR AI, STRATEGY, AND RL ENGINES
from xgboost_engine import get_live_regime_prediction, fetch_historical_bars, calculate_technical_indicators
from strategy_selector import select_trading_strategy
from rl_optimizer import optimize_execution

# ==========================================
# 2. SUPABASE CONNECTION (Loaded from .env.local)
# ==========================================
load_dotenv(".env.local")

url: str = os.getenv("SUPABASE_URL")
key: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not url or not key:
    raise ValueError("❌ Missing credentials! Check that SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are defined in your .env.local file.")

supabase: Client = create_client(url.strip(), key.strip())

def fetch_and_log_market_data(trading_pair="BTC-USDT"):
    print(f"📡 Connecting to OKX to fetch live 15m candlesticks for {trading_pair}...")
    
    # flag="0" specifies the live OKX production mainnet
    market_client = MarketAPI(flag="0")
    
    try:
        # Pull the last 5 periods of 15-minute candlestick data
        result = market_client.get_candlesticks(
            instId=trading_pair,
            bar="15m",
            limit="5"
        )
        
        if result and result.get("code") == "0":
            candles = result.get("data", [])
            
            # Index [1] = The last fully completed, closed candle
            latest_closed = candles[1]
            
            timestamp_ms = int(latest_closed[0])
            open_price = float(latest_closed[1])
            high_price = float(latest_closed[2])
            low_price = float(latest_closed[3])
            close_price = float(latest_closed[4])
            volume = float(latest_closed[5])
            
            dt_object = datetime.fromtimestamp(timestamp_ms / 1000.0, tz=timezone.utc)
            iso_timestamp = dt_object.strftime('%Y-%m-%d %H:%M:%S UTC')
            
            print(f"\n📊 --- Latest Closed 15m Bar ({iso_timestamp}) ---")
            print(f"   • Close Price : ${close_price:,.4f}")
            print(f"   • High / Low  : ${high_price:,.4f} / ${low_price:,.4f}")
            print(f"   • Volume      : {volume:,.2f}")
            
            # ==========================================
            # 3. RUN LAYER 3: XGBOOST REGIME CLASSIFIER
            # ==========================================
            print("\n🧠 Triggering XGBoost Layer 3 Regime Classifier...")
            live_regime, confidence = get_live_regime_prediction(trading_pair)
            
            # Extract live technical indicators for Strategy & RL math
            df_hist = fetch_historical_bars(trading_pair, limit="100")
            df_hist = calculate_technical_indicators(df_hist)
            latest_tech = df_hist.iloc[-1]
            
            rsi_val = float(latest_tech["rsi_14"])
            bb_up_val = float(latest_tech["bb_upper"])
            bb_low_val = float(latest_tech["bb_lower"])
            ema_9_val = float(latest_tech["ema_9"])
            ema_21_val = float(latest_tech["ema_21"])
            bb_width_val = float(latest_tech["bb_width"])
            
            # ==========================================
            # 4. RUN LAYER 4: STRATEGY SELECTOR
            # ==========================================
            print("\n⚙️ Triggering Layer 4 Strategy Playbook...")
            trade_plan = select_trading_strategy(
                regime=live_regime,
                close_price=close_price,
                rsi=rsi_val,
                bb_upper=bb_up_val,
                bb_lower=bb_low_val,
                ema_9=ema_9_val,
                ema_21=ema_21_val
            )
            
            # ==========================================
            # 5. RUN LAYER 5: RL ACTION OPTIMIZER
            # ==========================================
            print("\n🤖 Triggering Layer 5 Reinforcement Learning Action Optimizer...")
            final_action, capital_risked_aed, sniper_entry, rl_state_key = optimize_execution(
                regime=live_regime,
                trade_plan=trade_plan,
                confidence=confidence,
                bb_width=bb_width_val,
                max_budget_aed=10.00 # Max risk per trade from your 100 AED account budget
            )
            
            # ==========================================
            # 6. LOG TO SUPABASE LEDGER (Relational Weld)
            # ==========================================
            context_payload = {
                "okx_close_price": close_price,
                "xgboost_regime": f"{live_regime} ({confidence:.1f}%)",
                "chronos_macro_trend": "Awaiting Model Integration",
                "kronos_volatility_warning": False
            }
            
            print("\n💾 Pushing live AI context to 'market_context' table...")
            context_response = supabase.table("market_context").insert(context_payload).execute()
            generated_context_id = context_response.data[0]["id"]
            print(f"✅ Success! Context logged with Row ID: {generated_context_id}")
            
            # Weld the Layer 5 RL Decision and Strategy to the Context Row!
            execution_payload = {
                "market_context_id": generated_context_id,
                "strategy_used": f"{trade_plan['strategy_name']} [{rl_state_key}]",
                "action": final_action,
                "entry_price": sniper_entry,
                "capital_risked_aed": capital_risked_aed, # Perfectly calculated by Layer 5 RL Agent!
                "status": "OPEN" if final_action in ["BUY_DIP", "BUY_MOMENTUM", "SELL_PEAK"] else "HOLDING"
            }
            
            print("💾 Pushing strategy decision to 'trade_executions' table...")
            trade_response = supabase.table("trade_executions").insert(execution_payload).execute()
            generated_trade_id = trade_response.data[0]["id"]
            print(f"✅ Success! Fully Optimized Execution Plan logged with Trade ID: {generated_trade_id}")
            
            return {
                "context_id": generated_context_id,
                "trade_id": generated_trade_id,
                "plan": trade_plan,
                "rl_allocation_aed": capital_risked_aed
            }
            
        else:
            print(f"❌ OKX API Error: {result.get('msg')}")
            return None
            
    except Exception as e:
        print(f"❌ Execution failed: {str(e)}")
        return None

if __name__ == "__main__":
    fetch_and_log_market_data("BTC-USDT")