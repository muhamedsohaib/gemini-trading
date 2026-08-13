"""Candidate v0.3 prediction-context and schedule contract tests."""

from __future__ import annotations

import importlib
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, cast

import pytest

from gemini_trading.domain.candle import Candle
from gemini_trading.research.serialization import canonical_json_bytes
from gemini_trading.strategy.contracts import RegimeState, SpecialistKind
from gemini_trading.strategy.determinism import TrendDeterminismReceipt
from gemini_trading.strategy.features import (
    FeatureDefinition,
    FeatureGroup,
    FeatureMatrix,
    FeatureRow,
)
from gemini_trading.strategy.labels import LabelPolicy, LabelVector
from gemini_trading.strategy.policy import CandidatePolicy
from gemini_trading.strategy.study import StudyPhase
from gemini_trading.strategy.study_predictions import PredictionBundle, candidate_events
from gemini_trading.strategy.study_strategy import ScheduledAction

_CONTEXT_FEATURES = (
    "trend_strength_12_42_atr24",
    "volatility_ratio_6_42",
    "true_range_ratio_24",
    "ema_12_42_sign_streak",
    "close_zscore_24",
    "drawdown_from_high_24",
)


def _v03_module() -> Any:
    return importlib.import_module("gemini_trading.strategy.v0_3_predictions")


def _context_matrix() -> FeatureMatrix:
    definitions = tuple(
        FeatureDefinition(
            name=name,
            version="v1",
            group=FeatureGroup.REGIME,
            lookback_candles=1,
        )
        for name in _CONTEXT_FEATURES
    )
    rows: list[FeatureRow] = []
    start = datetime(2024, 1, 1, tzinfo=UTC)
    for index in range(80):
        if index < 40:
            values = (
                Decimal("1.2"),
                Decimal("1.0"),
                Decimal("1.0"),
                Decimal("3"),
                Decimal("0"),
                Decimal("0"),
            )
        else:
            values = (
                Decimal("0.2"),
                Decimal("1.0"),
                Decimal("1.0"),
                Decimal("0"),
                Decimal("-1.0"),
                Decimal("0.03"),
            )
        rows.append(
            FeatureRow(
                candle_index=index,
                candle_open_time=start + timedelta(hours=4 * index),
                values=values,
            )
        )
    return FeatureMatrix(
        schema_version="v0.3-prediction-context-test-v1",
        definitions=definitions,
        rows=tuple(rows),
    )


def _receipt() -> TrendDeterminismReceipt:
    digest = "0" * 64
    return TrendDeterminismReceipt(
        schema_version="candidate-v0.2-trend-determinism-v1",
        fold_number=1,
        iteration_count=10,
        first_model_sha256=digest,
        second_model_sha256=digest,
        first_bundle_sha256=digest,
        second_bundle_sha256=digest,
        exact_match=True,
    )


def test_v0_3_context_reuses_unchanged_verified_bundle_and_builds_six_thresholds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _v03_module()
    context_type = getattr(module, "V03PredictionContext", None)
    fit_context = getattr(module, "fit_v0_3_prediction_context", None)
    assert context_type is not None, "v0_3_predictions must define V03PredictionContext"
    assert fit_context is not None, "v0_3_predictions must define fit_v0_3_prediction_context"

    trend_platt = object()
    mean_platt = object()
    bundle = cast(
        PredictionBundle,
        SimpleNamespace(
            trend_model=SimpleNamespace(feature_names=()),
            mean_reversion_model=SimpleNamespace(feature_names=()),
            trend_platt=trend_platt,
            mean_reversion_platt=mean_platt,
            predictions=(),
        ),
    )
    receipt = _receipt()
    observed_policies: list[CandidatePolicy] = []

    def fake_fit_verified_prediction_bundle(**kwargs: object):
        policy = cast(CandidatePolicy, kwargs["policy"])
        observed_policies.append(policy)
        assert policy == CandidatePolicy.locked_v0_2()
        return bundle, receipt

    monkeypatch.setattr(
        module,
        "fit_verified_prediction_bundle",
        fake_fit_verified_prediction_bundle,
    )

    def fake_predict_raw(_model: object, _values: object) -> float:
        return 0.0

    def fake_apply_platt(_platt: object, _score: float) -> Decimal:
        return Decimal("0.60")

    monkeypatch.setattr(module, "predict_raw", fake_predict_raw)
    monkeypatch.setattr(module, "apply_platt", fake_apply_platt)

    kwargs = {
        "phase": StudyPhase.DEVELOPMENT,
        "fold_number": 1,
        "matrix": _context_matrix(),
        "labels": cast(LabelVector, object()),
        "policy": CandidatePolicy.locked_v0_3(),
        "training_indices": (0,),
        "calibration_indices": tuple(range(80)),
        "prediction_indices": (79,),
    }
    first = fit_context(**kwargs)
    second = fit_context(**kwargs)

    assert isinstance(first, context_type)
    assert first.bundle is bundle
    assert first.determinism_receipt is receipt
    assert observed_policies == [CandidatePolicy.locked_v0_2(), CandidatePolicy.locked_v0_2()]
    artifacts = {
        (artifact.specialist, artifact.percentile): artifact
        for artifact in first.threshold_artifacts
    }
    assert set(artifacts) == {
        (specialist, percentile)
        for specialist in (SpecialistKind.TREND, SpecialistKind.MEAN_REVERSION)
        for percentile in (Decimal("0.70"), Decimal("0.75"), Decimal("0.80"))
    }
    assert all(artifact.effective_threshold == Decimal("0.60") for artifact in artifacts.values())
    assert first.effective_thresholds(Decimal("0.75")) == {
        SpecialistKind.TREND: Decimal("0.60"),
        SpecialistKind.MEAN_REVERSION: Decimal("0.60"),
    }
    first_bytes = canonical_json_bytes(
        {"threshold_artifacts": [asdict(item) for item in first.threshold_artifacts]}
    )
    second_bytes = canonical_json_bytes(
        {"threshold_artifacts": [asdict(item) for item in second.threshold_artifacts]}
    )
    assert first_bytes == second_bytes


class _ScheduleMatrix:
    def __init__(self, *, stretched: bool = False) -> None:
        self.stretched = stretched

    def value_for(self, _index: int, name: str) -> Decimal:
        if name == "atr_24":
            return Decimal("1")
        if name == "close_zscore_24":
            return Decimal("-1") if self.stretched else Decimal("0")
        if name == "drawdown_from_high_24":
            return Decimal("0.03") if self.stretched else Decimal("0")
        return Decimal("0")


def _bundle(
    indices: tuple[int, ...],
    *,
    regime: RegimeState = RegimeState.TRENDING,
    trend_probability: Decimal = Decimal("0.70"),
    mean_probability: Decimal = Decimal("0.50"),
    trend_expected: Decimal = Decimal("0.008"),
    mean_expected: Decimal = Decimal("0.008"),
) -> PredictionBundle:
    predictions = tuple(
        SimpleNamespace(
            candle_index=index,
            trend_probability=trend_probability,
            mean_reversion_probability=mean_probability,
            trend_expected_return=trend_expected,
            mean_reversion_expected_return=mean_expected,
            regime=SimpleNamespace(state=regime),
        )
        for index in indices
    )
    return cast(PredictionBundle, SimpleNamespace(predictions=predictions))


def _candles(max_index: int) -> tuple[Candle, ...]:
    rows = tuple(
        SimpleNamespace(close=Decimal("100"), low=Decimal("99")) for _ in range(max_index + 1)
    )
    return cast(tuple[Candle, ...], rows)


def _label_policy() -> LabelPolicy:
    return cast(LabelPolicy, SimpleNamespace(hurdle_bps=Decimal("60")))


def _thresholds(value: str = "0.58") -> dict[SpecialistKind, Decimal]:
    threshold = Decimal(value)
    return {
        SpecialistKind.TREND: threshold,
        SpecialistKind.MEAN_REVERSION: threshold,
    }


def test_q75_schedule_can_admit_probability_rejected_by_fixed_v0_2_entry() -> None:
    bundle = _bundle(
        (0, 1),
        trend_probability=Decimal("0.58"),
        mean_probability=Decimal("0.50"),
    )
    legacy = candidate_events(
        bundle,
        candles=_candles(1),
        matrix=cast(FeatureMatrix, _ScheduleMatrix()),
        label_policy=_label_policy(),
        policy=CandidatePolicy.locked_v0_3(),
    )
    v03 = candidate_events(
        bundle,
        candles=_candles(1),
        matrix=cast(FeatureMatrix, _ScheduleMatrix()),
        label_policy=_label_policy(),
        policy=CandidatePolicy.locked_v0_3(),
        entry_thresholds=_thresholds(),
        companion_disagreement_diagnostic_only=True,
    )

    assert legacy == ()
    assert v03 == (
        (0, ScheduledAction.ENTER_LONG),
        (1, ScheduledAction.EXIT_TO_CASH),
    )


def test_v0_3_schedule_makes_companion_and_disagreement_diagnostic_only() -> None:
    bundle = _bundle(
        (0, 1),
        trend_probability=Decimal("0.70"),
        mean_probability=Decimal("0.20"),
    )
    enforced = candidate_events(
        bundle,
        candles=_candles(1),
        matrix=cast(FeatureMatrix, _ScheduleMatrix()),
        label_policy=_label_policy(),
        policy=CandidatePolicy.locked_v0_3(),
        entry_thresholds=_thresholds(),
    )
    diagnostic = candidate_events(
        bundle,
        candles=_candles(1),
        matrix=cast(FeatureMatrix, _ScheduleMatrix()),
        label_policy=_label_policy(),
        policy=CandidatePolicy.locked_v0_3(),
        entry_thresholds=_thresholds(),
        companion_disagreement_diagnostic_only=True,
    )

    assert enforced == ()
    assert diagnostic[0] == (0, ScheduledAction.ENTER_LONG)


def test_v0_3_schedule_keeps_expected_edge_as_a_hard_veto() -> None:
    bundle = _bundle((0, 1), trend_expected=Decimal("0.0070"))
    events = candidate_events(
        bundle,
        candles=_candles(1),
        matrix=cast(FeatureMatrix, _ScheduleMatrix()),
        label_policy=_label_policy(),
        policy=CandidatePolicy.locked_v0_3(),
        entry_thresholds=_thresholds(),
        companion_disagreement_diagnostic_only=True,
    )

    assert events == ()


def test_v0_3_mean_reversion_still_requires_ranging_stretch() -> None:
    bundle = _bundle(
        (0, 1),
        regime=RegimeState.RANGING,
        trend_probability=Decimal("0.50"),
        mean_probability=Decimal("0.70"),
    )
    rejected = candidate_events(
        bundle,
        candles=_candles(1),
        matrix=cast(FeatureMatrix, _ScheduleMatrix(stretched=False)),
        label_policy=_label_policy(),
        policy=CandidatePolicy.locked_v0_3(),
        entry_thresholds=_thresholds(),
        companion_disagreement_diagnostic_only=True,
    )
    accepted = candidate_events(
        bundle,
        candles=_candles(1),
        matrix=cast(FeatureMatrix, _ScheduleMatrix(stretched=True)),
        label_policy=_label_policy(),
        policy=CandidatePolicy.locked_v0_3(),
        entry_thresholds=_thresholds(),
        companion_disagreement_diagnostic_only=True,
    )

    assert rejected == ()
    assert accepted[0] == (0, ScheduledAction.ENTER_LONG)


def test_v0_3_schedule_preserves_segment_gap_cash_reset() -> None:
    events = candidate_events(
        _bundle((0, 1, 5, 6)),
        candles=_candles(6),
        matrix=cast(FeatureMatrix, _ScheduleMatrix()),
        label_policy=_label_policy(),
        policy=CandidatePolicy.locked_v0_3(),
        entry_thresholds=_thresholds(),
        companion_disagreement_diagnostic_only=True,
    )

    assert events == (
        (0, ScheduledAction.ENTER_LONG),
        (1, ScheduledAction.EXIT_TO_CASH),
        (5, ScheduledAction.ENTER_LONG),
        (6, ScheduledAction.EXIT_TO_CASH),
    )


def test_candidate_events_without_v0_3_options_keeps_v0_2_schedule() -> None:
    events = candidate_events(
        _bundle((0, 1)),
        candles=_candles(1),
        matrix=cast(FeatureMatrix, _ScheduleMatrix()),
        label_policy=_label_policy(),
        policy=CandidatePolicy.locked_v0_2(),
    )

    assert events == (
        (0, ScheduledAction.ENTER_LONG),
        (1, ScheduledAction.EXIT_TO_CASH),
    )
