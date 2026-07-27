"""Contracts for candle-dataset-v4 identity and supporting evidence."""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Protocol, cast

import pytest

import gemini_trading.data.datasets.canonical_writer as canonical_writer
from gemini_trading.data.datasets.canonical_writer import (
    build_dataset_manifest,
    serialize_candles,
    serialize_dataset_manifest,
)
from gemini_trading.domain.candle import Candle
from gemini_trading.domain.instrument import Instrument
from gemini_trading.domain.timeframe import Timeframe

_INSTRUMENT = Instrument("ETHUSDT", "ETH", "USDT")
_START = datetime(2025, 1, 1, tzinfo=UTC)
_END = datetime(2025, 1, 2, tzinfo=UTC)
_CLOSURE_BYTES = b'{"closures":[1,2]}\n'
_EXCLUSION_BYTES = b'{"exclusions":[1,2]}\n'
_SEGMENT_BYTES = b'{"segments":[1,2,3]}\n'


class _DatasetIdV4(Protocol):
    def __call__(
        self,
        *,
        provider: str,
        instrument: Instrument,
        timeframe: Timeframe,
        start_time: datetime,
        end_time: datetime,
        canonical_bytes: bytes,
        closure_manifest_bytes: bytes,
        exclusion_manifest_bytes: bytes,
        segment_manifest_bytes: bytes,
    ) -> str: ...


def _candle() -> Candle:
    return Candle(
        instrument=_INSTRUMENT,
        timeframe=Timeframe.H4,
        open_time=_START,
        close_time=datetime(2025, 1, 1, 3, 59, 59, 999000, tzinfo=UTC),
        open=Decimal("100"),
        high=Decimal("110"),
        low=Decimal("90"),
        close=Decimal("105"),
        volume=Decimal("12"),
        completed=True,
        source_provider="binance_spot",
    )


def _dataset_id_v4(
    *,
    canonical_bytes: bytes,
    closure_manifest_bytes: bytes = _CLOSURE_BYTES,
    exclusion_manifest_bytes: bytes = _EXCLUSION_BYTES,
    segment_manifest_bytes: bytes = _SEGMENT_BYTES,
) -> str:
    function = cast(_DatasetIdV4, canonical_writer.__dict__["dataset_id_v4"])
    return function(
        provider="binance_spot",
        instrument=_INSTRUMENT,
        timeframe=Timeframe.H4,
        start_time=_START,
        end_time=_END,
        canonical_bytes=canonical_bytes,
        closure_manifest_bytes=closure_manifest_bytes,
        exclusion_manifest_bytes=exclusion_manifest_bytes,
        segment_manifest_bytes=segment_manifest_bytes,
    )


def test_v4_dataset_identity_binds_every_supporting_byte_stream() -> None:
    canonical = serialize_candles((_candle(),))
    identity = _dataset_id_v4(canonical_bytes=canonical)

    assert _dataset_id_v4(canonical_bytes=canonical) == identity
    assert _dataset_id_v4(canonical_bytes=canonical + b" ") != identity
    assert (
        _dataset_id_v4(
            canonical_bytes=canonical,
            closure_manifest_bytes=_CLOSURE_BYTES + b" ",
        )
        != identity
    )
    assert (
        _dataset_id_v4(
            canonical_bytes=canonical,
            exclusion_manifest_bytes=_EXCLUSION_BYTES + b" ",
        )
        != identity
    )
    assert (
        _dataset_id_v4(
            canonical_bytes=canonical,
            segment_manifest_bytes=_SEGMENT_BYTES + b" ",
        )
        != identity
    )


def test_build_and_serialize_v4_manifest_binds_all_evidence() -> None:
    canonical = serialize_candles((_candle(),))
    manifest = build_dataset_manifest(
        schema_version="candle-dataset-v4",
        provider="binance_spot",
        instrument=_INSTRUMENT,
        timeframe=Timeframe.H4,
        start_time=_START,
        end_time=_END,
        candles=(_candle(),),
        canonical_bytes=canonical,
        closure_manifest_bytes=_CLOSURE_BYTES,
        exclusion_manifest_bytes=_EXCLUSION_BYTES,
        segment_manifest_bytes=_SEGMENT_BYTES,
        closure_count=2,
        exclusion_count=2,
        segment_count=3,
    )

    assert manifest.dataset_id == _dataset_id_v4(canonical_bytes=canonical)
    encoded = serialize_dataset_manifest(manifest)
    assert b'"schema_version":"candle-dataset-v4"' in encoded
    assert b'"closure_manifest_sha256":"' in encoded
    assert b'"exclusion_manifest_sha256":"' in encoded
    assert b'"segment_manifest_sha256":"' in encoded
    assert b'"closure_count":2' in encoded
    assert b'"exclusion_count":2' in encoded
    assert b'"segment_count":3' in encoded


@pytest.mark.parametrize(
    ("closure_count", "exclusion_count", "segment_count", "message"),
    [
        (2, 1, 3, "exclusion_count"),
        (2, 2, 2, "segment_count"),
    ],
)
def test_v4_manifest_rejects_inconsistent_supporting_counts(
    closure_count: int,
    exclusion_count: int,
    segment_count: int,
    message: str,
) -> None:
    canonical = serialize_candles((_candle(),))
    with pytest.raises(ValueError, match=message):
        build_dataset_manifest(
            schema_version="candle-dataset-v4",
            provider="binance_spot",
            instrument=_INSTRUMENT,
            timeframe=Timeframe.H4,
            start_time=_START,
            end_time=_END,
            candles=(_candle(),),
            canonical_bytes=canonical,
            closure_manifest_bytes=b"{}\n",
            exclusion_manifest_bytes=b"{}\n",
            segment_manifest_bytes=b"{}\n",
            closure_count=closure_count,
            exclusion_count=exclusion_count,
            segment_count=segment_count,
        )


def test_v4_manifest_requires_exclusion_evidence() -> None:
    canonical = serialize_candles((_candle(),))
    with pytest.raises(ValueError, match="exclusion manifest"):
        build_dataset_manifest(
            schema_version="candle-dataset-v4",
            provider="binance_spot",
            instrument=_INSTRUMENT,
            timeframe=Timeframe.H4,
            start_time=_START,
            end_time=_END,
            candles=(_candle(),),
            canonical_bytes=canonical,
            closure_manifest_bytes=b"{}\n",
            segment_manifest_bytes=b"{}\n",
            closure_count=1,
            exclusion_count=1,
            segment_count=2,
        )
