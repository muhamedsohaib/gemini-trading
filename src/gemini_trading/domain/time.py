"""Shared time validation helpers for market-data domain values."""

from datetime import datetime, timedelta


def require_utc(value: datetime, field_name: str) -> None:
    """Require a timezone-aware datetime whose UTC offset is exactly zero."""

    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError(f"{field_name} must be UTC-aware")
