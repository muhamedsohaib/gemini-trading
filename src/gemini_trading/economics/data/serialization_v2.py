"""Deterministic serialization for Economic Data Fabric v2 contracts."""

import json
from collections.abc import Iterable
from datetime import UTC, date, datetime
from decimal import Decimal

from gemini_trading.economics.data.availability import EconomicAvailabilityEvidence
from gemini_trading.economics.data.observation import EconomicDataError
from gemini_trading.economics.data.observation_v2 import EconomicObservationV2
from gemini_trading.economics.data.publication import EconomicPublicationEvent


def _format_utc(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        raise EconomicDataError("v2 serialization requires timezone-aware datetimes")
    return value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _format_date(value: date | None) -> str | None:
    return None if value is None else value.isoformat()


def _format_decimal(value: Decimal) -> str:
    if not value.is_finite():
        raise EconomicDataError("v2 serialization requires finite decimals")
    return format(value, "f")


def _json_line(payload: dict[str, object]) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n").encode()


def availability_evidence_identity_key(row: EconomicAvailabilityEvidence) -> str:
    return row.evidence_id


def publication_event_identity_key(row: EconomicPublicationEvent) -> str:
    return row.event_id


def observation_v2_identity_key(row: EconomicObservationV2) -> str:
    return row.version_id


def _availability_payload(row: EconomicAvailabilityEvidence) -> dict[str, object]:
    return {
        "schema_version": row.schema_version,
        "evidence_id": row.evidence_id,
        "publication_event_id": row.publication_event_id,
        "source_id": row.source_id,
        "consumer_class": row.consumer_class,
        "availability_channel": row.availability_channel,
        "availability_precision": row.availability_precision.value,
        "available_time": _format_utc(row.available_time),
        "available_date": _format_date(row.available_date),
        "interval_start": _format_utc(row.interval_start),
        "interval_end": _format_utc(row.interval_end),
        "source_timezone": row.source_timezone,
        "source_utc_offset_minutes": row.source_utc_offset_minutes,
        "retrieved_time": _format_utc(row.retrieved_time),
        "raw_sha256": row.raw_sha256,
    }


def _publication_payload(row: EconomicPublicationEvent) -> dict[str, object]:
    return {
        "schema_version": row.schema_version,
        "event_id": row.event_id,
        "publisher": row.publisher,
        "source_id": row.source_id,
        "event_type": row.event_type,
        "scheduled_time": _format_utc(row.scheduled_time),
        "published_time": _format_utc(row.published_time),
        "available_time": _format_utc(row.available_time),
        "available_date": _format_date(row.available_date),
        "consumer_class": row.consumer_class,
        "availability_channel": row.availability_channel,
        "availability_precision": row.availability_precision.value,
        "availability_evidence_ids": sorted(row.availability_evidence_ids),
        "availability_evidence_id": row.availability_evidence_id,
        "availability_status": row.availability_status.value,
        "publication_sequence": row.publication_sequence.value,
        "revision_class": row.revision_class.value,
        "provider_native_publication_sequence": row.provider_native_publication_sequence,
        "provider_native_event_id": row.provider_native_event_id,
        "provider_native_source_id": row.provider_native_source_id,
        "source_version": row.source_version,
        "predecessor_event_id": row.predecessor_event_id,
        "retrieved_time": _format_utc(row.retrieved_time),
        "raw_sha256": row.raw_sha256,
    }


def _observation_payload(row: EconomicObservationV2) -> dict[str, object]:
    return {
        "schema_version": row.schema_version,
        "version_id": row.version_id,
        "series_id": row.series_id,
        "observation_time": _format_utc(row.observation_time),
        "reference_period_start": _format_date(row.reference_period_start),
        "reference_period_end": _format_date(row.reference_period_end),
        "available_time": _format_utc(row.available_time),
        "available_date": _format_date(row.available_date),
        "vintage_time": _format_utc(row.vintage_time),
        "vintage_date": _format_date(row.vintage_date),
        "retrieved_time": _format_utc(row.retrieved_time),
        "source_id": row.source_id,
        "value": _format_decimal(row.value),
        "unit": row.unit,
        "scale": _format_decimal(row.scale),
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


def serialize_availability_evidence(rows: Iterable[EconomicAvailabilityEvidence]) -> bytes:
    ordered = tuple(sorted(rows, key=availability_evidence_identity_key))
    seen: set[str] = set()
    encoded: list[bytes] = []
    for row in ordered:
        identity = availability_evidence_identity_key(row)
        if identity in seen:
            raise EconomicDataError("duplicate economic availability evidence identity")
        seen.add(identity)
        encoded.append(_json_line(_availability_payload(row)))
    return b"".join(encoded)


def serialize_publication_events(rows: Iterable[EconomicPublicationEvent]) -> bytes:
    ordered = tuple(sorted(rows, key=publication_event_identity_key))
    seen: set[str] = set()
    encoded: list[bytes] = []
    for row in ordered:
        identity = publication_event_identity_key(row)
        if identity in seen:
            raise EconomicDataError("duplicate economic publication event identity")
        seen.add(identity)
        encoded.append(_json_line(_publication_payload(row)))
    return b"".join(encoded)


def serialize_observations_v2(rows: Iterable[EconomicObservationV2]) -> bytes:
    ordered = tuple(
        sorted(
            rows,
            key=lambda row: (
                row.series_id,
                row.reference_period_start,
                row.reference_period_end,
                observation_v2_identity_key(row),
            ),
        )
    )
    seen: set[str] = set()
    encoded: list[bytes] = []
    for row in ordered:
        identity = observation_v2_identity_key(row)
        if identity in seen:
            raise EconomicDataError("duplicate economic observation v2 identity")
        seen.add(identity)
        encoded.append(_json_line(_observation_payload(row)))
    return b"".join(encoded)


__all__ = [
    "availability_evidence_identity_key",
    "observation_v2_identity_key",
    "publication_event_identity_key",
    "serialize_availability_evidence",
    "serialize_observations_v2",
    "serialize_publication_events",
]
