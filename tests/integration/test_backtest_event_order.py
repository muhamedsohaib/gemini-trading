"""Integration tests for completed-candle decision and fill ordering."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from gemini_trading.domain.candle import Candle
from gemini_trading.domain.dataset import DatasetManifest
from gemini_trading.domain.instrument import Instrument
from gemini_trading.domain.order import OrderIntent, OrderSide, OrderType, TimeInForce
from gemini_trading.domain.timeframe import Timeframe
from gemini_trading.research.config import SimulationConfig
from gemini_trading.research.dataset_reader import VerifiedDataset
from gemini_trading.research.engine import run_backtest
from gemini_trading.research.fixture_strategy import ScriptedFixtureStrategy
from gemini_trading.research.identity import build_experiment_manifest


def test_completed_candle_decision_fills_only_on_next_candle() -> None:
    instrument = Instrument("ETHUSDT", "ETH", "USDT")
    start = datetime(2025, 1, 1, tzinfo=UTC)
    candles = tuple(
        Candle(
            instrument=instrument,
            timeframe=Timeframe.H4,
            open_time=start + timedelta(hours=4 * index),
            close_time=start
            + timedelta(hours=4 * (index + 1))
            - timedelta(milliseconds=1),
            open=Decimal("100"),
            high=Decimal("110"),
            low=Decimal("90"),
            close=Decimal("105"),
            volume=Decimal("20"),
            completed=True,
            source_provider="binance_spot",
        )
        for index in range(2)
    )
    dataset = VerifiedDataset(
        manifest=DatasetManifest(
            schema_version="candle-dataset-v1",
            dataset_id="a" * 64,
            provider="binance_spot",
            instrument=instrument,
            timeframe=Timeframe.H4,
            start_time=start,
            end_time=start + timedelta(hours=8),
            first_open_time=candles[0].open_time,
            last_open_time=candles[-1].open_time,
            candle_count=2,
            canonical_sha256="b" * 64,
        ),
        candles=candles,
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
                        time_in_force=TimeInForce.BAR,
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

    evidence = run_backtest(dataset, manifest, config, strategy)

    assert evidence.decisions[0].candle_index == 0
    assert evidence.orders[0].created_candle_index == 0
    assert evidence.orders[0].eligible_candle_index == 1
    assert evidence.fills[0].candle_index == 1
    assert len(evidence.account_series) == 2
    assert evidence.terminal_account.position_quantity == Decimal("1")
