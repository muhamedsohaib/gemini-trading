"""First-class economic publication event contracts."""

from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from typing import Final

from gemini_trading.economics.data.availability import (
    AvailabilityPrecision,
    AvailabilityStatus,
)
from gemini_trading.economics.data.observation import (
    EconomicChronologyError,
    EconomicDataError,
)

ECONOMIC_PUBLICATION_EVENT_SCHEMA_V1: Final[str] = "economic-publication-event-v1"


class PublicationSequence(StrEnum):
    INITIAL = "INITIAL"
    ADVANCE = "ADVANCE"
    SECOND = "SECOND"
    THIRD = "THIRD"
    ROUTINE_REVISION = "ROUTINE_REVISION"
    SEASONAL_REVISION = "SEASONAL_REVISION"
    BENCHMARK_REVISION = "BENCHMARK_REVISION"
    METHODOLOGY_REVISION = "METHODOLOGY_REVISION"
    CORRECTION = "CORRECTION"
    OTHER = "OTHER"


class RevisionClass(StrEnum):
    INITIAL = "INITIAL"
    ROUTINE_REVISION = "ROUTINE_REVISION"
    SEASONAL_REVISION = "SEASONAL_REVISION"
    BENCHMARK_REVISION = "BENCHMARK_REVISION"
    METHODOLOGY_REVISION = "METHODOLOGY_REVISION"
    CORRECTION = "CORRECTION"
    OTHER = "OTHER"


def _require_aware_optional(value: datetime | None, field_name: str) -> None:
    if value is not None and (value.tzinfo is None or value.utcoffset() is None):
        raise EconomicChronologyError(f"{field_name} must be timezone-aware")


def _require_nonblank_optional(value: str | None, field_name: str) -> None:
    if value is not None and not value.strip():
        raise EconomicDataError(f"{field_name} must not be blank")


@dataclass(frozen=True, slots=True)
class EconomicPublicationEvent:
    schema_version: str
    event_id: str
    publisher: str
    source_id: str
    event_type: str
    scheduled_time: datetime | None
    published_time: datetime | None
    available_time: datetime | None
    available_date: date | None
    consumer_class: str
    availability_channel: str
    availability_precision: AvailabilityPrecision
    availability_evidence_ids: tuple[str, ...]
    availability_evidence_id: str | None
    availability_status: AvailabilityStatus
    publication_sequence: PublicationSequence
    revision_class: RevisionClass
    provider_native_publication_sequence: str | None
    provider_native_event_id: str | None
    provider_native_source_id: str | None
    source_version: str | None
    predecessor_event_id: str | None
    retrieved_time: datetime
    raw_sha256: str

    def __post_init__(self) -> None:
        if self.schema_version != ECONOMIC_PUBLICATION_EVENT_SCHEMA_V1:
            raise EconomicDataError("unsupported economic publication event schema")
        for name, value in (
            ("event_id", self.event_id),
            ("publisher", self.publisher),
            ("source_id", self.source_id),
            ("event_type", self.event_type),
            ("consumer_class", self.consumer_class),
            ("availability_channel", self.availability_channel),
        ):
            if not value.strip():
                raise EconomicDataError(f"{name} must not be empty")
        _require_aware_optional(self.scheduled_time, "scheduled_time")
        _require_aware_optional(self.published_time, "published_time")
        _require_aware_optional(self.available_time, "available_time")
        _require_aware_optional(self.retrieved_time, "retrieved_time")
        if self.retrieved_time.tzinfo is None or self.retrieved_time.utcoffset() is None:
            raise EconomicChronologyError("retrieved_time must be timezone-aware")
        if self.published_time is not None and self.retrieved_time < self.published_time:
            raise EconomicChronologyError("retrieved_time precedes published_time")
        if len(self.raw_sha256) != 64 or any(
            character not in "0123456789abcdef" for character in self.raw_sha256
        ):
            raise EconomicDataError("raw_sha256 must be lowercase SHA-256 hex")
        for field_name, value in (
            ("provider_native_publication_sequence", self.provider_native_publication_sequence),
            ("provider_native_event_id", self.provider_native_event_id),
            ("provider_native_source_id", self.provider_native_source_id),
            ("source_version", self.source_version),
            ("predecessor_event_id", self.predecessor_event_id),
        ):
            _require_nonblank_optional(value, field_name)
        if len(set(self.availability_evidence_ids)) != len(self.availability_evidence_ids):
            raise EconomicDataError("duplicate availability evidence identity")
        if any(not evidence_id.strip() for evidence_id in self.availability_evidence_ids):
            raise EconomicDataError("availability_evidence_ids must not contain blanks")
        self._validate_availability()

    def _validate_availability(self) -> None:
        if self.availability_status is AvailabilityStatus.RESOLVED:
            if self.availability_evidence_id is None:
                raise EconomicDataError("RESOLVED event requires availability_evidence_id")
            if self.availability_evidence_id not in self.availability_evidence_ids:
                raise EconomicDataError("availability_evidence_id is not declared")
            if self.availability_precision in {
                AvailabilityPrecision.EXACT_SECOND,
                AvailabilityPrecision.EXACT_MINUTE,
                AvailabilityPrecision.EXACT_HOUR,
            }:
                if self.available_time is None or self.available_date is not None:
                    raise EconomicDataError("RESOLVED exact event requires available_time only")
                if self.retrieved_time < self.available_time:
                    raise EconomicChronologyError("retrieved_time precedes available_time")
                return
            if self.availability_precision is AvailabilityPrecision.DATE_ONLY:
                if self.available_date is None or self.available_time is not None:
                    raise EconomicDataError("RESOLVED DATE_ONLY event requires available_date only")
                return
            raise EconomicDataError(
                "RESOLVED event requires exact or DATE_ONLY admitted availability"
            )

        if self.availability_status is AvailabilityStatus.CONFLICTED:
            if self.available_time is not None or self.available_date is not None:
                raise EconomicDataError("CONFLICTED event cannot carry admitted availability")
            if self.availability_evidence_id is not None:
                raise EconomicDataError("CONFLICTED event cannot select availability_evidence_id")
            return

        if self.availability_status is AvailabilityStatus.UNKNOWN:
            if self.available_time is not None or self.available_date is not None:
                raise EconomicDataError("UNKNOWN event cannot carry admitted availability")
            if self.availability_evidence_id is not None:
                raise EconomicDataError("UNKNOWN event cannot select availability_evidence_id")
            return

        raise EconomicDataError("unsupported availability status")


__all__ = [
    "ECONOMIC_PUBLICATION_EVENT_SCHEMA_V1",
    "EconomicPublicationEvent",
    "PublicationSequence",
    "RevisionClass",
]
