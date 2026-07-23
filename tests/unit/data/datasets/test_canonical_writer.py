import hashlib
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from gemini_trading.data.datasets.canonical_writer import (
    build_dataset_manifest,
    build_provenance,
    dataset_id,
    serialize_candles,
    serialize_dataset_manifest,
    serialize_provenance,
)
from gemini_trading.domain.candle import Candle
from gemini_trading.domain.instrument import Instrument
from gemini_trading.domain.timeframe import Timeframe

_INSTRUMENT = Instrument("ETHUSDT", "ETH", "USDT")
_START = datetime(2025, 1, 1, tzinfo=UTC)
_END = datetime(2025, 1, 2, tzinfo=UTC)
_OPEN_TIME = datetime(2025, 1, 1, 0, 0, 0, 123000, tzinfo=UTC)
_CLOSE_TIME = datetime(2025, 1, 1, 3, 59, 59, 999000, tzinfo=UTC)
_SCHEMA_VERSION = "candle-dataset-v1"


def _candle(**changes: object) -> Candle:
    candle = Candle(
        instrument=_INSTRUMENT,
        timeframe=Timeframe.H4,
        open_time=_OPEN_TIME,
        close_time=_CLOSE_TIME,
        open=Decimal("100.00"),
        high=Decimal("110.50"),
        low=Decimal("90.25"),
        close=Decimal("105.00"),
        volume=Decimal("12.3400"),
        completed=True,
        source_provider="binance_spot",
    )
    return replace(candle, **changes)


def test_serialize_candles_uses_fixed_compact_field_order_and_exact_formats() -> None:
    canonical = serialize_candles((_candle(),))

    assert canonical == (
        b'{"symbol":"ETHUSDT","base_asset":"ETH","quote_asset":"USDT",'
        b'"timeframe":"4h","open_time":"2025-01-01T00:00:00.123Z",'
        b'"close_time":"2025-01-01T03:59:59.999Z","open":"100.00",'
        b'"high":"110.50","low":"90.25","close":"105.00",'
        b'"volume":"12.3400","completed":true,"source_provider":"binance_spot"}\n'
    )
    assert canonical.count(b"\n") == 1
    assert b" " not in canonical


def test_serialize_candles_writes_one_newline_per_row() -> None:
    candles = (
        _candle(),
        _candle(
            open_time=datetime(2025, 1, 1, 4, tzinfo=UTC),
            close_time=datetime(2025, 1, 1, 7, 59, 59, 999000, tzinfo=UTC),
        ),
    )

    canonical = serialize_candles(candles)

    assert canonical.endswith(b"\n")
    assert canonical.count(b"\n") == len(candles)
    assert all(line.startswith(b'{"symbol":') for line in canonical.splitlines())


def test_serialize_candles_rejects_incomplete_canonical_rows() -> None:
    with pytest.raises(ValueError, match="canonical datasets require completed candles"):
        serialize_candles((_candle(completed=False),))


def test_dataset_id_uses_exact_schema_newline_content_formula() -> None:
    canonical = serialize_candles((_candle(),))

    identity = dataset_id(_SCHEMA_VERSION, canonical)

    expected = hashlib.sha256(_SCHEMA_VERSION.encode("utf-8") + b"\n" + canonical).hexdigest()
    assert identity == expected
    assert dataset_id(_SCHEMA_VERSION, canonical) == identity
    assert dataset_id(f"{_SCHEMA_VERSION}-changed", canonical) != identity


def test_dataset_id_rejects_blank_schema_version() -> None:
    with pytest.raises(ValueError, match="schema_version must not be empty"):
        dataset_id("  ", b"{}\n")


def test_build_and_serialize_dataset_manifest_are_deterministic() -> None:
    candles = (
        _candle(),
        _candle(
            open_time=datetime(2025, 1, 1, 4, tzinfo=UTC),
            close_time=datetime(2025, 1, 1, 7, 59, 59, 999000, tzinfo=UTC),
        ),
    )
    canonical = serialize_candles(candles)
    identity = dataset_id(_SCHEMA_VERSION, canonical)

    manifest = build_dataset_manifest(
        schema_version=_SCHEMA_VERSION,
        provider="binance_spot",
        instrument=_INSTRUMENT,
        timeframe=Timeframe.H4,
        start_time=_START,
        end_time=_END,
        candles=candles,
        canonical_bytes=canonical,
    )

    expected = (
        b'{"schema_version":"candle-dataset-v1","dataset_id":"'
        + identity.encode("ascii")
        + b'","provider":"binance_spot","instrument":{"symbol":"ETHUSDT",'
        b'"base_asset":"ETH","quote_asset":"USDT"},"timeframe":"4h",'
        b'"start_time":"2025-01-01T00:00:00.000Z",'
        b'"end_time":"2025-01-02T00:00:00.000Z",'
        b'"first_open_time":"2025-01-01T00:00:00.123Z",'
        b'"last_open_time":"2025-01-01T04:00:00.000Z","candle_count":2,'
        b'"canonical_sha256":"' + hashlib.sha256(canonical).hexdigest().encode("ascii") + b'"}\n'
    )
    assert manifest.dataset_id == identity
    assert manifest.first_open_time == candles[0].open_time
    assert manifest.last_open_time == candles[-1].open_time
    assert manifest.candle_count == 2
    assert serialize_dataset_manifest(manifest) == expected
    assert serialize_dataset_manifest(manifest) == expected


def test_build_dataset_manifest_requires_at_least_one_candle() -> None:
    with pytest.raises(ValueError, match="canonical dataset must contain at least one candle"):
        build_dataset_manifest(
            schema_version=_SCHEMA_VERSION,
            provider="binance_spot",
            instrument=_INSTRUMENT,
            timeframe=Timeframe.H4,
            start_time=_START,
            end_time=_END,
            candles=(),
            canonical_bytes=b"",
        )


def test_provenance_contains_run_metadata_without_changing_canonical_identity() -> None:
    canonical = serialize_candles((_candle(),))
    identity = dataset_id(_SCHEMA_VERSION, canonical)
    first = build_provenance(
        schema_version="dataset-provenance-v1",
        dataset_id=identity,
        run_id="run-001",
        page_hashes=("a" * 64,),
        retrieval_manifest_sha256="b" * 64,
        linked=True,
        created_at=datetime(2025, 1, 2, 0, 0, 0, 123000, tzinfo=UTC),
    )
    second = build_provenance(
        schema_version="dataset-provenance-v1",
        dataset_id=identity,
        run_id="run-002",
        page_hashes=("c" * 64,),
        retrieval_manifest_sha256="d" * 64,
        linked=True,
        created_at=datetime(2025, 1, 3, 0, 0, 0, 456000, tzinfo=UTC),
    )

    expected_first = (
        b'{"schema_version":"dataset-provenance-v1","dataset_id":"'
        + identity.encode("ascii")
        + b'","run_id":"run-001","page_hashes":["'
        + ("a" * 64).encode("ascii")
        + b'"],"retrieval_manifest_sha256":"'
        + ("b" * 64).encode("ascii")
        + b'","linked":true,"created_at":"2025-01-02T00:00:00.123Z"}\n'
    )
    assert serialize_provenance(first) == expected_first
    assert serialize_provenance(first) != serialize_provenance(second)
    assert dataset_id(_SCHEMA_VERSION, canonical) == identity
