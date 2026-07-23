"""Tests for deterministic simulation configuration."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from gemini_trading.domain.dataset import DatasetManifest
from gemini_trading.domain.experiment import LimitFillPolicy, TimingPolicy
from gemini_trading.domain.instrument import Instrument
from gemini_trading.domain.order import TimeInForce
from gemini_trading.domain.timeframe import Timeframe
from gemini_trading.research.config import SimulationConfig, serialize_simulation_config
from gemini_trading.research.dataset_reader import VerifiedDataset
from gemini_trading.research.errors import InvalidExperimentConfigError
from gemini_trading.research.identity import build_experiment_manifest

_SHA = "a" * 64
_COMMIT = "b" * 40


def _official(**overrides: object) -> SimulationConfig:
    values: dict[str, object] = {
        "maker_fee_rate": Decimal("0.001"),
        "taker_fee_rate": Decimal("0.001"),
        "half_spread_bps": Decimal("5"),
        "slippage_bps": Decimal("10"),
        "latency_bars": 0,
        "price_tick": Decimal("0.01"),
        "quantity_step": Decimal("0.0001"),
        "min_quantity": Decimal("0.0001"),
        "min_notional": Decimal("5"),
        "max_volume_participation": Decimal("0.01"),
    }
    values.update(overrides)
    return SimulationConfig.official(**values)  # type: ignore[arg-type]


def _dataset() -> VerifiedDataset:
    instant = datetime(2025, 1, 1, tzinfo=UTC)
    manifest = DatasetManifest(
        schema_version="candle-dataset-v1",
        dataset_id=_SHA,
        provider="binance_spot",
        instrument=Instrument("ETHUSDT", "ETH", "USDT"),
        timeframe=Timeframe.H4,
        start_time=instant,
        end_time=datetime(2025, 1, 2, tzinfo=UTC),
        first_open_time=instant,
        last_open_time=instant,
        candle_count=1,
        canonical_sha256=_SHA,
    )
    return VerifiedDataset(manifest, (), b"")


def test_official_config_rejects_zero_costs() -> None:
    with pytest.raises(InvalidExperimentConfigError, match="official"):
        _official(
            maker_fee_rate=Decimal("0"),
            taker_fee_rate=Decimal("0"),
            half_spread_bps=Decimal("0"),
            slippage_bps=Decimal("0"),
        )


def test_diagnostic_policy_forces_non_promotable_result() -> None:
    config = SimulationConfig(
        maker_fee_rate=Decimal("0.001"),
        taker_fee_rate=Decimal("0.001"),
        half_spread_bps=Decimal("5"),
        slippage_bps=Decimal("10"),
        latency_bars=0,
        price_tick=Decimal("0.01"),
        quantity_step=Decimal("0.0001"),
        min_quantity=Decimal("0.0001"),
        min_notional=Decimal("5"),
        max_volume_participation=Decimal("0.01"),
        max_active_candles=3,
        timing_policy=TimingPolicy.SAME_CLOSE_DIAGNOSTIC,
        limit_fill_policy=LimitFillPolicy.OPTIMISTIC_TOUCH_DIAGNOSTIC,
        default_time_in_force=TimeInForce.BAR,
        promotable=True,
    )

    assert config.promotable is False


def test_config_rejects_invalid_liquidity_and_precision() -> None:
    with pytest.raises(InvalidExperimentConfigError, match="max_volume_participation"):
        _official(max_volume_participation=Decimal("1.01"))
    with pytest.raises(InvalidExperimentConfigError, match="price_tick"):
        _official(price_tick=Decimal("0"))


def test_build_manifest_records_verified_dataset_and_config_hash() -> None:
    config = _official()

    manifest = build_experiment_manifest(
        dataset=_dataset(),
        config=config,
        code_commit=_COMMIT,
        strategy_id="fixture-v1",
        strategy_config=(("entry", "1"),),
        initial_cash=Decimal("1000"),
        random_seed=7,
    )

    assert manifest.dataset_id == _SHA
    assert manifest.canonical_sha256 == _SHA
    assert manifest.engine_version == "research-engine-v1"
    assert len(manifest.simulation_config_sha256) == 64
    assert serialize_simulation_config(config).endswith(b"\n")
