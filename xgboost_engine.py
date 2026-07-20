import numpy as np
import pandas as pd
from okx.MarketData import MarketAPI
from xgboost import XGBClassifier

def fetch_historical_bars(trading_pair="BTC-USDT", limit="100"):
    """Fetches historical 15m candles from OKX to build our feature matrix."""
    market_client = MarketAPI(flag="0")
    result = market_client.get_candlesticks(instId=trading_pair, bar="15m", limit=limit)
    
    if not result or result.get("code") != "0":
        raise Exception(f"Failed to fetch data from OKX: {result.get('msg')}")
        
    candles = result.get("data", [])
    
    # OKX returns newest-to-oldest. We reverse it to oldest-to-newest for chronological math
    candles.reverse()
    
    # Structure into a Pandas DataFrame
    df = pd.DataFrame(candles, columns=["timestamp", "open", "high", "low", "close", "volume", "volCcy", "volCcyQuote", "confirm"])
    
    # Convert numerical columns from strings to floats
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = df[col].astype(float)
        
    return df

def calculate_technical_indicators(df):
    """Calculates RSI, Bollinger Bands, and Exponential Moving Averages (EMA)."""
    
    # 1. Exponential Moving Averages (EMA 9 and EMA 21 for trend momentum)
    df["ema_9"] = df["close"].ewm(span=9, adjust=False).mean()
    df["ema_21"] = df["close"].ewm(span=21, adjust=False).mean()
    df["ema_crossover"] = df["ema_9"] - df["ema_21"]
    
    # 2. Relative Strength Index (RSI - 14 period)
    delta = df["close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss.replace(0, np.nan)  # Prevent division by zero
    df["rsi_14"] = 100 - (100 / (1 + rs))
    df["rsi_14"] = df["rsi_14"].fillna(50) # Default neutral if undefined
    
    # 3. Bollinger Bands (20 period, 2 Standard Deviations)
    df["sma_20"] = df["close"].rolling(window=20).mean()
    df["std_20"] = df["close"].rolling(window=20).std()
    df["bb_upper"] = df["sma_20"] + (df["std_20"] * 2)
    df["bb_lower"] = df["sma_20"] - (df["std_20"] * 2)
    
    # Normalized Bandwidth (Measures market volatility compression)
    df["bb_width"] = (df["bb_upper"] - df["bb_lower"]) / df["sma_20"]
    
    return df

def label_market_regimes(df, trend_threshold=0.004):
    """
    Supervised Labeling: Looks 3 candles into the future (45 mins) to define ground truth.
    Class 1: Trending Up   (Future price gained > +0.4%)
    Class 2: Trending Down (Future price lost > -0.4%)
    Class 0: Ranging       (Price stayed within +/- 0.4%)
    """
    # Calculate percentage change 3 periods ahead
    future_return = df["close"].shift(-3) / df["close"] - 1
    
    conditions = [
        (future_return > trend_threshold),
        (future_return < -trend_threshold)
    ]
    choices = [1, 2] # 1 = Trending Up, 2 = Trending Down
    
    # Default to 0 (Ranging) if neither condition is met
    df["target_regime"] = np.select(conditions, choices, default=0)
    
    return df

def get_live_regime_prediction(trading_pair="BTC-USDT"):
    print(f"🧠 Computing XGBoost Feature Matrix for {trading_pair}...")
    
    # 1. Prepare Data
    df = fetch_historical_bars(trading_pair, limit="100")
    df = calculate_technical_indicators(df)
    df = label_market_regimes(df)
    
    # Drop rows with NaN values caused by rolling windows (e.g., first 20 rows for Bollinger Bands)
    df_clean = df.dropna().copy()
    
    # Define our feature vectors
    features = ["rsi_14", "ema_crossover", "bb_width"]
    
    # 2. Split into Training Data (all closed candles except the very latest one)
    X_train = df_clean[features].iloc[:-1]
    y_train = df_clean["target_regime"].iloc[:-1]
    
    # The latest closed candle that we want to classify right now
    X_live = df_clean[features].iloc[[-1]]
    
    # 3. Train the XGBoost Classifier
    model = XGBClassifier(
        n_estimators=50,
        learning_rate=0.05,
        max_depth=3,
        random_state=42,
        eval_metric="mlogloss"
    )
    model.fit(X_train, y_train)
    
    # 4. Predict Live Regime
    prediction = model.predict(X_live)[0]
    probabilities = model.predict_proba(X_live)[0]
    confidence = probabilities[prediction] * 100
    
    regime_map = {0: "Ranging", 1: "Trending Up", 2: "Trending Down"}
    predicted_label = regime_map[prediction]
    
    print(f"📈 --- XGBoost Inference Complete ---")
    print(f"   • RSI (14)      : {X_live['rsi_14'].values[0]:.2f}")
    print(f"   • EMA Crossover : {X_live['ema_crossover'].values[0]:.2f}")
    print(f"   • BB Width      : {X_live['bb_width'].values[0]:.4f}")
    print(f"   • Prediction    : [{predicted_label}] ({confidence:.1f}% confidence)")
    
    return predicted_label, float(confidence)

if __name__ == "__main__":
    get_live_regime_prediction("BTC-USDT")