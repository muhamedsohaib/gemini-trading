"""Property tests for deterministic backtest result identity."""

from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st

from gemini_trading.domain.account import AccountSnapshot
from gemini_trading.domain.experiment import ExperimentManifest, LimitFillPolicy, TimingPolicy
from gemini_trading.domain.order import TimeInForce
from gemini_trading.research.artifacts import build_artifacts
from gemini_trading.research.engine import BacktestEvidence


def _empty_evidence(initial_cash: Decimal) -> BacktestEvidence:
    manifest = ExperimentManifest(
        schema_version="research-experiment-v1",
        dataset_id="a" * 64,
        canonical_sha256="b" * 64,
        code_commit="1" * 40,
        engine_version="research-engine-v1",
        strategy_id="fixture.scripted.v1",
        strategy_config=(("script", "[]"),),
        initial_cash=initial_cash,
        timing_policy=TimingPolicy.NEXT_CANDLE,
        limit_fill_policy=LimitFillPolicy.CONSERVATIVE,
        default_time_in_force=TimeInForce.BAR,
        max_active_candles=3,
        random_seed=0,
        simulation_config_sha256="c" * 64,
    )
    terminal = AccountSnapshot.initial(initial_cash)
    return BacktestEvidence(
        experiment_manifest=manifest,
        decisions=(),
        orders=(),
        fills=(),
        ledger=(),
        account_series=(terminal,),
        rejection_records=(),
        terminal_account=terminal,
    )


@given(initial_cash_value=st.integers(min_value=1, max_value=1_000_000))
def test_identical_evidence_has_identical_result_identity(initial_cash_value: int) -> None:
    evidence = _empty_evidence(Decimal(initial_cash_value))

    first = build_artifacts(evidence)
    second = build_artifacts(evidence)

    assert first == second
    assert len(first.experiment_id) == 64
    assert len(first.result_id) == 64


def test_result_identity_changes_when_evidence_changes() -> None:
    first = build_artifacts(_empty_evidence(Decimal("1000")))
    second = build_artifacts(_empty_evidence(Decimal("1001")))

    assert first.experiment_id != second.experiment_id
    assert first.result_id != second.result_id
