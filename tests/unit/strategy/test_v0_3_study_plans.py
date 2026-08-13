"""Candidate v0.3 qualification case-plan contract tests."""

from __future__ import annotations

import importlib
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, cast

from gemini_trading.research.config import SimulationConfig
from gemini_trading.research.dataset_reader import VerifiedDataset
from gemini_trading.research.serialization import canonical_json_bytes
from gemini_trading.strategy.baselines import BaselineAction, BaselineSchedule
from gemini_trading.strategy.contracts import RegimeState, SpecialistKind
from gemini_trading.strategy.features import FeatureMatrix
from gemini_trading.strategy.labels import LabelPolicy
from gemini_trading.strategy.policy import CandidatePolicy
from gemini_trading.strategy.replay import SUPPORTED_REPLAY_STRATEGY_IDS
from gemini_trading.strategy.study import StudyPhase
from gemini_trading.strategy.study_execution import CasePlan
from gemini_trading.strategy.study_strategy import ScheduledAction
from gemini_trading.strategy.v0_3_predictions import V03PredictionContext

_EXPECTED_CASE_IDS = (
    "candidate.multi_model.v0_3",
    "cash.v1",
    "buy_hold.v1",
    "ema_20_50.v1",
    "donchian_20_10.v1",
    "mean_reversion_z24.v1",
    "trend.specialist.v1",
    "mean_reversion.specialist.v1",
    "trend.ema_20_50.gated.v1",
    "ranging.mean_reversion_z24.gated.v1",
    "ablation.no_percentile_selectivity.v1",
    "ablation.no_volume.v1",
    "ablation.no_protection.v1",
    "control.delayed_features.v1",
    "control.shuffled_labels.v1",
    "cost.1_5x",
    "cost.2x",
    "sensitivity.entry_percentile_0_70",
    "sensitivity.entry_percentile_0_80",
    "sensitivity.exit_0_42",
    "sensitivity.exit_0_48",
    "sensitivity.max_hold_12",
    "sensitivity.max_hold_24",
    "sensitivity.initial_stop_2_0",
    "sensitivity.initial_stop_3_0",
    "sensitivity.cooldown_1",
    "sensitivity.cooldown_3",
    "control.shuffled_labels.seed_1799",
    "control.delayed_features.final",
    "bootstrap.seed_1788",
)


def _modules() -> tuple[Any, Any]:
    return (
        importlib.import_module("gemini_trading.strategy.v0_3_cases"),
        importlib.import_module("gemini_trading.strategy.v0_3_study_plans"),
    )


def test_v0_3_qualification_case_inventory_is_exact_and_removes_obsolete_cases() -> None:
    cases, _ = _modules()

    assert cases.V03_QUALIFICATION_CASE_IDS == _EXPECTED_CASE_IDS
    assert len(cases.V03_QUALIFICATION_CASE_IDS) == len(set(cases.V03_QUALIFICATION_CASE_IDS))
    assert "ablation.no_disagreement.v1" not in cases.V03_QUALIFICATION_CASE_IDS
    assert "sensitivity.entry_0_59" not in cases.V03_QUALIFICATION_CASE_IDS
    assert "sensitivity.entry_0_65" not in cases.V03_QUALIFICATION_CASE_IDS
    assert "candidate.multi_model.v0_3" in SUPPORTED_REPLAY_STRATEGY_IDS


def _prediction(
    index: int,
    regime: RegimeState,
    trend: str,
    mean: str,
) -> SimpleNamespace:
    return SimpleNamespace(
        candle_index=index,
        trend_probability=Decimal(trend),
        mean_reversion_probability=Decimal(mean),
        regime=SimpleNamespace(state=regime),
    )


def test_v0_3_fold_diagnostics_are_canonical_and_non_gating() -> None:
    cases, _ = _modules()
    bundle = SimpleNamespace(
        predictions=(
            _prediction(10, RegimeState.TRENDING, "0.70", "0.20"),
            _prediction(11, RegimeState.RANGING, "0.40", "0.65"),
            _prediction(12, RegimeState.UNSTABLE, "0.60", "0.40"),
        )
    )
    first = cases.build_v0_3_fold_diagnostics(
        fold_number=3,
        indices=(10, 11, 12),
        bundle=bundle,
    )
    second = cases.build_v0_3_fold_diagnostics(
        fold_number=3,
        indices=(10, 11, 12),
        bundle=bundle,
    )

    assert first.schema_version == "candidate-v0.3-fold-diagnostics-v1"
    assert first.fold_number == 3
    assert first.companion_indices == (10, 11)
    assert first.companion_probabilities == (Decimal("0.20"), Decimal("0.40"))
    assert first.disagreement_indices == (10, 11, 12)
    assert first.absolute_disagreements == (
        Decimal("0.50"),
        Decimal("0.25"),
        Decimal("0.20"),
    )
    assert len(first.companion_distribution_sha256) == 64
    assert len(first.disagreement_distribution_sha256) == 64
    assert cases.serialize_v0_3_fold_diagnostics(first) == cases.serialize_v0_3_fold_diagnostics(second)
    assert canonical_json_bytes({"diagnostics": first})


def _simulation() -> SimulationConfig:
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
    )


def _baseline_schedules() -> dict[str, BaselineSchedule]:
    actions = (BaselineAction.CASH,) * 4
    return {
        case_id: BaselineSchedule(case_id, actions)
        for case_id in (
            "cash.v1",
            "buy_hold.v1",
            "ema_20_50.v1",
            "donchian_20_10.v1",
            "mean_reversion_z24.v1",
        )
    }


def test_prepare_v0_3_phase_uses_q75_primary_q70_q80_neighbors_and_half_floor_ablation(
    monkeypatch,
) -> None:
    cases, plans_module = _modules()
    calls: list[dict[str, object]] = []

    def fake_candidate_events(_bundle, **kwargs):
        calls.append(dict(kwargs))
        return ((0, ScheduledAction.ENTER_LONG), (1, ScheduledAction.EXIT_TO_CASH))

    monkeypatch.setattr(plans_module, "candidate_events", fake_candidate_events)
    monkeypatch.setattr(plans_module, "threshold_events", lambda *_args, **_kwargs: ())
    monkeypatch.setattr(plans_module, "baseline_events", lambda *_args, **_kwargs: ())

    class FakeContext:
        bundle = SimpleNamespace(
            predictions=(
                _prediction(0, RegimeState.TRENDING, "0.70", "0.45"),
                _prediction(1, RegimeState.TRENDING, "0.70", "0.45"),
            )
        )

        @staticmethod
        def effective_thresholds(percentile: Decimal) -> dict[SpecialistKind, Decimal]:
            values = {
                Decimal("0.70"): (Decimal("0.57"), Decimal("0.58")),
                Decimal("0.75"): (Decimal("0.61"), Decimal("0.62")),
                Decimal("0.80"): (Decimal("0.66"), Decimal("0.67")),
            }
            trend, mean = values[percentile]
            return {
                SpecialistKind.TREND: trend,
                SpecialistKind.MEAN_REVERSION: mean,
            }

    dataset = cast(
        VerifiedDataset,
        SimpleNamespace(candles=(SimpleNamespace(), SimpleNamespace(), SimpleNamespace(), SimpleNamespace())),
    )
    plans: dict[tuple[StudyPhase, int | None, str], CasePlan] = {}
    plans_module.prepare_v0_3_phase(
        phase=StudyPhase.DEVELOPMENT,
        fold_number=1,
        indices=(0, 1),
        context=cast(V03PredictionContext, FakeContext()),
        dataset=dataset,
        simulation=_simulation(),
        policy=CandidatePolicy.locked_v0_3(),
        label_policy=cast(LabelPolicy, SimpleNamespace(hurdle_bps=Decimal("60"))),
        matrix=cast(FeatureMatrix, SimpleNamespace()),
        baseline_schedules=_baseline_schedules(),
        plans=plans,
    )

    assert tuple(key[2] for key in plans) == cases.V03_QUALIFICATION_CASE_IDS
    primary = plans[(StudyPhase.DEVELOPMENT, 1, "candidate.multi_model.v0_3")]
    assert primary.strategy.strategy_id == "candidate.multi_model.v0_3"
    assert plans[(StudyPhase.DEVELOPMENT, 1, "cost.1_5x")].simulation.taker_fee_rate == Decimal("0.0015")
    assert plans[(StudyPhase.DEVELOPMENT, 1, "cost.2x")].simulation.taker_fee_rate == Decimal("0.002")

    threshold_calls = [
        cast(dict[SpecialistKind, Decimal], call["entry_thresholds"])
        for call in calls
        if call.get("entry_thresholds") is not None
    ]
    assert {
        (values[SpecialistKind.TREND], values[SpecialistKind.MEAN_REVERSION])
        for values in threshold_calls
    } >= {
        (Decimal("0.57"), Decimal("0.58")),
        (Decimal("0.61"), Decimal("0.62")),
        (Decimal("0.66"), Decimal("0.67")),
        (Decimal("0.50"), Decimal("0.50")),
    }
    assert all(
        call.get("companion_disagreement_diagnostic_only") is True
        for call in calls
        if call.get("entry_thresholds") is not None
    )
