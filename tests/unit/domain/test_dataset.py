from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta, timezone

import pytest

from gemini_trading.domain.dataset import DatasetManifest, RetrievalRequest
from gemini_trading.domain.instrument import Instrument
from gemini_trading.domain.timeframe import Timeframe


def test_retrieval_request_uses_bounded_utc_window() -> None:
    request = RetrievalRequest(
        instrument=Instrument("ETHUSDT", "ETH", "USDT"),
        timeframe=Timeframe.H4,
        start_time=datetime(2025, 1, 1, tzinfo=UTC),
        end_time=datetime(2025, 1, 2, tzinfo=UTC),
    )

    assert request.start_time == datetime(2025, 1, 1, tzinfo=UTC)
    assert request.end_time == datetime(2025, 1, 2, tzinfo=UTC)


def test_retrieval_request_rejects_naive_or_non_utc_window() -> None:
    instrument = Instrument("ETHUSDT", "ETH", "USDT")

    with pytest.raises(ValueError, match="UTC-aware"):
        RetrievalRequest(
            instrument,
            Timeframe.H4,
            datetime(2025, 1, 1),
            datetime(2025, 1, 2),
        )

    with pytest.raises(ValueError, match="UTC-aware"):
        RetrievalRequest(
            instrument,
            Timeframe.H4,
            datetime(2025, 1, 1, tzinfo=timezone(timedelta(hours=4))),
            datetime(2025, 1, 2, tzinfo=timezone(timedelta(hours=4))),
        )


def test_retrieval_request_requires_end_after_start() -> None:
    instrument = Instrument("ETHUSDT", "ETH", "USDT")
    instant = datetime(2025, 1, 1, tzinfo=UTC)

    with pytest.raises(ValueError, match="later than"):
        RetrievalRequest(instrument, Timeframe.H4, instant, instant)


def test_retrieval_request_is_immutable() -> None:
    request = RetrievalRequest(
        Instrument("ETHUSDT", "ETH", "USDT"),
        Timeframe.H4,
        datetime(2025, 1, 1, tzinfo=UTC),
        datetime(2025, 1, 2, tzinfo=UTC),
    )

    with pytest.raises(FrozenInstanceError):
        request.end_time = datetime(2025, 1, 3, tzinfo=UTC)  # type: ignore[misc]


def test_v2_dataset_manifest_requires_valid_supporting_hashes_and_counts() -> None:
    manifest = DatasetManifest(
        schema_version="candle-dataset-v2",
        dataset_id="a" * 64,
        provider="binance_spot",
        instrument=Instrument("BTCUSDT", "BTC", "USDT"),
        timeframe=Timeframe.H4,
        start_time=datetime(2018, 1, 1, tzinfo=UTC),
        end_time=datetime(2026, 7, 1, tzinfo=UTC),
        first_open_time=datetime(2018, 1, 1, tzinfo=UTC),
        last_open_time=datetime(2026, 6, 30, 20, tzinfo=UTC),
        candle_count=1,
        canonical_sha256="b" * 64,
        closure_manifest_sha256="c" * 64,
        segment_manifest_sha256="d" * 64,
        closure_count=1,
        segment_count=2,
    )
    assert manifest.segment_count == manifest.closure_count + 1

    with pytest.raises(ValueError, match="segment_count"):
        replace(manifest, segment_count=3)
    with pytest.raises(ValueError, match="closure_manifest_sha256"):
        replace(manifest, closure_manifest_sha256="bad")
