"""Tests for chronological backtesting orchestration and order lifecycles."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from gemini_trading.domain.candle import Candle
from gemini_trading.domain.dataset import DatasetManifest
from gemini_trading.domain.experiment import LimitFillPolicy, TimingPolicy
from gemini_trading.domain.instrument import Instrument
from gemini_trading.domain.order import (
    OrderIntent,
    OrderSide,
    OrderStatus,
    OrderType,
    TimeInForce,
)
from gemini_trading.domain.timeframe import Timeframe
from gemini_trading.research.config import SimulationConfig
from gemini_trading.research.dataset_reader import VerifiedDataset
from gemini_trading.research.engine import BacktestEvidence, run_backtest
from gemini_trading.research.fixture_strategy import ScriptedFixtureStrategy
from gemini_trading.research.identity import build_experiment_manifest

_INSTRUMENT = Instrument("ETHUSDT", "ETH", "USDT")
_START = datetime(2025, 1, 1, tzinfo=UTC)


def _candle(index: int, *, volume: Decimal = Decimal("20")) -> Candle:
    open_time = _START + timedelta(hours=4 * index)
    return Candle(
        instrument=_INSTRUMENT,
        timeframe=Timeframe.H4,
        open_time=open_time,
        close_time=open_time + timedelta(hours=4) - timedelta(milliseconds=1),
        open=Decimal("100"),
        high=Decimal("110"),
        low=Decimal("90"),
        close=Decimal("105"),
        volume=volume,
        completed=True,
        source_provider="binance_spot",
    )


def _dataset(*, candle_count: int = 4, volume: Decimal = Decimal("20")) -> VerifiedDataset:
    candles = tuple(_candle(index, volume=volume) for index in range(candle_count))
    manifest = DatasetManifest(
        schema_version="candle-dataset-v1",
        dataset_id="a" * 64,
        provider="binance_spot",
        instrument=_INSTRUMENT,
        timeframe=Timeframe.H4,
        start_time=_START,
        end_time=_START + timedelta(hours=4 * candle_count),
        first_open_time=candles[0].open_time,
        last_open_time=candles[-1].open_time,
        candle_count=len(candles),
        canonical_sha256="b" * 64,
    )
    return VerifiedDataset(manifest=manifest, candles=candles, canonical_bytes=b"fixture")


def _config(
    *,
    timing_policy: TimingPolicy = TimingPolicy.NEXT_CANDLE,
    max_active_candles: int = 3,
    participation: Decimal = Decimal("0.25"),
) -> SimulationConfig:
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
        max_volume_participation=participation,
        max_active_candles=max_active_candles,
        timing_policy=timing_policy,
        limit_fill_policy=LimitFillPolicy.CONSERVATIVE,
    )


def _market(side: OrderSide, quantity: str, tif: TimeInForce = TimeInForce.BAR) -> OrderIntent:
    return OrderIntent(
        side=side,
        order_type=OrderType.MARKET,
        quantity=Decimal(quantity),
        limit_price=None,
        time_in_force=tif,
    )


def _limit(price: str, tif: TimeInForce = TimeInForce.GTC) -> OrderIntent:
    return OrderIntent(
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=Decimal("1"),
        limit_price=Decimal(price),
        time_in_force=tif,
    )


def _run(
    script: tuple[tuple[int, tuple[OrderIntent, ...]], ...],
    *,
    dataset: VerifiedDataset | None = None,
    config: SimulationConfig | None = None,
) -> BacktestEvidence:
    selected_dataset = _dataset() if dataset is None else dataset
    selected_config = _config() if config is None else config
    strategy = ScriptedFixtureStrategy(script=script)
    manifest = build_experiment_manifest(
        dataset=selected_dataset,
        config=selected_config,
        code_commit="1" * 40,
        strategy_id=strategy.strategy_id,
        strategy_config=strategy.configuration(),
        initial_cash=Decimal("1000"),
        random_seed=0,
    )
    return run_backtest(selected_dataset, manifest, selected_config, strategy)


def test_official_decision_on_candle_zero_cannot_fill_before_candle_one() -> None:
    evidence = _run(((0, (_market(OrderSide.BUY, "1"),)),))

    assert evidence.decisions[0].candle_index == 0
    assert evidence.orders[0].eligible_candle_index == 1
    assert evidence.fills[0].candle_index == 1


def test_bar_partial_fill_cancels_remainder_after_first_eligible_candle() -> None:
    evidence = _run(
        ((0, (_market(OrderSide.BUY, "2"),)),),
        dataset=_dataset(volume=Decimal("2")),
    )

    assert len(evidence.fills) == 1
    assert evidence.fills[0].quantity == Decimal("0.5")
    assert evidence.orders[0].status is OrderStatus.CANCELLED


def test_gtc_order_expires_after_bounded_lifetime() -> None:
    evidence = _run(
        ((0, (_limit("80"),)),),
        config=_config(max_active_candles=2),
    )

    assert evidence.fills == ()
    assert evidence.orders[0].eligible_candle_index == 1
    assert evidence.orders[0].expires_after_candle_index == 2
    assert evidence.orders[0].status is OrderStatus.EXPIRED


def test_sell_without_owned_position_is_rejected() -> None:
    evidence = _run(((0, (_market(OrderSide.SELL_TO_CLOSE, "1"),)),))

    assert evidence.orders == ()
    assert evidence.rejection_records[0]["reason"] == "insufficient_position"


def test_conflicting_simultaneous_intents_are_rejected() -> None:
    evidence = _run(
        (
            (
                0,
                (
                    _market(OrderSide.BUY, "1"),
                    _market(OrderSide.SELL_TO_CLOSE, "1"),
                ),
            ),
        )
    )

    assert evidence.orders == ()
    assert len(evidence.rejection_records) == 2
    assert {record["reason"] for record in evidence.rejection_records} == {"conflicting_intents"}


def test_experiment_end_cancels_still_active_order() -> None:
    evidence = _run(
        ((3, (_limit("80"),)),),
        config=_config(max_active_candles=3),
    )

    assert evidence.orders[0].status is OrderStatus.CANCELLED


def test_same_close_diagnostic_fills_at_decision_candle_and_is_non_promotable() -> None:
    config = _config(timing_policy=TimingPolicy.SAME_CLOSE_DIAGNOSTIC)
    evidence = _run(((0, (_market(OrderSide.BUY, "1"),)),), config=config)

    assert config.promotable is False
    assert evidence.fills[0].candle_index == 0
    assert evidence.fills[0].reference_price == Decimal("105")
