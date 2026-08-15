"""Source-linked Candidate v0.4 Stage 1 dataset verification tests."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from pathlib import Path
from typing import Protocol, cast

import pytest

from gemini_trading.strategy.errors import DatasetHandoffError
from gemini_trading.strategy.handoff import (
    ArtifactInventoryEntry,
    ExcludedProviderRow,
    inventory_root_sha256,
)
from gemini_trading.strategy.v0_4_stage1 import build_v0_4_closure_manifest
from gemini_trading.strategy.v0_4_stage1_handoff import (
    V04DatasetHandoffManifest,
    expected_v0_4_stage1_shape,
)

_PROJECT_ROOT = Path(__file__).resolve().parents[3]


class _DatasetManifest(Protocol):
    schema_version: str
    dataset_id: str
    provider: str
    symbol: str
    interval: str
    start: str
    end_exclusive: str
    candle_count: int
    first_open_time: str
    last_open_time: str
    canonical_candles_path: str
    canonical_candles_sha256: str
    source_closure_manifest_sha256: str
    closure_manifest_path: str
    closure_manifest_sha256: str
    closure_count: int
    exclusion_manifest_path: str
    exclusion_manifest_sha256: str
    exclusion_count: int
    segment_manifest_path: str
    segment_manifest_sha256: str
    segment_count: int


def _module() -> object:
    from gemini_trading.strategy import v0_4_stage1_handoff

    return v0_4_stage1_handoff


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _builder() -> Callable[..., _DatasetManifest]:
    value = cast(
        Callable[..., _DatasetManifest] | None,
        getattr(_module(), "build_v0_4_dataset_manifest", None),
    )
    assert value is not None, "Candidate v0.4 dataset-manifest builder is missing"
    return value


def _serializer() -> Callable[[_DatasetManifest], bytes]:
    value = cast(
        Callable[[_DatasetManifest], bytes] | None,
        getattr(_module(), "serialize_v0_4_dataset_manifest", None),
    )
    assert value is not None, "Candidate v0.4 dataset-manifest serializer is missing"
    return value


def _loader() -> Callable[[bytes], _DatasetManifest]:
    value = cast(
        Callable[[bytes], _DatasetManifest] | None,
        getattr(_module(), "load_v0_4_dataset_manifest", None),
    )
    assert value is not None, "Candidate v0.4 dataset-manifest loader is missing"
    return value


def _verifier() -> Callable[..., None]:
    value = cast(
        Callable[..., None] | None,
        getattr(_module(), "verify_v0_4_dataset_handoff", None),
    )
    assert value is not None, "Candidate v0.4 dataset-handoff verifier is missing"
    return value


def _write(root: Path, relative: str, raw: bytes) -> ArtifactInventoryEntry:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return ArtifactInventoryEntry(path=relative, size_bytes=len(raw), sha256=_sha(raw))


def _fixture(root: Path) -> tuple[V04DatasetHandoffManifest, _DatasetManifest]:
    shape = expected_v0_4_stage1_shape(_PROJECT_ROOT)
    closure, closure_raw = build_v0_4_closure_manifest(_PROJECT_ROOT)
    canonical_raw = b'{"test":"canonical-hourly-candles"}\n'
    exclusion_raw = b'{"test":"partial-row-evidence"}\n'
    segment_raw = b'{"test":"segment-evidence"}\n'
    dataset = _builder()(
        canonical_candles_sha256=_sha(canonical_raw),
        source_closure_manifest_sha256=closure.source_manifest_sha256,
        closure_manifest_sha256=_sha(closure_raw),
        exclusion_manifest_sha256=_sha(exclusion_raw),
        segment_manifest_sha256=_sha(segment_raw),
        shape=shape,
    )
    dataset_raw = _serializer()(dataset)
    entries = tuple(
        sorted(
            (
                _write(root, dataset.canonical_candles_path, canonical_raw),
                _write(root, dataset.closure_manifest_path, closure_raw),
                _write(root, dataset.exclusion_manifest_path, exclusion_raw),
                _write(root, dataset.segment_manifest_path, segment_raw),
                _write(
                    root,
                    f"data/canonical/{dataset.dataset_id}/manifest.json",
                    dataset_raw,
                ),
            ),
            key=lambda item: item.path,
        )
    )
    excluded_rows = tuple(
        ExcludedProviderRow(
            closure_id=closure_id,
            provider_row_sha256=hashlib.sha256(closure_id.encode()).hexdigest(),
        )
        for closure_id in shape.partial_closure_ids
    )
    handoff = V04DatasetHandoffManifest(
        schema_version="candidate-v0.4-dataset-handoff-v1",
        repository="muhamedsohaib/gemini-trading",
        source_commit="1" * 40,
        workflow_name="candidate-v0.4-stage1",
        workflow_run_id=123,
        workflow_run_attempt=1,
        job_name="dataset",
        provider="binance_spot",
        symbol="BTCUSDT",
        base_asset="BTC",
        quote_asset="USDT",
        interval="1h",
        start="2018-01-01T00:00:00Z",
        end_exclusive="2026-08-01T00:00:00Z",
        run_id="retrieval-1",
        dataset_id=dataset.dataset_id,
        dataset_schema_version="candidate-v0.4-candle-dataset-v1",
        closure_manifest_path=dataset.closure_manifest_path,
        closure_manifest_sha256=dataset.closure_manifest_sha256,
        exclusion_manifest_path=dataset.exclusion_manifest_path,
        exclusion_manifest_sha256=dataset.exclusion_manifest_sha256,
        segment_manifest_path=dataset.segment_manifest_path,
        segment_manifest_sha256=dataset.segment_manifest_sha256,
        closure_count=shape.closure_count,
        exclusion_count=shape.exclusion_count,
        segment_count=shape.segment_count,
        closure_ids=shape.closure_ids,
        excluded_provider_rows=excluded_rows,
        segment_boundary_indices=shape.segment_boundary_indices,
        candle_count=shape.candle_count,
        first_open_time=shape.first_open_time,
        last_open_time=shape.last_open_time,
        replay_status="completed",
        verification_status="verified",
        files=entries,
        inventory_root_sha256=inventory_root_sha256(entries),
    )
    return handoff, dataset


def test_v0_4_dataset_manifest_round_trips_and_binds_content_identity(tmp_path: Path) -> None:
    _handoff, dataset = _fixture(tmp_path)
    raw = _serializer()(dataset)
    loaded = _loader()(raw)

    assert loaded == dataset
    assert loaded.schema_version == "candidate-v0.4-candle-dataset-v1"
    assert loaded.dataset_id == dataset.dataset_id
    assert loaded.interval == "1h"
    assert loaded.candle_count == expected_v0_4_stage1_shape(_PROJECT_ROOT).candle_count


def test_v0_4_source_linked_handoff_verification_accepts_exact_artifact(tmp_path: Path) -> None:
    handoff, _dataset = _fixture(tmp_path)

    _verifier()(
        handoff,
        tmp_path,
        project_root=_PROJECT_ROOT,
        expected_commit="1" * 40,
        expected_dataset_id=handoff.dataset_id,
        expected_run_id=123,
    )


def test_v0_4_verifier_rejects_full_missing_only_closure_as_exclusion(tmp_path: Path) -> None:
    handoff, _dataset = _fixture(tmp_path)
    shape = expected_v0_4_stage1_shape(_PROJECT_ROOT)
    full_missing_only = next(
        closure_id
        for closure_id in shape.closure_ids
        if closure_id not in set(shape.partial_closure_ids)
    )
    rows = handoff.excluded_provider_rows + (
        ExcludedProviderRow(
            closure_id=full_missing_only,
            provider_row_sha256=hashlib.sha256(b"fabricated").hexdigest(),
        ),
    )
    tampered = V04DatasetHandoffManifest(
        **{
            **handoff.__dict__,
            "excluded_provider_rows": rows,
            "exclusion_count": len(rows),
        }
    )
    with pytest.raises(DatasetHandoffError, match="partial closure"):
        _verifier()(
            tampered,
            tmp_path,
            project_root=_PROJECT_ROOT,
            expected_commit="1" * 40,
            expected_dataset_id=handoff.dataset_id,
            expected_run_id=123,
        )


def test_v0_4_verifier_rejects_inventory_file_tamper(tmp_path: Path) -> None:
    handoff, dataset = _fixture(tmp_path)
    (tmp_path / dataset.canonical_candles_path).write_bytes(b"tampered\n")

    with pytest.raises(DatasetHandoffError, match="inventory"):
        _verifier()(
            handoff,
            tmp_path,
            project_root=_PROJECT_ROOT,
            expected_commit="1" * 40,
            expected_dataset_id=handoff.dataset_id,
            expected_run_id=123,
        )
