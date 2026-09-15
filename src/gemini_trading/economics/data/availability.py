"""Evidenced historical availability contracts for economic publications."""

from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from typing import Final

from gemini_trading.economics.data.observation import (
    EconomicChronologyError,
    EconomicDataError,
)

ECONOMIC_AVAILABILITY_EVIDENCE_SCHEMA_V1: Final[str] = "economic-availability-evidence-v1"


class AvailabilityPrecision(StrEnum):
    EXACT_SECOND = "EXACT_SECOND"
    EXACT_MINUTE = "EXACT_MINUTE"
    EXACT_HOUR = "EXACT_HOUR"
    DATE_ONLY = "DATE_ONLY"
    INFERRED_INTERVAL = "INFERRED_INTERVAL"
    UNKNOWN = "UNKNOWN"


class AvailabilityStatus(StrEnum):
    RESOLVED = "RESOLVED"
    CONFLICTED = "CONFLICTED"
    UNKNOWN = "UNKNOWN"


def _require_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise EconomicChronologyError(f"{field_name} must be timezone-aware")


def _require_sha256(value: str) -> None:
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise EconomicDataError("raw_sha256 must be lowercase SHA-256 hex")


@dataclass(frozen=True, slots=True)
class EconomicAvailabilityEvidence:
    schema_version: str
    evidence_id: str
    publication_event_id: str
    source_id: str
    consumer_class: str
    availability_channel: str
    availability_precision: AvailabilityPrecision
    available_time: datetime | None
    available_date: date | None
    interval_start: datetime | None
    interval_end: datetime | None
    source_timezone: str | None
    source_utc_offset_minutes: int | None
    retrieved_time: datetime
    raw_sha256: str

    def __post_init__(self) -> None:
        if self.schema_version != ECONOMIC_AVAILABILITY_EVIDENCE_SCHEMA_V1:
            raise EconomicDataError("unsupported economic availability evidence schema")
        for name, value in (
            ("evidence_id", self.evidence_id),
            ("publication_event_id", self.publication_event_id),
            ("source_id", self.source_id),
            ("consumer_class", self.consumer_class),
            ("availability_channel", self.availability_channel),
        ):
            if not value.strip():
                raise EconomicDataError(f"{name} must not be empty")
        _require_aware(self.retrieved_time, "retrieved_time")
        _require_sha256(self.raw_sha256)
        if self.source_timezone is not None and not self.source_timezone.strip():
            raise EconomicDataError("source_timezone must not be blank")
        if (
            self.source_utc_offset_minutes is not None
            and not -24 * 60 <= self.source_utc_offset_minutes <= 24 * 60
        ):
            raise EconomicDataError("source_utc_offset_minutes is out of range")
        self._validate_precision()

    def _validate_precision(self) -> None:
        precision = self.availability_precision
        exact = {
            AvailabilityPrecision.EXACT_SECOND,
            AvailabilityPrecision.EXACT_MINUTE,
            AvailabilityPrecision.EXACT_HOUR,
        }
        if precision in exact:
            if self.available_time is None or self.available_date is not None:
                raise EconomicDataError(f"{precision.value} requires only available_time")
            if self.interval_start is not None or self.interval_end is not None:
                raise EconomicDataError(f"{precision.value} cannot carry interval bounds")
            _require_aware(self.available_time, "available_time")
            if precision is AvailabilityPrecision.EXACT_HOUR and (
                self.available_time.minute
                or self.available_time.second
                or self.available_time.microsecond
            ):
                raise EconomicDataError("EXACT_HOUR available_time exceeds evidenced precision")
            if precision is AvailabilityPrecision.EXACT_MINUTE and (
                self.available_time.second or self.available_time.microsecond
            ):
                raise EconomicDataError("EXACT_MINUTE available_time exceeds evidenced precision")
            if precision is AvailabilityPrecision.EXACT_SECOND and self.available_time.microsecond:
                raise EconomicDataError("EXACT_SECOND available_time exceeds evidenced precision")
            if self.retrieved_time < self.available_time:
                raise EconomicChronologyError("retrieved_time precedes evidenced available_time")
            return

        if precision is AvailabilityPrecision.DATE_ONLY:
            if self.available_date is None or self.available_time is not None:
                raise EconomicDataError("DATE_ONLY requires available_date and no available_time")
            if self.interval_start is not None or self.interval_end is not None:
                raise EconomicDataError("DATE_ONLY cannot carry interval bounds")
            return

        if precision is AvailabilityPrecision.INFERRED_INTERVAL:
            if self.available_time is not None or self.available_date is not None:
                raise EconomicDataError("INFERRED_INTERVAL cannot carry exact/date availability")
            if self.interval_start is None or self.interval_end is None:
                raise EconomicDataError("INFERRED_INTERVAL requires interval bounds")
            _require_aware(self.interval_start, "interval_start")
            _require_aware(self.interval_end, "interval_end")
            if self.interval_end < self.interval_start:
                raise EconomicChronologyError("availability interval end precedes start")
            if self.retrieved_time < self.interval_end:
                raise EconomicChronologyError("retrieved_time precedes availability interval end")
            return

        if precision is AvailabilityPrecision.UNKNOWN:
            if any(
                value is not None
                for value in (
                    self.available_time,
                    self.available_date,
                    self.interval_start,
                    self.interval_end,
                )
            ):
                raise EconomicDataError("UNKNOWN availability cannot carry fabricated timing")
            return

        raise EconomicDataError("unsupported availability precision")


__all__ = [
    "ECONOMIC_AVAILABILITY_EVIDENCE_SCHEMA_V1",
    "AvailabilityPrecision",
    "AvailabilityStatus",
    "EconomicAvailabilityEvidence",
]
