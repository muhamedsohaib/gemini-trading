"""Unit tests for strict verified canonical dataset loading."""

import json
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


def _candles() -> tuple[Candle, ...]:
    instrument = Instrument("ETHUSDT", "ETH", "USDT")
    start = datetime(2025, 1, 1, tzinfo=UTC)
    values: list[Candle] = []
    for index, close in enumerate(("101", "102", "103")):
        open_time = start + timedelta(hours=4 * index)
        values.append(
            Candle(
                instrument=instrument,
                timeframe=Timeframe.H4,
                open_time=open_time,
                close_time=open_time + timedelta(hours=4) - timedelta(milliseconds=1),
                open=Decimal("100"),
                high=Decimal("110"),
                low=Decimal("90"),
                close=Decimal(close),
                volume=Decimal("10"),
                completed=True,
                source_provider="binance_spot",
            )
        )
    return tuple(values)


def _write_dataset(root: Path, canonical_bytes: bytes | None = None) -> str:
    candles = _candles()
    selected_bytes = serialize_candles(candles) if canonical_bytes is None else canonical_bytes
    manifest = build_dataset_manifest(
        schema_version="candle-dataset-v1",
        provider="binance_spot",
        instrument=candles[0].instrument,
        timeframe=candles[0].timeframe,
        start_time=candles[0].open_time,
        end_time=candles[-1].open_time + candles[-1].timeframe.duration,
        candles=candles,
        canonical_bytes=selected_bytes,
    )
    LocalImmutableStore(root).write_dataset(
        manifest.dataset_id,
        selected_bytes,
        serialize_dataset_manifest(manifest),
    )
    return manifest.dataset_id


def test_reader_rejects_unknown_candle_fields_even_with_valid_identity(tmp_path: Path) -> None:
    row = json.loads(serialize_candles((_candles()[0],)).decode())
    row["future_return"] = "999"
    canonical_bytes = (json.dumps(row, separators=(",", ":")) + "\n").encode()
    dataset_id_value = _write_dataset(tmp_path, canonical_bytes)

    with pytest.raises(DatasetVerificationError, match="candle fields"):
        load_verified_dataset(LocalImmutableStore(tmp_path), dataset_id_value)


def test_reader_rejects_incomplete_candle_even_with_valid_identity(tmp_path: Path) -> None:
    rows = [json.loads(line) for line in serialize_candles(_candles()).decode().splitlines()]
    rows[1]["completed"] = False
    canonical_bytes = b"".join(
        (json.dumps(row, separators=(",", ":")) + "\n").encode() for row in rows
    )
    dataset_id_value = _write_dataset(tmp_path, canonical_bytes)

    with pytest.raises(DatasetVerificationError, match="completed"):
        load_verified_dataset(LocalImmutableStore(tmp_path), dataset_id_value)


def test_reader_rejects_unknown_manifest_fields(tmp_path: Path) -> None:
    dataset_id_value = _write_dataset(tmp_path)
    manifest_path = tmp_path / "data" / "canonical" / dataset_id_value / "dataset-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["created_at"] = "2025-01-01T00:00:00.000Z"
    manifest_path.write_text(json.dumps(manifest, separators=(",", ":")) + "\n")

    with pytest.raises(DatasetVerificationError, match="manifest fields"):
        load_verified_dataset(LocalImmutableStore(tmp_path), dataset_id_value)
