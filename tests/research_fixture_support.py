"""Shared deterministic fixture builders for research integration tests."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from gemini_trading.data.datasets.canonical_writer import (
    build_dataset_manifest,
    serialize_candles,
    serialize_dataset_manifest,
)
from gemini_trading.data.storage.local_immutable import LocalImmutableStore
from gemini_trading.domain.candle import Candle
from gemini_trading.domain.instrument import Instrument
from gemini_trading.domain.order import OrderIntent, OrderSide, OrderType, TimeInForce
from gemini_trading.domain.timeframe import Timeframe
from gemini_trading.research.artifacts import LocalResearchStore, ResearchArtifacts, build_artifacts
from gemini_trading.research.config import SimulationConfig
from gemini_trading.research.dataset_reader import VerifiedDataset, load_verified_dataset
from gemini_trading.research.engine import run_backtest
from gemini_trading.research.fixture_strategy import ScriptedFixtureStrategy
from gemini_trading.research.identity import build_experiment_manifest


def official_config() -> SimulationConfig:
    """Return the fixed cost-bearing conservative acceptance configuration."""

    return SimulationConfig.official(
        maker_fee_rate=Decimal("0.001"),
        taker_fee_rate=Decimal("0.001"),
        half_spread_bps=Decimal("5"),
        slippage_bps=Decimal("10"),
        latency_bars=0,
        price_tick=Decimal("0.01"),
        quantity_step=Decimal("0.0001"),
        min_quantity=Decimal("0.0001"),
        min_notional=Decimal("1"),
        max_volume_participation=Decimal("0.25"),
    )


def fixture_strategy() -> ScriptedFixtureStrategy:
    """Return one deterministic buy-hold-sell fixture strategy."""

    buy = OrderIntent(
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("1"),
        limit_price=None,
        time_in_force=TimeInForce.BAR,
    )
    sell = OrderIntent(
        side=OrderSide.SELL_TO_CLOSE,
        order_type=OrderType.MARKET,
        quantity=Decimal("1"),
        limit_price=None,
        time_in_force=TimeInForce.BAR,
    )
    return ScriptedFixtureStrategy(script=((0, (buy,)), (2, (sell,))))


def write_fixture_dataset(root: Path) -> VerifiedDataset:
    """Write and reload one canonical four-candle ETHUSDT dataset."""

    instrument = Instrument("ETHUSDT", "ETH", "USDT")
    start = datetime(2025, 1, 1, tzinfo=UTC)
    candles = tuple(
        Candle(
            instrument=instrument,
            timeframe=Timeframe.H4,
            open_time=start + timedelta(hours=4 * index),
            close_time=start + timedelta(hours=4 * (index + 1)) - timedelta(milliseconds=1),
            open=Decimal(open_price),
            high=Decimal(high),
            low=Decimal(low),
            close=Decimal(close),
            volume=Decimal("20"),
            completed=True,
            source_provider="binance_spot",
        )
        for index, (open_price, high, low, close) in enumerate(
            (
                ("100", "103", "98", "101"),
                ("102", "106", "100", "105"),
                ("105", "109", "103", "108"),
                ("110", "113", "108", "111"),
            )
        )
    )
    canonical_bytes = serialize_candles(candles)
    manifest = build_dataset_manifest(
        schema_version="candle-dataset-v1",
        provider="binance_spot",
        instrument=instrument,
        timeframe=Timeframe.H4,
        start_time=start,
        end_time=start + timedelta(hours=16),
        candles=candles,
        canonical_bytes=canonical_bytes,
    )
    store = LocalImmutableStore(root)
    store.write_dataset(
        manifest.dataset_id,
        canonical_bytes,
        serialize_dataset_manifest(manifest),
    )
    return load_verified_dataset(store, manifest.dataset_id)


def write_completed_fixture_experiment(
    root: Path,
    *,
    code_commit: str = "1" * 40,
) -> tuple[str, ResearchArtifacts]:
    """Run and persist one completed deterministic fixture experiment."""

    dataset = write_fixture_dataset(root)
    config = official_config()
    strategy = fixture_strategy()
    manifest = build_experiment_manifest(
        dataset=dataset,
        config=config,
        code_commit=code_commit,
        strategy_id=strategy.strategy_id,
        strategy_config=strategy.configuration(),
        initial_cash=Decimal("1000"),
        random_seed=0,
    )
    evidence = run_backtest(dataset, manifest, config, strategy)
    artifacts = build_artifacts(evidence)
    LocalResearchStore(root).write(artifacts)
    return artifacts.experiment_id, artifacts
