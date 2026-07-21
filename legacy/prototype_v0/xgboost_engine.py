import numpy as np
import pandas as pd
from okx.MarketData import MarketAPI
from xgboost import XGBClassifier


def fetch_historical_bars(trading_pair: str = "BTC-USDT", limit: str = "100"):
    """Historical Version 0 data loader retained for regression analysis only."""
    market_client = MarketAPI(flag="0")
    result = market_client.get_candlesticks(
        instId=trading_pair,
        bar="15m",
        limit=limit,
    )

    if not result or result.get("code") != "0":
        raise RuntimeError(f"Failed to fetch data from OKX: {result.get('msg')}")

    candles = result.get("data", [])
    candles.reverse()
    frame = pd.DataFrame(
        candles,
        columns=[
            "timestamp",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "volCcy",
            "volCcyQuote",
            "confirm",
        ],
    )
    for column in ["open", "high", "low", "close", "volume"]:
        frame[column] = frame[column].astype(float)
    return frame


def calculate_technical_indicators(frame):
    frame["ema_9"] = frame["close"].ewm(span=9, adjust=False).mean()
    frame["ema_21"] = frame["close"].ewm(span=21, adjust=False).mean()
    frame["ema_crossover"] = frame["ema_9"] - frame["ema_21"]

    delta = frame["close"].diff()
    gain = delta.where(delta > 0, 0).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    relative_strength = gain / loss.replace(0, np.nan)
    frame["rsi_14"] = 100 - (100 / (1 + relative_strength))
    frame["rsi_14"] = frame["rsi_14"].fillna(50)

    frame["sma_20"] = frame["close"].rolling(window=20).mean()
    frame["std_20"] = frame["close"].rolling(window=20).std()
    frame["bb_upper"] = frame["sma_20"] + frame["std_20"] * 2
    frame["bb_lower"] = frame["sma_20"] - frame["std_20"] * 2
    frame["bb_width"] = (
        frame["bb_upper"] - frame["bb_lower"]
    ) / frame["sma_20"]
    return frame


def label_market_regimes(frame, trend_threshold: float = 0.004):
    future_return = frame["close"].shift(-3) / frame["close"] - 1
    conditions = [
        future_return > trend_threshold,
        future_return < -trend_threshold,
    ]
    frame["target_regime"] = np.select(conditions, [1, 2], default=0)
    return frame


def get_live_regime_prediction(trading_pair: str = "BTC-USDT"):
    frame = fetch_historical_bars(trading_pair, limit="100")
    frame = calculate_technical_indicators(frame)
    frame = label_market_regimes(frame)
    clean = frame.dropna().copy()

    features = ["rsi_14", "ema_crossover", "bb_width"]
    training_features = clean[features].iloc[:-1]
    training_target = clean["target_regime"].iloc[:-1]
    live_features = clean[features].iloc[[-1]]

    model = XGBClassifier(
        n_estimators=50,
        learning_rate=0.05,
        max_depth=3,
        random_state=42,
        eval_metric="mlogloss",
    )
    model.fit(training_features, training_target)

    prediction = model.predict(live_features)[0]
    probabilities = model.predict_proba(live_features)[0]
    confidence = probabilities[prediction] * 100
    regime_map = {0: "Ranging", 1: "Trending Up", 2: "Trending Down"}
    return regime_map[prediction], float(confidence)
