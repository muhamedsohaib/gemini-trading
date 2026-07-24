"""Deterministic fixtures shared by candidate-strategy tests."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from gemini_trading.domain.candle import Candle
from gemini_trading.domain.instrument import Instrument
from gemini_trading.domain.timeframe import Timeframe
from gemini_trading.strategy.identity import StrategyStudyManifest


def example_study_manifest() -> StrategyStudyManifest:
    """Return one valid manifest with visibly distinct trust-boundary hashes."""

    return StrategyStudyManifest(
        schema_version="strategy-study-manifest-v1",
        dataset_id="a" * 64,
        canonical_sha256="b" * 64,
        code_commit="3" * 40,
        policy_id="c" * 64,
        simulation_config_id="d" * 64,
        feature_registry_id="e" * 64,
        label_policy_id="f" * 64,
        split_plan_id="1" * 64,
        random_seed_policy_id="2" * 64,
        initial_cash=Decimal("10000"),
    )


def strategy_instrument() -> Instrument:
    """Return the locked candidate instrument without production-source literals."""

    base_asset = "BTC"
    quote_asset = "USDT"
    return Instrument(f"{base_asset}{quote_asset}", base_asset, quote_asset)


def btc_candle(
    index: int,
    *,
    close: Decimal,
    volume: Decimal | None = None,
) -> Candle:
    """Return one completed deterministic four-hour candle."""

    opened = datetime(2020, 1, 1, tzinfo=UTC) + timedelta(hours=4 * index)
    opening = close - Decimal("3") + Decimal(index % 5)
    high = max(opening, close) + Decimal("4") + Decimal(index % 3)
    low = min(opening, close) - Decimal("4") - Decimal(index % 2)
    resolved_volume = volume if volume is not None else Decimal("1000") + Decimal(index * 7)
    return Candle(
        instrument=strategy_instrument(),
        timeframe=Timeframe.H4,
        open_time=opened,
        close_time=opened + timedelta(hours=4) - timedelta(milliseconds=1),
        open=opening,
        high=high,
        low=low,
        close=close,
        volume=resolved_volume,
        completed=True,
        source_provider="binance_spot",
    )


def rising_candles(count: int) -> tuple[Candle, ...]:
    """Return deterministic non-degenerate candles for feature tests."""

    return tuple(
        btc_candle(
            index,
            close=(
                Decimal("10000") + Decimal(index * 11) + Decimal((index % 7) - 3) * Decimal("2.5")
            ),
        )
        for index in range(count)
    )
