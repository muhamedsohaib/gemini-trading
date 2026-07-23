"""Approved market-data intervals."""

from datetime import timedelta
from enum import StrEnum


class Timeframe(StrEnum):
    """Curated interval set supported by the first market-data milestone."""

    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    H1 = "1h"
    H4 = "4h"
    D1 = "1d"
    W1 = "1w"

    @property
    def duration(self) -> timedelta:
        """Return the exact wall-clock duration represented by the interval."""

        durations = {
            Timeframe.M1: timedelta(minutes=1),
            Timeframe.M5: timedelta(minutes=5),
            Timeframe.M15: timedelta(minutes=15),
            Timeframe.H1: timedelta(hours=1),
            Timeframe.H4: timedelta(hours=4),
            Timeframe.D1: timedelta(days=1),
            Timeframe.W1: timedelta(days=7),
        }
        return durations[self]
