"""Deterministic fixtures shared by candidate-strategy tests."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from gemini_trading.domain.candle import Candle
from gemini_trading.domain.experiment import LimitFillPolicy, TimingPolicy
from gemini_trading.domain.instrument import Instrument
from gemini_trading.domain.order import TimeInForce
from gemini_trading.domain.timeframe import Timeframe
from gemini_trading.research.config import SimulationConfig
from gemini_trading.strategy.features import FeatureMatrix, FeatureRegistry, FeatureRow
from gemini_trading.strategy.identity import StrategyStudyManifest
from gemini_trading.strategy.labels import LabelObservation, LabelVector


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


def base_simulation() -> SimulationConfig:
    """Return the approved conservative simulation assumptions used by labels."""

    return SimulationConfig.official(
        maker_fee_rate=Decimal("0.001"),
        taker_fee_rate=Decimal("0.001"),
        half_spread_bps=Decimal("5"),
        slippage_bps=Decimal("10"),
        latency_bars=0,
        price_tick=Decimal("0.01"),
        quantity_step=Decimal("0.000001"),
        min_quantity=Decimal("0.000001"),
        min_notional=Decimal("5"),
        max_volume_participation=Decimal("0.01"),
        max_active_candles=3,
        timing_policy=TimingPolicy.NEXT_CANDLE,
        limit_fill_policy=LimitFillPolicy.CONSERVATIVE,
        default_time_in_force=TimeInForce.BAR,
        promotable=True,
    )


def btc_candle(
    index: int,
    *,
    close: Decimal,
    volume: Decimal | None = None,
    start: datetime = datetime(2020, 1, 1, tzinfo=UTC),
) -> Candle:
    """Return one completed deterministic four-hour candle."""

    opened = start + timedelta(hours=4 * index)
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


def rising_candles(
    count: int,
    *,
    start: datetime = datetime(2020, 1, 1, tzinfo=UTC),
) -> tuple[Candle, ...]:
    """Return deterministic non-degenerate candles for strategy tests."""

    return tuple(
        btc_candle(
            index,
            close=(
                Decimal("10000") + Decimal(index * 11) + Decimal((index % 7) - 3) * Decimal("2.5")
            ),
            start=start,
        )
        for index in range(count)
    )


def calendar_candles(
    *,
    start: datetime,
    end_exclusive: datetime,
) -> tuple[Candle, ...]:
    """Return continuous completed four-hour candles for calendar split tests."""

    if start.tzinfo is None or end_exclusive.tzinfo is None:
        raise ValueError("calendar fixture bounds must be timezone-aware")
    duration = end_exclusive - start
    count = int(duration.total_seconds() // (4 * 60 * 60))
    if start + timedelta(hours=4 * count) != end_exclusive:
        raise ValueError("calendar fixture range must contain whole four-hour candles")
    return rising_candles(count, start=start)


def deterministic_model_fixture(
    row_count: int = 320,
) -> tuple[FeatureMatrix, LabelVector, tuple[int, ...]]:
    """Return aligned non-degenerate features and labels for specialist tests."""

    registry = FeatureRegistry.locked_v0_1()
    start_index = registry.maximum_lookback_candles
    rows: list[FeatureRow] = []
    labels: list[LabelObservation] = []
    for offset in range(row_count):
        candle_index = start_index + offset
        values: list[Decimal] = []
        for column_index, definition in enumerate(registry.definitions):
            value = Decimal((offset + 1) * (column_index + 2)) / Decimal("1000") + Decimal(
                ((offset + column_index * 3) % 17) - 8
            ) / Decimal("100")
            if definition.name == "close_zscore_24":
                value = Decimal("-1.00") if offset % 4 else Decimal("0.25")
            elif definition.name == "drawdown_from_high_24":
                value = Decimal("0.03") if offset % 5 == 0 else Decimal("0.005")
            values.append(value)
        rows.append(
            FeatureRow(
                candle_index=candle_index,
                candle_open_time=datetime(2020, 1, 1, tzinfo=UTC)
                + timedelta(hours=4 * candle_index),
                values=tuple(values),
            )
        )
        positive = offset % 5 in {0, 1}
        labels.append(
            LabelObservation(
                decision_candle_index=candle_index,
                entry_candle_index=candle_index + 1,
                exit_candle_index=candle_index + 4,
                entry_reference_price=Decimal("100"),
                exit_reference_price=Decimal("101") if positive else Decimal("99"),
                entry_fill_price=Decimal("100.20"),
                exit_fill_price=Decimal("100.90") if positive else Decimal("98.80"),
                gross_return=Decimal("0.007") if positive else Decimal("-0.014"),
                net_return=Decimal("0.008") if positive else Decimal("-0.016"),
                hurdle_bps=Decimal("60"),
                positive=positive,
            )
        )
    matrix = FeatureMatrix(
        schema_version="candidate-feature-matrix-v1",
        definitions=registry.definitions,
        rows=tuple(rows),
    )
    vector = LabelVector(
        schema_version="candidate-label-vector-v1",
        horizon_candles=3,
        hurdle_bps=Decimal("60"),
        observations=tuple(labels),
    )
    return matrix, vector, tuple(row.candle_index for row in rows)
