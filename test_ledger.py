from supabase import create_client, Client

# 1. Initialize the connection
url: str = "https://yivjlouxgoxecylwfudg.supabase.co"
key: str = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inlpdmpsb3V4Z294ZWN5bHdmdWRnIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4NDUzNDU3MSwiZXhwIjoyMTAwMTEwNTcxfQ.9onKZ7-nICizXjvaK4HnTZVnqOJ4bDMaKHdiXrg1ad8".strip()

supabase: Client = create_client(url, key)

print("Attempting to connect to Supabase...")

# 2. Insert a dummy record into Table 1 (market_context)
context_data = {
    "okx_close_price": 0.00451234,
    "xgboost_regime": "Trending Up (Test)",
    "chronos_macro_trend": "Bullish Continuation",
    "kronos_volatility_warning": False
}

context_response = supabase.table("market_context").insert(context_data).execute()
generated_context_id = context_response.data[0]["id"]
print(f"✅ Success! Inserted Market Context with ID: {generated_context_id}")

# 3. Insert a dummy record into Table 2 (trade_executions) welded to Table 1
trade_data = {
    "market_context_id": generated_context_id,
    "strategy_used": "Momentum Breakout (Test)",
    "action": "BUY",
    "entry_price": 0.00451234,
    "capital_risked_aed": 10.00,
    "status": "OPEN"
}

trade_response = supabase.table("trade_executions").insert(trade_data).execute()
generated_trade_id = trade_response.data[0]["id"]

print(f"✅ Success! Inserted Trade Execution with ID: {generated_trade_id}")
print("🎉 Your Python-to-Supabase bridge is 100% operational!")