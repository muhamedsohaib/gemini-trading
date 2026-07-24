"""RED tests for the locked Candidate v0.1 baseline suite."""

from dataclasses import replace
from decimal import Decimal

from gemini_trading.strategy.baselines import BaselineSuite, build_baseline_schedules
from strategy_fixture_support import rising_candles


def test_baseline_ids_are_locked() -> None:
    assert tuple(item.strategy_id for item in BaselineSuite.locked_v0_1()) == (
        "cash.v1",
        "buy_hold.v1",
        "ema_20_50.v1",
        "donchian_20_10.v1",
        "mean_reversion_z24.v1",
    )


def test_cash_never_enters_and_buy_hold_enters_once() -> None:
    schedules = build_baseline_schedules(rising_candles(80))

    assert all(action.value == "cash" for action in schedules["cash.v1"].actions)
    buy_hold = schedules["buy_hold.v1"]
    assert sum(action.value == "enter_long" for action in buy_hold.actions) == 1
    assert all(action.value != "exit_to_cash" for action in buy_hold.actions)


def test_future_mutation_cannot_change_prior_baseline_actions() -> None:
    candles = rising_candles(100)
    original = build_baseline_schedules(candles)
    changed = (
        *candles[:-1],
        replace(
            candles[-1],
            open=Decimal("999999"),
            high=Decimal("1000000"),
            low=Decimal("999000"),
            close=Decimal("999500"),
        ),
    )
    mutated = build_baseline_schedules(changed)

    for strategy_id in original:
        assert original[strategy_id].actions[:-1] == mutated[strategy_id].actions[:-1]
