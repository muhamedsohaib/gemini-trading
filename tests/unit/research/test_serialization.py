"""Tests for canonical research JSON and JSONL encoding."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from gemini_trading.research.serialization import (
    canonical_json_bytes,
    canonical_jsonl_bytes,
    format_decimal,
    format_utc,
)


def test_canonical_json_is_sorted_compact_utf8_and_newline_terminated() -> None:
    payload = {"z": Decimal("1.2300"), "a": "é"}

    assert canonical_json_bytes(payload) == '{"a":"é","z":"1.2300"}\n'.encode("utf-8")


def test_canonical_jsonl_preserves_row_order() -> None:
    assert canonical_jsonl_bytes(({"n": 2}, {"n": 1})) == b'{"n":2}\n{"n":1}\n'


def test_decimal_and_utc_formatting_are_exact() -> None:
    assert format_decimal(Decimal("10.5000")) == "10.5000"
    assert format_utc(datetime(2025, 1, 1, 0, 0, tzinfo=UTC)) == "2025-01-01T00:00:00.000Z"


def test_serialization_rejects_non_finite_decimal_and_non_utc_time() -> None:
    with pytest.raises(ValueError, match="finite"):
        format_decimal(Decimal("NaN"))
    with pytest.raises(ValueError, match="UTC-aware"):
        format_utc(datetime(2025, 1, 1))
