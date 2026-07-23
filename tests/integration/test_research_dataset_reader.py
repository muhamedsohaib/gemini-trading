"""Integration tests for verified canonical research datasets."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from gemini_trading.data.datasets.canonical_writer import (
    build_dataset_manifest,
    serialize_candles,
    serialize_dataset_manifest,
)
from gemini_trading.data.storage.local_immutable import LocalImmutableStore
from gemini_trading.domain.candle import Candle
from gemini_trading.domain.instrument import Instrument
from gemini_trading.domain.timeframe import Timeframe
from gemini_trading.research.dataset_reader import load_verified_dataset
from gemini_trading.research.errors import DatasetVerificationError


def _write_known_canonical_fixture(root: Path) -> str:
    instrument = Instrument("ETHUSDT", "ETH", "USDT")
    start = datetime(2025, 1, 1, tzinfo=UTC)
    candles = tuple(
        Candle(
            instrument=instrument,
            timeframe=Timeframe.H4,
            open_time=start + timedelta(hours=4 * index),
            close_time=start + timedelta(hours=4 * (index + 1)) - timedelta(milliseconds=1),
            open=Decimal("100"),
            high=Decimal("110"),
            low=Decimal("90"),
            close=Decimal(str(101 + index)),
            volume=Decimal("10"),
            completed=True,
            source_provider="binance_spot",
        )
        for index in range(3)
    )
    canonical_bytes = serialize_candles(candles)
    manifest = build_dataset_manifest(
        schema_version="candle-dataset-v1",
        provider="binance_spot",
        instrument=instrument,
        timeframe=Timeframe.H4,
        start_time=start,
        end_time=start + timedelta(hours=12),
        candles=candles,
        canonical_bytes=canonical_bytes,
    )
    LocalImmutableStore(root).write_dataset(
        manifest.dataset_id,
        canonical_bytes,
        serialize_dataset_manifest(manifest),
    )
    return manifest.dataset_id


def test_reader_loads_completed_candles_and_verifies_identity(tmp_path: Path) -> None:
    dataset_id_value = _write_known_canonical_fixture(tmp_path)

    result = load_verified_dataset(LocalImmutableStore(tmp_path), dataset_id_value)

    assert result.manifest.dataset_id == dataset_id_value
    assert len(result.candles) == 3
    assert all(candle.completed for candle in result.candles)


def test_reader_rejects_tampered_canonical_bytes(tmp_path: Path) -> None:
    dataset_id_value = _write_known_canonical_fixture(tmp_path)
    candle_path = tmp_path / "data" / "canonical" / dataset_id_value / "candles.jsonl"
    candle_path.write_bytes(candle_path.read_bytes() + b"{}\n")

    with pytest.raises(DatasetVerificationError, match="canonical"):
        load_verified_dataset(LocalImmutableStore(tmp_path), dataset_id_value)
