"""Versioned point-in-time economic observation contract for real provider evidence."""

import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from hashlib import sha256
from typing import Final

from gemini_trading.economics.data.availability import AvailabilityPrecision
from gemini_trading.economics.data.observation import (
    EconomicChronologyError,
    EconomicDataError,
)
from gemini_trading.economics.data.publication import PublicationSequence, RevisionClass

ECONOMIC_OBSERVATION_SCHEMA_V2: Final[str] = "economic-observation-v2"
_EXACT_PRECISIONS = frozenset(
    {
        AvailabilityPrecision.EXACT_SECOND,
        AvailabilityPrecision.EXACT_MINUTE,
        AvailabilityPrecision.EXACT_HOUR,
    }
)


def _require_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise EconomicChronologyError(f"{field_name} must be timezone-aware")


def _format_time(value: datetime | None) -> str | None:
    if value is None:
        return None
    _require_aware(value, "identity datetime")
    return value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _identity_payload(row: "EconomicObservationV2") -> dict[str, object]:
    return {
        "schema_version": row.schema_version,
        "series_id": row.series_id,
        "observation_time": _format_time(row.observation_time),
        "reference_period_start": row.reference_period_start.isoformat(),
        "reference_period_end": row.reference_period_end.isoformat(),
        "available_time": _format_time(row.available_time),
        "available_date": None if row.available_date is None else row.available_date.isoformat(),
        "vintage_time": _format_time(row.vintage_time),
        "vintage_date": None if row.vintage_date is None else row.vintage_date.isoformat(),
        "retrieved_time": _format_time(row.retrieved_time),
        "source_id": row.source_id,
        "value": format(row.value, "f"),
        "unit": row.unit,
        "scale": format(row.scale, "f"),
        "frequency": row.frequency,
        "publication_event_id": row.publication_event_id,
        "availability_evidence_id": row.availability_evidence_id,
        "availability_channel": row.availability_channel,
        "availability_precision": row.availability_precision.value,
        "provider_native_source_id": row.provider_native_source_id,
        "source_version": row.source_version,
        "publication_sequence": row.publication_sequence.value,
        "revision_class": row.revision_class.value,
        "predecessor_version_id": row.predecessor_version_id,
        "raw_sha256": row.raw_sha256,
    }


def economic_observation_version_id(row: "EconomicObservationV2") -> str:
    """Return the deterministic semantic identity of one v2 observation."""

    payload = json.dumps(
        _identity_payload(row),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return sha256(payload).hexdigest()


def _require_optional_nonblank(value: str | None, field_name: str) -> None:
    if value is not None and not value.strip():
        raise EconomicDataError(f"{field_name} must not be blank")


@dataclass(frozen=True, slots=True)
class EconomicObservationV2:
    schema_version: str
    version_id: str
    series_id: str
    observation_time: datetime
    reference_period_start: date
    reference_period_end: date
    available_time: datetime | None
    available_date: date | None
    vintage_time: datetime | None
    vintage_date: date | None
    retrieved_time: datetime
    source_id: str
    value: Decimal
    unit: str
    scale: Decimal
    frequency: str
    publication_event_id: str
    availability_evidence_id: str | None
    availability_channel: str
    availability_precision: AvailabilityPrecision
    provider_native_source_id: str | None
    source_version: str | None
    publication_sequence: PublicationSequence
    revision_class: RevisionClass
    predecessor_version_id: str | None
    raw_sha256: str

    def __post_init__(self) -> None:
        if self.schema_version != ECONOMIC_OBSERVATION_SCHEMA_V2:
            raise EconomicDataError("unsupported economic observation v2 schema")
        for name, value in (
            ("series_id", self.series_id),
            ("source_id", self.source_id),
            ("unit", self.unit),
            ("frequency", self.frequency),
            ("publication_event_id", self.publication_event_id),
            ("availability_channel", self.availability_channel),
        ):
            if not value.strip():
                raise EconomicDataError(f"{name} must not be empty")
        for field_name, value in (
            ("provider_native_source_id", self.provider_native_source_id),
            ("source_version", self.source_version),
            ("predecessor_version_id", self.predecessor_version_id),
        ):
            _require_optional_nonblank(value, field_name)
        _require_aware(self.observation_time, "observation_time")
        _require_aware(self.retrieved_time, "retrieved_time")
        if self.reference_period_end < self.reference_period_start:
            raise EconomicChronologyError("reference period end precedes start")
        self._validate_value_and_digest()
        self._validate_temporal_precision()
        self._validate_version_identity()

    def _validate_value_and_digest(self) -> None:
        if not self.value.is_finite():
            raise EconomicDataError("value must be finite")
        if not self.scale.is_finite() or self.scale == 0:
            raise EconomicDataError("scale must be finite and nonzero")
        if len(self.raw_sha256) != 64 or any(
            character not in "0123456789abcdef" for character in self.raw_sha256
        ):
            raise EconomicDataError("raw_sha256 must be lowercase SHA-256 hex")
        if self.predecessor_version_id is not None and (
            len(self.predecessor_version_id) != 64
            or any(character not in "0123456789abcdef" for character in self.predecessor_version_id)
        ):
            raise EconomicDataError("predecessor_version_id must be lowercase SHA-256 hex")

    def _validate_temporal_precision(self) -> None:
        if self.vintage_time is not None:
            _require_aware(self.vintage_time, "vintage_time")
            if self.vintage_date is not None:
                raise EconomicDataError("vintage_time and vintage_date are mutually exclusive")
            if self.vintage_time > self.retrieved_time:
                raise EconomicChronologyError("vintage_time exceeds retrieved_time")
        if self.availability_precision in _EXACT_PRECISIONS:
            self._validate_exact_availability()
            return
        if self.availability_precision is AvailabilityPrecision.DATE_ONLY:
            if self.available_date is None or self.available_time is not None:
                raise EconomicDataError("DATE_ONLY requires available_date and no available_time")
            if self.availability_evidence_id is None:
                raise EconomicDataError("DATE_ONLY requires resolved availability evidence")
            return
        if self.availability_precision in {
            AvailabilityPrecision.INFERRED_INTERVAL,
            AvailabilityPrecision.UNKNOWN,
        }:
            if self.available_time is not None or self.available_date is not None:
                raise EconomicDataError(
                    f"{self.availability_precision.value} cannot carry admitted availability"
                )
            if self.availability_evidence_id is not None:
                raise EconomicDataError(
                    f"{self.availability_precision.value} cannot select resolved evidence"
                )
            return
        raise EconomicDataError("unsupported availability precision")

    def _validate_exact_availability(self) -> None:
        if self.available_time is None or self.available_date is not None:
            raise EconomicDataError("exact availability requires available_time only")
        if self.availability_evidence_id is None:
            raise EconomicDataError("exact availability requires resolved evidence")
        _require_aware(self.available_time, "available_time")
        if self.available_time < self.observation_time:
            raise EconomicChronologyError("available_time precedes observation_time")
        if self.retrieved_time < self.available_time:
            raise EconomicChronologyError("retrieved_time precedes available_time")

    def _validate_version_identity(self) -> None:
        derived = economic_observation_version_id(self)
        if self.version_id:
            if self.version_id != derived:
                raise EconomicDataError("version_id does not match observation semantics")
            return
        object.__setattr__(self, "version_id", derived)


__all__ = [
    "ECONOMIC_OBSERVATION_SCHEMA_V2",
    "EconomicObservationV2",
    "economic_observation_version_id",
]
