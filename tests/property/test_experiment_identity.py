"""Properties for deterministic experiment identity."""

from dataclasses import replace
from decimal import Decimal

from hypothesis import given, strategies as st

from gemini_trading.domain.experiment import (
    ExperimentManifest,
    LimitFillPolicy,
    TimingPolicy,
)
from gemini_trading.domain.order import TimeInForce
from gemini_trading.research.identity import experiment_id, serialize_experiment_manifest

_SHA = "a" * 64
_COMMIT = "b" * 40


def _manifest(strategy_config: tuple[tuple[str, str], ...]) -> ExperimentManifest:
    return ExperimentManifest(
        schema_version="research-experiment-v1",
        dataset_id=_SHA,
        canonical_sha256=_SHA,
        code_commit=_COMMIT,
        engine_version="research-engine-v1",
        strategy_id="fixture-v1",
        strategy_config=strategy_config,
        initial_cash=Decimal("1000"),
        timing_policy=TimingPolicy.NEXT_CANDLE,
        limit_fill_policy=LimitFillPolicy.CONSERVATIVE,
        default_time_in_force=TimeInForce.BAR,
        max_active_candles=3,
        random_seed=0,
        simulation_config_sha256=_SHA,
    )


@given(st.permutations([("b", "2"), ("a", "1")]))
def test_strategy_config_order_does_not_change_experiment_identity(
    items: list[tuple[str, str]],
) -> None:
    manifest = _manifest(tuple(items))
    normalized = replace(manifest, strategy_config=(("a", "1"), ("b", "2")))

    assert experiment_id(manifest) == experiment_id(normalized)
    assert serialize_experiment_manifest(manifest) == serialize_experiment_manifest(normalized)


def test_meaningful_input_changes_experiment_identity() -> None:
    manifest = _manifest((("a", "1"),))

    assert experiment_id(manifest) != experiment_id(replace(manifest, initial_cash=Decimal("1001")))
