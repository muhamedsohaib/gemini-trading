"""Regression tests for phase-window study schedules."""

from decimal import Decimal
from types import SimpleNamespace
from typing import cast

import pytest

from gemini_trading.domain.candle import Candle
from gemini_trading.strategy import study_predictions as study_predictions_module
from gemini_trading.strategy.arbitration import ArbitrationInput
from gemini_trading.strategy.baselines import BaselineAction
from gemini_trading.strategy.contracts import RegimeState, SpecialistKind, StrategyAction
from gemini_trading.strategy.features import FeatureMatrix
from gemini_trading.strategy.labels import LabelPolicy
from gemini_trading.strategy.policy import CandidatePolicy
from gemini_trading.strategy.study_predictions import (
    PredictionBundle,
    baseline_events,
    candidate_events,
    threshold_events,
)
from gemini_trading.strategy.study_strategy import ScheduledAction


def test_buy_hold_window_enters_when_schedule_is_already_long() -> None:
    actions = (
        BaselineAction.ENTER_LONG,
        BaselineAction.HOLD_LONG,
        BaselineAction.HOLD_LONG,
        BaselineAction.HOLD_LONG,
    )

    events = baseline_events(actions=actions, indices=(2, 3))

    assert events == (
        (2, ScheduledAction.ENTER_LONG),
        (3, ScheduledAction.EXIT_TO_CASH),
    )


def test_baseline_schedule_resets_to_cash_before_decision_discontinuity() -> None:
    actions = tuple(BaselineAction.HOLD_LONG for _ in range(7))

    events = baseline_events(actions=actions, indices=(0, 1, 5, 6))

    assert events == (
        (0, ScheduledAction.ENTER_LONG),
        (1, ScheduledAction.EXIT_TO_CASH),
        (5, ScheduledAction.ENTER_LONG),
        (6, ScheduledAction.EXIT_TO_CASH),
    )


def test_threshold_schedule_resets_to_cash_before_prediction_discontinuity() -> None:
    predictions = tuple(
        SimpleNamespace(
            candle_index=index,
            trend_probability=Decimal("0.70"),
            mean_reversion_probability=Decimal("0.50"),
            regime=SimpleNamespace(state=RegimeState.TRENDING),
        )
        for index in (0, 1, 5, 6)
    )
    bundle = cast(PredictionBundle, SimpleNamespace(predictions=predictions))

    events = threshold_events(
        bundle,
        specialist=SpecialistKind.TREND,
        matrix=cast(FeatureMatrix, object()),
    )

    assert events == (
        (0, ScheduledAction.ENTER_LONG),
        (1, ScheduledAction.EXIT_TO_CASH),
        (5, ScheduledAction.ENTER_LONG),
        (6, ScheduledAction.EXIT_TO_CASH),
    )


def test_candidate_schedule_resets_position_state_before_prediction_discontinuity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeArbiter:
        def __init__(self, _policy: CandidatePolicy) -> None:
            pass

        def decide(self, source: ArbitrationInput) -> SimpleNamespace:
            if source.currently_long:
                action = StrategyAction.REMAIN_LONG
            else:
                action = StrategyAction.ENTER_LONG
            return SimpleNamespace(
                action=action,
                active_specialist=SpecialistKind.TREND,
                hold_age=1,
                cooldown_remaining=0,
                indeterminate_streak=0,
                trailing_stop=Decimal("90"),
            )

    class FakeMatrix:
        def value_for(self, _index: int, name: str) -> Decimal:
            if name == "atr_24":
                return Decimal("1")
            return Decimal("0")

    predictions = tuple(
        SimpleNamespace(
            candle_index=index,
            trend_probability=Decimal("0.70"),
            mean_reversion_probability=Decimal("0.50"),
            trend_expected_return=Decimal("0.01"),
            mean_reversion_expected_return=Decimal("0.00"),
            regime=SimpleNamespace(state=RegimeState.TRENDING),
        )
        for index in (0, 1, 5, 6)
    )
    candles = tuple(SimpleNamespace(close=Decimal("100"), low=Decimal("99")) for _ in range(7))
    bundle = cast(PredictionBundle, SimpleNamespace(predictions=predictions))
    matrix = cast(FeatureMatrix, FakeMatrix())
    label_policy = cast(LabelPolicy, SimpleNamespace(hurdle_bps=Decimal("0")))

    monkeypatch.setattr(study_predictions_module, "MultiModelArbiter", FakeArbiter)

    events = candidate_events(
        bundle,
        candles=cast(tuple[Candle, ...], candles),
        matrix=matrix,
        label_policy=label_policy,
        policy=CandidatePolicy.locked_v0_2(),
    )

    assert events == (
        (0, ScheduledAction.ENTER_LONG),
        (1, ScheduledAction.EXIT_TO_CASH),
        (5, ScheduledAction.ENTER_LONG),
        (6, ScheduledAction.EXIT_TO_CASH),
    )


def test_baseline_schedule_flattens_before_verified_segment_boundary() -> None:
    actions = tuple(BaselineAction.HOLD_LONG for _ in range(5))

    events = baseline_events(
        actions=actions,
        indices=(0, 1, 2, 3, 4),
        segment_boundary_indices=(3,),
        latency_bars=0,
    )

    assert events == (
        (0, ScheduledAction.ENTER_LONG),
        (1, ScheduledAction.EXIT_TO_CASH),
        (3, ScheduledAction.ENTER_LONG),
        (4, ScheduledAction.EXIT_TO_CASH),
    )


def test_candidate_schedule_resets_before_verified_segment_boundary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeArbiter:
        def __init__(self, _policy: CandidatePolicy) -> None:
            pass

        def decide(self, source: ArbitrationInput, _overlay: object = None) -> SimpleNamespace:
            action = StrategyAction.REMAIN_LONG if source.currently_long else StrategyAction.ENTER_LONG
            return SimpleNamespace(
                action=action,
                active_specialist=SpecialistKind.TREND,
                hold_age=1,
                cooldown_remaining=0,
                indeterminate_streak=0,
                trailing_stop=Decimal("90"),
            )

    class FakeMatrix:
        def value_for(self, _index: int, name: str) -> Decimal:
            if name == "atr_24":
                return Decimal("1")
            return Decimal("0")

    predictions = tuple(
        SimpleNamespace(
            candle_index=index,
            trend_probability=Decimal("0.70"),
            mean_reversion_probability=Decimal("0.50"),
            trend_expected_return=Decimal("0.01"),
            mean_reversion_expected_return=Decimal("0.00"),
            regime=SimpleNamespace(state=RegimeState.TRENDING),
        )
        for index in range(5)
    )
    candles = tuple(SimpleNamespace(close=Decimal("100"), low=Decimal("99")) for _ in range(5))
    bundle = cast(PredictionBundle, SimpleNamespace(predictions=predictions))
    matrix = cast(FeatureMatrix, FakeMatrix())
    label_policy = cast(LabelPolicy, SimpleNamespace(hurdle_bps=Decimal("0")))

    monkeypatch.setattr(study_predictions_module, "MultiModelArbiter", FakeArbiter)

    events = candidate_events(
        bundle,
        candles=cast(tuple[Candle, ...], candles),
        matrix=matrix,
        label_policy=label_policy,
        policy=CandidatePolicy.locked_v0_3(),
        entry_thresholds={
            SpecialistKind.TREND: Decimal("0.50"),
            SpecialistKind.MEAN_REVERSION: Decimal("0.50"),
        },
        companion_disagreement_diagnostic_only=True,
        segment_boundary_indices=(3,),
        latency_bars=0,
    )

    assert events == (
        (0, ScheduledAction.ENTER_LONG),
        (1, ScheduledAction.EXIT_TO_CASH),
        (3, ScheduledAction.ENTER_LONG),
        (4, ScheduledAction.EXIT_TO_CASH),
    )
