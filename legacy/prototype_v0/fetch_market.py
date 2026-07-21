import os
from datetime import datetime, timezone

from dotenv import load_dotenv
from okx.MarketData import MarketAPI
from supabase import Client, create_client

from rl_optimizer import optimize_execution
from strategy_selector import select_trading_strategy
from xgboost_engine import (
    calculate_technical_indicators,
    fetch_historical_bars,
    get_live_regime_prediction,
)

# Historical prototype only. This module is quarantined and is not part of the
# reconstructed package or any supported execution path.
load_dotenv(".env.local")

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not url or not key:
    raise ValueError(
        "Missing credentials. The quarantined prototype must not be run from "
        "the public repository."
    )

supabase: Client = create_client(url.strip(), key.strip())


def fetch_and_log_market_data(trading_pair: str = "BTC-USDT"):
    print(f"Connecting to OKX to fetch live 15m candlesticks for {trading_pair}...")
    market_client = MarketAPI(flag="0")

    try:
        result = market_client.get_candlesticks(
            instId=trading_pair,
            bar="15m",
            limit="5",
        )

        if result and result.get("code") == "0":
            candles = result.get("data", [])
            latest_closed = candles[1]

            timestamp_ms = int(latest_closed[0])
            high_price = float(latest_closed[2])
            low_price = float(latest_closed[3])
            close_price = float(latest_closed[4])
            volume = float(latest_closed[5])

            dt_object = datetime.fromtimestamp(timestamp_ms / 1000.0, tz=timezone.utc)
            iso_timestamp = dt_object.strftime("%Y-%m-%d %H:%M:%S UTC")

            print(f"\nLatest Closed 15m Bar ({iso_timestamp})")
            print(f"Close Price: ${close_price:,.4f}")
            print(f"High / Low: ${high_price:,.4f} / ${low_price:,.4f}")
            print(f"Volume: {volume:,.2f}")

            live_regime, confidence = get_live_regime_prediction(trading_pair)

            df_hist = fetch_historical_bars(trading_pair, limit="100")
            df_hist = calculate_technical_indicators(df_hist)
            latest_tech = df_hist.iloc[-1]

            trade_plan = select_trading_strategy(
                regime=live_regime,
                close_price=close_price,
                rsi=float(latest_tech["rsi_14"]),
                bb_upper=float(latest_tech["bb_upper"]),
                bb_lower=float(latest_tech["bb_lower"]),
                ema_9=float(latest_tech["ema_9"]),
                ema_21=float(latest_tech["ema_21"]),
            )

            final_action, capital_risked_aed, sniper_entry, rl_state_key = (
                optimize_execution(
                    regime=live_regime,
                    trade_plan=trade_plan,
                    confidence=confidence,
                    bb_width=float(latest_tech["bb_width"]),
                    max_budget_aed=10.00,
                )
            )

            context_payload = {
                "okx_close_price": close_price,
                "xgboost_regime": f"{live_regime} ({confidence:.1f}%)",
                "chronos_macro_trend": "Awaiting Model Integration",
                "kronos_volatility_warning": False,
            }
            context_response = (
                supabase.table("market_context").insert(context_payload).execute()
            )
            generated_context_id = context_response.data[0]["id"]

            execution_payload = {
                "market_context_id": generated_context_id,
                "strategy_used": f"{trade_plan['strategy_name']} [{rl_state_key}]",
                "action": final_action,
                "entry_price": sniper_entry,
                "capital_risked_aed": capital_risked_aed,
                "status": (
                    "OPEN"
                    if final_action in ["BUY_DIP", "BUY_MOMENTUM", "SELL_PEAK"]
                    else "HOLDING"
                ),
            }
            trade_response = (
                supabase.table("trade_executions").insert(execution_payload).execute()
            )
            generated_trade_id = trade_response.data[0]["id"]

            return {
                "context_id": generated_context_id,
                "trade_id": generated_trade_id,
                "plan": trade_plan,
                "rl_allocation_aed": capital_risked_aed,
            }

        print(f"OKX API Error: {result.get('msg')}")
        return None
    except Exception as exc:
        print(f"Execution failed: {exc}")
        return None


if __name__ == "__main__":
    fetch_and_log_market_data("BTC-USDT")
