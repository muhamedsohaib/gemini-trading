"""Immutable point-in-time economic observation contract."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Final

ECONOMIC_OBSERVATION_SCHEMA_V1: Final[str] = "economic-observation-v1"


class EconomicDataError(ValueError):
    """Base error for economic data contract violations."""


class EconomicChronologyError(EconomicDataError):
    """Raised when point-in-time chronology is invalid."""


@dataclass(frozen=True, slots=True)
class EconomicObservation:
    """One immutable value with explicit observation and availability chronology."""

    schema_version: str
    series_id: str
    observation_time: datetime
    available_time: datetime
    vintage_time: datetime | None
    retrieved_time: datetime
    source_id: str
    value: Decimal
    unit: str
    scale: Decimal
    frequency: str
    release_id: str | None
    raw_sha256: str

    def __post_init__(self) -> None:
        if self.schema_version != ECONOMIC_OBSERVATION_SCHEMA_V1:
            raise EconomicDataError("unsupported economic observation schema")

        for name, value in (
            ("series_id", self.series_id),
            ("source_id", self.source_id),
            ("unit", self.unit),
            ("frequency", self.frequency),
        ):
            if not value.strip():
                raise EconomicDataError(f"{name} must not be empty")

        for name, value in (
            ("observation_time", self.observation_time),
            ("available_time", self.available_time),
            ("retrieved_time", self.retrieved_time),
        ):
            if value.tzinfo is None or value.utcoffset() is None:
                raise EconomicChronologyError(f"{name} must be timezone-aware")

        if self.vintage_time is not None and (
            self.vintage_time.tzinfo is None or self.vintage_time.utcoffset() is None
        ):
            raise EconomicChronologyError("vintage_time must be timezone-aware")

        if self.available_time < self.observation_time:
            raise EconomicChronologyError("available_time precedes observation_time")
        if self.retrieved_time < self.available_time:
            raise EconomicChronologyError("retrieved_time precedes available_time")
        if self.vintage_time is not None and self.vintage_time > self.retrieved_time:
            raise EconomicChronologyError("vintage_time exceeds retrieved_time")

        if not self.value.is_finite():
            raise EconomicDataError("value must be finite")
        if not self.scale.is_finite() or self.scale == 0:
            raise EconomicDataError("scale must be finite and nonzero")

        if len(self.raw_sha256) != 64 or any(
            character not in "0123456789abcdef" for character in self.raw_sha256
        ):
            raise EconomicDataError("raw_sha256 must be lowercase SHA-256 hex")
