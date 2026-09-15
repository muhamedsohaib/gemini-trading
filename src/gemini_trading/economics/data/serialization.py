"""Deterministic serialization for point-in-time economic evidence."""

import json
from collections.abc import Iterable
from datetime import UTC, datetime
from decimal import Decimal

from gemini_trading.economics.data.observation import (
    EconomicDataError,
    EconomicObservation,
)
from gemini_trading.economics.data.series import (
    EconomicSeriesDefinition,
    EconomicSeriesRegistry,
)


def _format_utc(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise EconomicDataError("economic serialization requires timezone-aware datetimes")
    return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _format_decimal(value: Decimal) -> str:
    if not value.is_finite():
        raise EconomicDataError("economic serialization requires finite decimals")
    return format(value, "f")


def _json_line(payload: dict[str, object]) -> bytes:
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return f"{encoded}\n".encode("utf-8")


def observation_identity_key(
    row: EconomicObservation,
) -> tuple[str, datetime, datetime, str, str]:
    """Return the logical immutable identity of one observation row."""

    return (
        row.series_id,
        row.observation_time.astimezone(UTC),
        row.available_time.astimezone(UTC),
        row.source_id,
        row.release_id or "",
    )


def _observation_payload(row: EconomicObservation) -> dict[str, object]:
    return {
        "schema_version": row.schema_version,
        "series_id": row.series_id,
        "observation_time": _format_utc(row.observation_time),
        "available_time": _format_utc(row.available_time),
        "vintage_time": None if row.vintage_time is None else _format_utc(row.vintage_time),
        "retrieved_time": _format_utc(row.retrieved_time),
        "source_id": row.source_id,
        "value": _format_decimal(row.value),
        "unit": row.unit,
        "scale": _format_decimal(row.scale),
        "frequency": row.frequency,
        "release_id": row.release_id,
        "raw_sha256": row.raw_sha256,
    }


def serialize_observations(rows: Iterable[EconomicObservation]) -> bytes:
    """Serialize unique observations in deterministic logical order."""

    ordered = tuple(
        sorted(
            rows,
            key=lambda row: (*observation_identity_key(row), row.raw_sha256),
        )
    )
    seen: set[tuple[str, datetime, datetime, str, str]] = set()
    encoded: list[bytes] = []
    for row in ordered:
        identity = observation_identity_key(row)
        if identity in seen:
            raise EconomicDataError("duplicate economic observation identity")
        seen.add(identity)
        encoded.append(_json_line(_observation_payload(row)))
    return b"".join(encoded)


def _series_payload(definition: EconomicSeriesDefinition) -> dict[str, object]:
    return {
        "schema_version": definition.schema_version,
        "series_id": definition.series_id,
        "title": definition.title,
        "domain": definition.domain.value,
        "unit": definition.unit,
        "scale": _format_decimal(definition.scale),
        "frequency": definition.frequency,
        "observation_semantics": definition.observation_semantics,
        "availability_semantics": definition.availability_semantics,
        "revision_policy": definition.revision_policy.value,
    }


def serialize_series_registry(registry: EconomicSeriesRegistry) -> bytes:
    """Serialize the canonical sorted economic series registry."""

    return b"".join(_json_line(_series_payload(item)) for item in registry.definitions)


__all__ = [
    "observation_identity_key",
    "serialize_observations",
    "serialize_series_registry",
]
