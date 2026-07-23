"""Tests for immutable experiment contracts."""

from dataclasses import FrozenInstanceError, replace
from decimal import Decimal

import pytest

from gemini_trading.domain.experiment import (
    ExperimentManifest,
    LimitFillPolicy,
    TimingPolicy,
)
from gemini_trading.domain.order import TimeInForce

_SHA = "a" * 64
_COMMIT = "b" * 40


def _manifest() -> ExperimentManifest:
    return ExperimentManifest(
        schema_version="research-experiment-v1",
        dataset_id=_SHA,
        canonical_sha256=_SHA,
        code_commit=_COMMIT,
        engine_version="0.1.0",
        strategy_id="fixture-v1",
        strategy_config=(("entry", "1"),),
        initial_cash=Decimal("1000.00"),
        timing_policy=TimingPolicy.NEXT_CANDLE,
        limit_fill_policy=LimitFillPolicy.CONSERVATIVE,
        default_time_in_force=TimeInForce.BAR,
        max_active_candles=3,
        random_seed=0,
        simulation_config_sha256=_SHA,
    )


def test_experiment_manifest_is_immutable_and_preserves_policy_identity() -> None:
    manifest = _manifest()

    assert manifest.timing_policy is TimingPolicy.NEXT_CANDLE
    assert manifest.limit_fill_policy is LimitFillPolicy.CONSERVATIVE
    with pytest.raises(FrozenInstanceError):
        manifest.initial_cash = Decimal("1")  # type: ignore[misc]


def test_experiment_manifest_validates_hashes_commit_and_capital() -> None:
    manifest = _manifest()

    with pytest.raises(ValueError, match="dataset_id"):
        replace(manifest, dataset_id="not-a-sha")
    with pytest.raises(ValueError, match="code_commit"):
        replace(manifest, code_commit="ABC")
    with pytest.raises(ValueError, match="initial_cash"):
        replace(manifest, initial_cash=Decimal("0"))
    with pytest.raises(ValueError, match="max_active_candles"):
        replace(manifest, max_active_candles=0)


def test_experiment_manifest_rejects_duplicate_strategy_config_keys() -> None:
    with pytest.raises(ValueError, match="strategy_config"):
        replace(_manifest(), strategy_config=(("entry", "1"), ("entry", "2")))
