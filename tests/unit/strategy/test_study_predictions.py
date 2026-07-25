"""Regression tests for phase-window baseline schedules."""

from gemini_trading.strategy.baselines import BaselineAction
from gemini_trading.strategy.study_predictions import baseline_events
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
