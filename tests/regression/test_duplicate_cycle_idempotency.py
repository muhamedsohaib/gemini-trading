"""Regression guards against duplicate chronological decision cycles."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from gemini_trading.domain.candle import Candle
from gemini_trading.domain.dataset import DatasetManifest
from gemini_trading.domain.instrument import Instrument
from gemini_trading.domain.order import OrderIntent, OrderSide, OrderType, TimeInForce
from gemini_trading.domain.timeframe import Timeframe
from gemini_trading.research.config import SimulationConfig
from gemini_trading.research.dataset_reader import VerifiedDataset
from gemini_trading.research.engine import BacktestEngine
from gemini_trading.research.errors import ChronologyViolationError
from gemini_trading.research.fixture_strategy import ScriptedFixtureStrategy
from gemini_trading.research.identity import build_experiment_manifest


def test_duplicate_event_identity_does_not_create_duplicate_orders() -> None:
    instrument = Instrument("ETHUSDT", "ETH", "USDT")
    start = datetime(2025, 1, 1, tzinfo=UTC)
    candle = Candle(
        instrument=instrument,
        timeframe=Timeframe.H4,
        open_time=start,
        close_time=start + timedelta(hours=4) - timedelta(milliseconds=1),
        open=Decimal("100"),
        high=Decimal("110"),
        low=Decimal("90"),
        close=Decimal("105"),
        volume=Decimal("20"),
        completed=True,
        source_provider="binance_spot",
    )
    dataset = VerifiedDataset(
        manifest=DatasetManifest(
            schema_version="candle-dataset-v1",
            dataset_id="a" * 64,
            provider="binance_spot",
            instrument=instrument,
            timeframe=Timeframe.H4,
            start_time=start,
            end_time=start + timedelta(hours=4),
            first_open_time=start,
            last_open_time=start,
            candle_count=1,
            canonical_sha256="b" * 64,
        ),
        candles=(candle,),
        canonical_bytes=b"fixture",
    )
    config = SimulationConfig.official(
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
    strategy = ScriptedFixtureStrategy(
        script=(
            (
                0,
                (
                    OrderIntent(
                        side=OrderSide.BUY,
                        order_type=OrderType.MARKET,
                        quantity=Decimal("1"),
                        limit_price=None,
                        time_in_force=TimeInForce.GTC,
                    ),
                ),
            ),
        )
    )
    manifest = build_experiment_manifest(
        dataset=dataset,
        config=config,
        code_commit="1" * 40,
        strategy_id=strategy.strategy_id,
        strategy_config=strategy.configuration(),
        initial_cash=Decimal("1000"),
        random_seed=0,
    )
    engine = BacktestEngine(dataset, manifest, config, strategy)

    engine.process_candle(0, candle)
    with pytest.raises(ChronologyViolationError, match="duplicate"):
        engine.process_candle(0, candle)

    assert len(engine.evidence.decisions) == 1
    assert len(engine.evidence.orders) == 1
