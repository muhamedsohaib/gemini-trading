"""RED integration tests for locked baseline execution equivalence."""

import hashlib
from datetime import timedelta
from decimal import Decimal

import pytest

from gemini_trading.data.providers.binance_spot import BinanceSpotProvider
from gemini_trading.domain.dataset import DatasetManifest
from gemini_trading.domain.experiment import LimitFillPolicy, TimingPolicy
from gemini_trading.research.config import serialize_simulation_config
from gemini_trading.research.dataset_reader import VerifiedDataset
from gemini_trading.research.engine import run_backtest
from gemini_trading.research.identity import build_experiment_manifest
from gemini_trading.strategy.baselines import BaselineSuite
from research_fixture_support import official_config
from strategy_fixture_support import rising_candles


def baseline_dataset() -> VerifiedDataset:
    """Return one deterministic provider-free baseline comparison dataset."""

    candles = rising_candles(90)
    manifest = DatasetManifest(
        schema_version="candle-dataset-v1",
        dataset_id="7" * 64,
        provider="binance_spot",
        instrument=candles[0].instrument,
        timeframe=candles[0].timeframe,
        start_time=candles[0].open_time,
        end_time=candles[-1].close_time + timedelta(milliseconds=1),
        first_open_time=candles[0].open_time,
        last_open_time=candles[-1].open_time,
        candle_count=len(candles),
        canonical_sha256="8" * 64,
    )
    return VerifiedDataset(
        manifest=manifest,
        candles=candles,
        canonical_bytes=b"baseline-fixture",
    )


def provider_forbidden(*_args: object, **_kwargs: object) -> None:
    raise AssertionError("baseline comparison must not construct a provider")


def test_locked_baselines_share_the_exact_research_engine_policy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(BinanceSpotProvider, "__init__", provider_forbidden)
    dataset = baseline_dataset()
    config = official_config()
    expected_config_hash = hashlib.sha256(serialize_simulation_config(config)).hexdigest()
    strategies = BaselineSuite.for_candles(
        dataset.candles,
        quantity_step=config.quantity_step,
        minimum_quantity=config.min_quantity,
        minimum_notional=config.min_notional,
    )

    evidences = []
    for strategy in strategies:
        manifest = build_experiment_manifest(
            dataset=dataset,
            config=config,
            code_commit="4" * 40,
            strategy_id=strategy.strategy_id,
            strategy_config=strategy.configuration(),
            initial_cash=Decimal("1000"),
            random_seed=0,
        )
        evidence = run_backtest(dataset, manifest, config, strategy)
        evidences.append(evidence)

    assert len(evidences) == 5
    assert all(
        item.experiment_manifest.simulation_config_sha256 == expected_config_hash
        for item in evidences
    )
    assert all(
        item.experiment_manifest.timing_policy is TimingPolicy.NEXT_CANDLE
        for item in evidences
    )
    assert all(
        item.experiment_manifest.limit_fill_policy is LimitFillPolicy.CONSERVATIVE
        for item in evidences
    )
    buy_hold = next(
        item
        for item in evidences
        if item.experiment_manifest.strategy_id == "buy_hold.v1"
    )
    assert buy_hold.fills
    assert buy_hold.fills[0].candle_index == 1
