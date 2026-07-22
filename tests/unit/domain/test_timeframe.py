from datetime import timedelta

from gemini_trading.domain.timeframe import Timeframe


def test_timeframe_set_is_curated() -> None:
    assert {item.value for item in Timeframe} == {
        "1m",
        "5m",
        "15m",
        "1h",
        "4h",
        "1d",
        "1w",
    }


def test_timeframe_durations_are_exact() -> None:
    assert Timeframe.M1.duration == timedelta(minutes=1)
    assert Timeframe.M5.duration == timedelta(minutes=5)
    assert Timeframe.M15.duration == timedelta(minutes=15)
    assert Timeframe.H1.duration == timedelta(hours=1)
    assert Timeframe.H4.duration == timedelta(hours=4)
    assert Timeframe.D1.duration == timedelta(days=1)
    assert Timeframe.W1.duration == timedelta(days=7)
