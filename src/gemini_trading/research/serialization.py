"""Canonical research JSON and JSONL encoding."""

import json
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from decimal import Decimal


def format_decimal(value: Decimal) -> str:
    """Return an exact finite decimal string without normalization."""

    if not value.is_finite():
        raise ValueError("Decimal value must be finite")
    return format(value, "f")


def format_utc(value: datetime) -> str:
    """Return a millisecond-resolution UTC timestamp."""

    offset = value.utcoffset() if value.tzinfo is not None else None
    if offset is None or offset.total_seconds() != 0:
        raise ValueError("datetime must be UTC-aware")
    return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _default(value: object) -> object:
    if isinstance(value, Decimal):
        return format_decimal(value)
    if isinstance(value, datetime):
        return format_utc(value)
    raise TypeError(f"unsupported canonical JSON type: {type(value).__name__}")


def canonical_json_bytes(payload: Mapping[str, object]) -> bytes:
    """Serialize one mapping as deterministic compact UTF-8 JSON."""

    encoded = json.dumps(
        dict(payload),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
        default=_default,
    )
    return f"{encoded}\n".encode()


def canonical_jsonl_bytes(rows: Iterable[Mapping[str, object]]) -> bytes:
    """Serialize ordered mappings as deterministic JSON Lines."""

    return b"".join(canonical_json_bytes(row) for row in rows)
