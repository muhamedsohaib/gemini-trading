"""Immutable candle candidate contract."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from gemini_trading.domain.instrument import Instrument
from gemini_trading.domain.time import require_utc
from gemini_trading.domain.timeframe import Timeframe


@dataclass(frozen=True, slots=True)
class Candle:
    """Normalized market-data candle with explicit completion and provenance state."""

    instrument: Instrument
    timeframe: Timeframe
    open_time: datetime
    close_time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    completed: bool
    source_provider: str

    def __post_init__(self) -> None:
        require_utc(self.open_time, "open_time")
        require_utc(self.close_time, "close_time")

        if self.close_time <= self.open_time:
            raise ValueError("close_time must be later than open_time")
        if self.open_time.microsecond % 1000 != 0:
            raise ValueError("open_time must be millisecond-aligned")
        if self.close_time.microsecond % 1000 != 0:
            raise ValueError("close_time must be millisecond-aligned")

        for field_name, value in (
            ("open", self.open),
            ("high", self.high),
            ("low", self.low),
            ("close", self.close),
            ("volume", self.volume),
        ):
            if not value.is_finite():
                raise ValueError(f"{field_name} must be finite")

        source_provider = self.source_provider.strip()
        if not source_provider:
            raise ValueError("source_provider must not be empty")
        object.__setattr__(self, "source_provider", source_provider)
