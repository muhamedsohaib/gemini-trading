"""Regression tests for phase-window study schedules."""

from decimal import Decimal
from types import SimpleNamespace
from typing import cast

from gemini_trading.strategy.baselines import BaselineAction
from gemini_trading.strategy.contracts import RegimeState, SpecialistKind
from gemini_trading.strategy.features import FeatureMatrix
from gemini_trading.strategy.study_predictions import (
    PredictionBundle,
    baseline_events,
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
