"""Canonical research JSON and JSONL encoding."""

import json
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from decimal import Decimal
from typing import cast


def format_decimal(value: Decimal) -> str:
    """Format one finite Decimal without losing trailing zeroes."""

    if not value.is_finite():
        raise ValueError("Decimal value must be finite")
    return format(value, "f")


def format_utc(value: datetime) -> str:
    """Format one UTC-aware timestamp using millisecond precision."""

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must be UTC-aware")
    if value.utcoffset().total_seconds() != 0:
        raise ValueError("datetime must be UTC-aware")
    return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _default(value: object) -> object:
    if isinstance(value, Decimal):
        return format_decimal(value)
    if isinstance(value, datetime):
        return format_utc(value)
    raise TypeError(f"unsupported canonical JSON type: {type(value).__name__}")


def canonical_json_bytes(payload: Mapping[str, object]) -> bytes:
    """Serialize one mapping as sorted compact UTF-8 JSON with one newline."""

    encoded = json.dumps(
        dict(payload),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
        default=_default,
    )
    return f"{encoded}\n".encode("utf-8")


def canonical_jsonl_bytes(rows: Iterable[Mapping[str, object]]) -> bytes:
    """Serialize mappings as canonical JSON Lines while preserving row order."""

    return b"".join(canonical_json_bytes(cast(Mapping[str, object], row)) for row in rows)
