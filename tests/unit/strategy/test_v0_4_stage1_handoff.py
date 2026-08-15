"""Candidate v0.4 Stage 1 dataset-shape and handoff contracts."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from importlib import import_module
from pathlib import Path
from typing import Protocol, cast

import pytest

from gemini_trading.strategy.errors import DatasetHandoffError
from gemini_trading.strategy.handoff import (
    ArtifactInventoryEntry,
    ExcludedProviderRow,
    inventory_root_sha256,
)

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_MODULE_NAME = "gemini_trading.strategy.v0_4_stage1"


class _ExpectedShape(Protocol):
    closure_count: int
    exclusion_count: int
    segment_count: int
    closure_ids: tuple[str, ...]
    partial_closure_ids: tuple[str, ...]
    segment_boundary_indices: tuple[int, ...]
    candle_count: int
    first_open_time: str
    last_open_time: str


class _Handoff(Protocol):
    schema_version: str
    repository: str
    source_commit: str
    workflow_name: str
    workflow_run_id: int
    workflow_run_attempt: int
    job_name: str
    provider: str
    symbol: str
    base_asset: str
    quote_asset: str
    interval: str
    start: str
    end_exclusive: str
    run_id: str
    dataset_id: str
    dataset_schema_version: str
    closure_count: int
    exclusion_count: int
    segment_count: int
    closure_ids: tuple[str, ...]
    excluded_provider_rows: tuple[ExcludedProviderRow, ...]
    segment_boundary_indices: tuple[int, ...]
    candle_count: int
    first_open_time: str
    last_open_time: str
    files: tuple[ArtifactInventoryEntry, ...]
    inventory_root_sha256: str


def _module() -> object:
    return import_module(_MODULE_NAME)


def _expected_shape() -> _ExpectedShape:
    builder = cast(
        Callable[[Path], _ExpectedShape] | None,
        getattr(_module(), "expected_v0_4_stage1_shape", None),
    )
    assert builder is not None, "Candidate v0.4 expected Stage 1 shape builder is missing"
    return builder(_PROJECT_ROOT)


def _handoff_type() -> Callable[..., _Handoff]:
    constructor = cast(
        Callable[..., _Handoff] | None,
        getattr(_module(), "V04DatasetHandoffManifest", None),
    )
    assert constructor is not None, "Candidate v0.4 handoff type is missing"
    return constructor


def _excluded_rows(shape: _ExpectedShape) -> tuple[ExcludedProviderRow, ...]:
    return tuple(
        ExcludedProviderRow(
            closure_id=closure_id,
            provider_row_sha256=hashlib.sha256(closure_id.encode()).hexdigest(),
        )
        for closure_id in shape.partial_closure_ids
    )


def _valid_handoff(**overrides: object) -> _Handoff:
    shape = _expected_shape()
    files = (
        ArtifactInventoryEntry(
            path="data/canonical/example/manifest.json",
            size_bytes=1,
            sha256="a" * 64,
        ),
    )
    values: dict[str, object] = {
        "schema_version": "candidate-v0.4-dataset-handoff-v1",
        "repository": "muhamedsohaib/gemini-trading",
        "source_commit": "1" * 40,
        "workflow_name": "candidate-v0.4-stage1",
        "workflow_run_id": 123,
        "workflow_run_attempt": 1,
        "job_name": "dataset",
        "provider": "binance_spot",
        "symbol": "BTCUSDT",
        "base_asset": "BTC",
        "quote_asset": "USDT",
        "interval": "1h",
        "start": "2018-01-01T00:00:00Z",
        "end_exclusive": "2026-08-01T00:00:00Z",
        "run_id": "retrieval-1",
        "dataset_id": "b" * 64,
        "dataset_schema_version": "candidate-v0.4-candle-dataset-v1",
        "closure_manifest_path": "data/canonical/example/exchange-closures.json",
        "closure_manifest_sha256": "c" * 64,
        "exclusion_manifest_path": "data/canonical/example/candle-exclusions.json",
        "exclusion_manifest_sha256": "d" * 64,
        "segment_manifest_path": "data/canonical/example/candle-segments.json",
        "segment_manifest_sha256": "e" * 64,
        "closure_count": shape.closure_count,
        "exclusion_count": shape.exclusion_count,
        "segment_count": shape.segment_count,
        "closure_ids": shape.closure_ids,
        "excluded_provider_rows": _excluded_rows(shape),
        "segment_boundary_indices": shape.segment_boundary_indices,
        "candle_count": shape.candle_count,
        "first_open_time": shape.first_open_time,
        "last_open_time": shape.last_open_time,
        "replay_status": "completed",
        "verification_status": "verified",
        "files": files,
        "inventory_root_sha256": inventory_root_sha256(files),
    }
    values.update(overrides)
    return _handoff_type()(**values)


def test_v0_4_expected_shape_is_derived_from_hourly_closures_not_prices() -> None:
    shape = _expected_shape()

    assert shape.closure_count == len(shape.closure_ids)
    assert shape.exclusion_count == len(shape.partial_closure_ids)
    assert 0 < shape.exclusion_count < shape.closure_count
    assert shape.segment_count == shape.closure_count + 1
    assert len(shape.segment_boundary_indices) == shape.closure_count
    assert shape.segment_boundary_indices == tuple(sorted(set(shape.segment_boundary_indices)))
    assert shape.candle_count < 75_216
    assert shape.first_open_time == "2018-01-01T00:00:00Z"
    assert shape.last_open_time == "2026-07-31T23:00:00Z"


def test_v0_4_handoff_round_trips_canonically() -> None:
    module = _module()
    serializer = cast(
        Callable[[_Handoff], bytes] | None,
        getattr(module, "serialize_v0_4_dataset_handoff", None),
    )
    loader = cast(
        Callable[[bytes], _Handoff] | None,
        getattr(module, "load_v0_4_dataset_handoff", None),
    )
    assert serializer is not None, "Candidate v0.4 handoff serializer is missing"
    assert loader is not None, "Candidate v0.4 handoff loader is missing"

    handoff = _valid_handoff()
    raw = serializer(handoff)
    assert loader(raw) == handoff
    assert serializer(loader(raw)) == raw


def test_v0_4_handoff_rejects_legacy_interval_and_dataset_schema() -> None:
    with pytest.raises(DatasetHandoffError, match="market scope"):
        _valid_handoff(interval="4h")
    with pytest.raises(DatasetHandoffError, match="dataset schema"):
        _valid_handoff(dataset_schema_version="candle-dataset-v4")


def test_v0_4_handoff_rejects_wrong_derived_counts_and_boundaries() -> None:
    shape = _expected_shape()
    with pytest.raises(DatasetHandoffError, match="evidence counts"):
        _valid_handoff(exclusion_count=shape.closure_count)
    with pytest.raises(DatasetHandoffError, match="segment boundaries"):
        _valid_handoff(segment_boundary_indices=shape.segment_boundary_indices[:-1])


def test_v0_4_handoff_rejects_exclusion_for_full_missing_only_closure() -> None:
    shape = _expected_shape()
    full_missing_only = next(
        closure_id
        for closure_id in shape.closure_ids
        if closure_id not in set(shape.partial_closure_ids)
    )
    rows = (
        *_excluded_rows(shape),
        ExcludedProviderRow(
            closure_id=full_missing_only,
            provider_row_sha256=hashlib.sha256(full_missing_only.encode()).hexdigest(),
        ),
    )
    with pytest.raises(DatasetHandoffError, match="excluded provider rows"):
        _valid_handoff(excluded_provider_rows=rows)


def test_v0_4_handoff_rejects_inventory_root_mismatch() -> None:
    with pytest.raises(DatasetHandoffError, match="inventory root"):
        _valid_handoff(inventory_root_sha256="f" * 64)
