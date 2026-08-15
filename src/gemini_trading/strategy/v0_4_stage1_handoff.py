"""Version-isolated Stage 1 shape and handoff evidence for Candidate v0.4."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Never, cast

from gemini_trading.research.serialization import canonical_json_bytes
from gemini_trading.strategy.errors import DatasetHandoffError
from gemini_trading.strategy.handoff import (
    ArtifactInventoryEntry,
    ExcludedProviderRow,
    inventory_root_sha256,
    validate_artifact_relative_path,
)
from gemini_trading.strategy.v0_4_stage1 import (
    V04_STAGE1_END_EXCLUSIVE,
    V04_STAGE1_START,
    build_v0_4_closure_manifest,
)

_HANDOFF_SCHEMA = "candidate-v0.4-dataset-handoff-v1"
_DATASET_SCHEMA = "candidate-v0.4-candle-dataset-v1"
_REPOSITORY = "muhamedsohaib/gemini-trading"
_WORKFLOW_NAME = "candidate-v0.4-stage1"
_JOB_NAME = "dataset"
_PROVIDER = "binance_spot"
_SYMBOL = "BTCUSDT"
_BASE_ASSET = "BTC"
_QUOTE_ASSET = "USDT"
_INTERVAL = "1h"
_START_TEXT = "2018-01-01T00:00:00Z"
_END_TEXT = "2026-08-01T00:00:00Z"
_LAST_OPEN_TEXT = "2026-07-31T23:00:00Z"
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_GIT_COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")
_IDENTITY_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_HANDOFF_FIELDS = {
    "schema_version",
    "repository",
    "source_commit",
    "workflow_name",
    "workflow_run_id",
    "workflow_run_attempt",
    "job_name",
    "provider",
    "symbol",
    "base_asset",
    "quote_asset",
    "interval",
    "start",
    "end_exclusive",
    "run_id",
    "dataset_id",
    "dataset_schema_version",
    "closure_manifest_path",
    "closure_manifest_sha256",
    "exclusion_manifest_path",
    "exclusion_manifest_sha256",
    "segment_manifest_path",
    "segment_manifest_sha256",
    "closure_count",
    "exclusion_count",
    "segment_count",
    "closure_ids",
    "excluded_provider_rows",
    "segment_boundary_indices",
    "candle_count",
    "first_open_time",
    "last_open_time",
    "replay_status",
    "verification_status",
    "files",
    "inventory_root_sha256",
}
_FILE_FIELDS = {"path", "size_bytes", "sha256"}
_EXCLUDED_ROW_FIELDS = {"closure_id", "provider_row_sha256"}


def _fail(message: str) -> Never:
    raise DatasetHandoffError(message)


def _require_sha256(value: str, field_name: str) -> None:
    if _SHA256_PATTERN.fullmatch(value) is None:
        _fail(f"invalid Candidate v0.4 {field_name}")


def _require_positive_int(value: int, field_name: str) -> None:
    if isinstance(value, bool) or value < 1:
        _fail(f"invalid Candidate v0.4 {field_name}")


def _require_non_negative_int(value: int, field_name: str) -> None:
    if isinstance(value, bool) or value < 0:
        _fail(f"invalid Candidate v0.4 {field_name}")


def _require_identity(value: str, field_name: str) -> None:
    if _IDENTITY_PATTERN.fullmatch(value) is None or ".." in value:
        _fail(f"invalid Candidate v0.4 {field_name}")


@dataclass(frozen=True, slots=True)
class V04Stage1ExpectedShape:
    """Price-independent expected shape implied by the frozen hourly outages."""

    closure_count: int
    exclusion_count: int
    segment_count: int
    closure_ids: tuple[str, ...]
    partial_closure_ids: tuple[str, ...]
    segment_boundary_indices: tuple[int, ...]
    candle_count: int
    first_open_time: str
    last_open_time: str

    def __post_init__(self) -> None:
        if self.closure_count != len(self.closure_ids) or self.closure_count < 1:
            _fail("Candidate v0.4 expected closure count mismatch")
        if self.exclusion_count != len(self.partial_closure_ids):
            _fail("Candidate v0.4 expected exclusion count mismatch")
        if not 0 <= self.exclusion_count <= self.closure_count:
            _fail("Candidate v0.4 expected evidence counts are invalid")
        if self.segment_count != self.closure_count + 1:
            _fail("Candidate v0.4 expected segment count mismatch")
        if len(self.segment_boundary_indices) != self.closure_count:
            _fail("Candidate v0.4 expected segment boundary count mismatch")
        if self.segment_boundary_indices != tuple(
            sorted(set(self.segment_boundary_indices))
        ):
            _fail("Candidate v0.4 expected segment boundaries are invalid")
        if self.candle_count < 1:
            _fail("Candidate v0.4 expected candle count must be positive")
        if (self.first_open_time, self.last_open_time) != (
            _START_TEXT,
            _LAST_OPEN_TEXT,
        ):
            _fail("Candidate v0.4 expected candle boundaries changed")


def expected_v0_4_stage1_shape(project_root: Path) -> V04Stage1ExpectedShape:
    """Derive exact Stage 1 counts and segment boundaries without using price data."""

    closure_manifest, _ = build_v0_4_closure_manifest(project_root)
    total_slots = (
        V04_STAGE1_END_EXCLUSIVE - V04_STAGE1_START
    ) // timedelta(hours=1)
    cumulative_unavailable = 0
    boundaries: list[int] = []
    for closure in closure_manifest.closures:
        cumulative_unavailable += closure.unavailable_candle_count
        raw_resume_index = (closure.resumed_open - V04_STAGE1_START) // timedelta(hours=1)
        boundary_index = raw_resume_index - cumulative_unavailable
        if boundary_index < 1:
            _fail("Candidate v0.4 derived segment boundary is invalid")
        boundaries.append(boundary_index)
    candle_count = total_slots - cumulative_unavailable
    return V04Stage1ExpectedShape(
        closure_count=len(closure_manifest.closures),
        exclusion_count=sum(item.partial_candle is not None for item in closure_manifest.closures),
        segment_count=len(closure_manifest.closures) + 1,
        closure_ids=tuple(item.closure_id for item in closure_manifest.closures),
        partial_closure_ids=tuple(
            item.closure_id for item in closure_manifest.closures if item.partial_candle is not None
        ),
        segment_boundary_indices=tuple(boundaries),
        candle_count=candle_count,
        first_open_time=_START_TEXT,
        last_open_time=_LAST_OPEN_TEXT,
    )


@dataclass(frozen=True, slots=True)
class V04DatasetHandoffManifest:
    """Immutable handoff for one exact Candidate v0.4 hourly Stage 1 artifact."""

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
    closure_manifest_path: str
    closure_manifest_sha256: str
    exclusion_manifest_path: str
    exclusion_manifest_sha256: str
    segment_manifest_path: str
    segment_manifest_sha256: str
    closure_count: int
    exclusion_count: int
    segment_count: int
    closure_ids: tuple[str, ...]
    excluded_provider_rows: tuple[ExcludedProviderRow, ...]
    segment_boundary_indices: tuple[int, ...]
    candle_count: int
    first_open_time: str
    last_open_time: str
    replay_status: str
    verification_status: str
    files: tuple[ArtifactInventoryEntry, ...]
    inventory_root_sha256: str

    def __post_init__(self) -> None:
        if self.schema_version != _HANDOFF_SCHEMA:
            _fail("unsupported Candidate v0.4 dataset handoff schema")
        if self.repository != _REPOSITORY:
            _fail("Candidate v0.4 handoff repository mismatch")
        if _GIT_COMMIT_PATTERN.fullmatch(self.source_commit) is None:
            _fail("invalid Candidate v0.4 source commit")
        if self.workflow_name != _WORKFLOW_NAME or self.job_name != _JOB_NAME:
            _fail("Candidate v0.4 handoff workflow identity mismatch")
        _require_positive_int(self.workflow_run_id, "workflow run ID")
        _require_positive_int(self.workflow_run_attempt, "workflow run attempt")
        if (self.provider, self.symbol, self.base_asset, self.quote_asset, self.interval) != (
            _PROVIDER,
            _SYMBOL,
            _BASE_ASSET,
            _QUOTE_ASSET,
            _INTERVAL,
        ):
            _fail("Candidate v0.4 handoff market scope mismatch")
        if (self.start, self.end_exclusive) != (_START_TEXT, _END_TEXT):
            _fail("Candidate v0.4 handoff historical window mismatch")
        _require_identity(self.run_id, "retrieval run ID")
        _require_sha256(self.dataset_id, "dataset ID")
        if self.dataset_schema_version != _DATASET_SCHEMA:
            _fail("Candidate v0.4 handoff dataset schema mismatch")
        object.__setattr__(
            self,
            "closure_manifest_path",
            validate_artifact_relative_path(self.closure_manifest_path),
        )
        object.__setattr__(
            self,
            "exclusion_manifest_path",
            validate_artifact_relative_path(self.exclusion_manifest_path),
        )
        object.__setattr__(
            self,
            "segment_manifest_path",
            validate_artifact_relative_path(self.segment_manifest_path),
        )
        _require_sha256(self.closure_manifest_sha256, "closure manifest SHA-256")
        _require_sha256(self.exclusion_manifest_sha256, "exclusion manifest SHA-256")
        _require_sha256(self.segment_manifest_sha256, "segment manifest SHA-256")
        _require_positive_int(self.closure_count, "closure count")
        _require_non_negative_int(self.exclusion_count, "exclusion count")
        _require_positive_int(self.segment_count, "segment count")
        if (
            self.closure_count != len(self.closure_ids)
            or self.exclusion_count != len(self.excluded_provider_rows)
            or self.exclusion_count > self.closure_count
            or self.segment_count != self.closure_count + 1
        ):
            _fail("Candidate v0.4 handoff evidence counts mismatch")
        if self.closure_ids != tuple(dict.fromkeys(self.closure_ids)):
            _fail("duplicate Candidate v0.4 handoff closure ID")
        for closure_id in self.closure_ids:
            _require_identity(closure_id, "closure ID")
        excluded_ids = tuple(item.closure_id for item in self.excluded_provider_rows)
        excluded_hashes = tuple(item.provider_row_sha256 for item in self.excluded_provider_rows)
        if len(set(excluded_ids)) != len(excluded_ids) or not set(excluded_ids) <= set(
            self.closure_ids
        ):
            _fail("Candidate v0.4 handoff excluded provider rows mismatch")
        if len(set(excluded_hashes)) != len(excluded_hashes):
            _fail("duplicate Candidate v0.4 handoff excluded row digest")
        if (
            len(self.segment_boundary_indices) != self.closure_count
            or self.segment_boundary_indices
            != tuple(sorted(set(self.segment_boundary_indices)))
        ):
            _fail("Candidate v0.4 handoff segment boundaries mismatch")
        for boundary in self.segment_boundary_indices:
            _require_positive_int(boundary, "segment boundary index")
        _require_positive_int(self.candle_count, "candle count")
        if (self.first_open_time, self.last_open_time) != (
            _START_TEXT,
            _LAST_OPEN_TEXT,
        ):
            _fail("Candidate v0.4 handoff candle boundary mismatch")
        if self.replay_status != "completed" or self.verification_status != "verified":
            _fail("Candidate v0.4 handoff is not verified")
        if not self.files:
            _fail("Candidate v0.4 handoff file inventory is empty")
        if tuple(item.path for item in self.files) != tuple(
            sorted(item.path for item in self.files)
        ):
            _fail("Candidate v0.4 handoff file inventory is not sorted")
        if len({item.path for item in self.files}) != len(self.files):
            _fail("duplicate Candidate v0.4 artifact-relative path")
        _require_sha256(self.inventory_root_sha256, "inventory root")
        if inventory_root_sha256(self.files) != self.inventory_root_sha256:
            _fail("Candidate v0.4 dataset inventory root mismatch")


def _handoff_payload(manifest: V04DatasetHandoffManifest) -> dict[str, object]:
    return {
        "schema_version": manifest.schema_version,
        "repository": manifest.repository,
        "source_commit": manifest.source_commit,
        "workflow_name": manifest.workflow_name,
        "workflow_run_id": manifest.workflow_run_id,
        "workflow_run_attempt": manifest.workflow_run_attempt,
        "job_name": manifest.job_name,
        "provider": manifest.provider,
        "symbol": manifest.symbol,
        "base_asset": manifest.base_asset,
        "quote_asset": manifest.quote_asset,
        "interval": manifest.interval,
        "start": manifest.start,
        "end_exclusive": manifest.end_exclusive,
        "run_id": manifest.run_id,
        "dataset_id": manifest.dataset_id,
        "dataset_schema_version": manifest.dataset_schema_version,
        "closure_manifest_path": manifest.closure_manifest_path,
        "closure_manifest_sha256": manifest.closure_manifest_sha256,
        "exclusion_manifest_path": manifest.exclusion_manifest_path,
        "exclusion_manifest_sha256": manifest.exclusion_manifest_sha256,
        "segment_manifest_path": manifest.segment_manifest_path,
        "segment_manifest_sha256": manifest.segment_manifest_sha256,
        "closure_count": manifest.closure_count,
        "exclusion_count": manifest.exclusion_count,
        "segment_count": manifest.segment_count,
        "closure_ids": list(manifest.closure_ids),
        "excluded_provider_rows": [
            {
                "closure_id": item.closure_id,
                "provider_row_sha256": item.provider_row_sha256,
            }
            for item in manifest.excluded_provider_rows
        ],
        "segment_boundary_indices": list(manifest.segment_boundary_indices),
        "candle_count": manifest.candle_count,
        "first_open_time": manifest.first_open_time,
        "last_open_time": manifest.last_open_time,
        "replay_status": manifest.replay_status,
        "verification_status": manifest.verification_status,
        "files": [
            {"path": item.path, "size_bytes": item.size_bytes, "sha256": item.sha256}
            for item in manifest.files
        ],
        "inventory_root_sha256": manifest.inventory_root_sha256,
    }


def serialize_v0_4_dataset_handoff(manifest: V04DatasetHandoffManifest) -> bytes:
    """Serialize one Candidate v0.4 handoff using canonical JSON bytes."""

    return canonical_json_bytes(_handoff_payload(manifest))


def _mapping(value: object, description: str) -> dict[str, object]:
    if not isinstance(value, dict):
        _fail(f"invalid Candidate v0.4 {description}")
    raw = cast(dict[object, object], value)
    if not all(isinstance(key, str) for key in raw):
        _fail(f"invalid Candidate v0.4 {description}")
    return cast(dict[str, object], raw)


def _exact_fields(mapping: dict[str, object], expected: set[str], description: str) -> None:
    if set(mapping) != expected:
        _fail(f"invalid Candidate v0.4 {description} fields")


def _string(mapping: dict[str, object], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str):
        _fail(f"invalid Candidate v0.4 handoff field: {key}")
    return value


def _integer(mapping: dict[str, object], key: str) -> int:
    value = mapping.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        _fail(f"invalid Candidate v0.4 handoff field: {key}")
    return value


def _strings(mapping: dict[str, object], key: str) -> tuple[str, ...]:
    value = mapping.get(key)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        _fail(f"invalid Candidate v0.4 handoff field: {key}")
    return tuple(cast(list[str], value))


def _integers(mapping: dict[str, object], key: str) -> tuple[int, ...]:
    value = mapping.get(key)
    if not isinstance(value, list) or not all(
        isinstance(item, int) and not isinstance(item, bool) for item in value
    ):
        _fail(f"invalid Candidate v0.4 handoff field: {key}")
    return tuple(cast(list[int], value))


def _excluded_rows(mapping: dict[str, object]) -> tuple[ExcludedProviderRow, ...]:
    raw_rows = mapping.get("excluded_provider_rows")
    if not isinstance(raw_rows, list):
        _fail("invalid Candidate v0.4 excluded provider rows")
    rows: list[ExcludedProviderRow] = []
    for raw_row in cast(list[object], raw_rows):
        row = _mapping(raw_row, "excluded provider row")
        _exact_fields(row, _EXCLUDED_ROW_FIELDS, "excluded provider row")
        rows.append(
            ExcludedProviderRow(
                closure_id=_string(row, "closure_id"),
                provider_row_sha256=_string(row, "provider_row_sha256"),
            )
        )
    return tuple(rows)


def _files(mapping: dict[str, object]) -> tuple[ArtifactInventoryEntry, ...]:
    raw_files = mapping.get("files")
    if not isinstance(raw_files, list):
        _fail("invalid Candidate v0.4 file inventory")
    files: list[ArtifactInventoryEntry] = []
    for raw_file in cast(list[object], raw_files):
        item = _mapping(raw_file, "file inventory entry")
        _exact_fields(item, _FILE_FIELDS, "file inventory entry")
        files.append(
            ArtifactInventoryEntry(
                path=_string(item, "path"),
                size_bytes=_integer(item, "size_bytes"),
                sha256=_string(item, "sha256"),
            )
        )
    return tuple(files)


def load_v0_4_dataset_handoff(raw: bytes) -> V04DatasetHandoffManifest:
    """Load canonical Candidate v0.4 handoff bytes and reject alternate encodings."""

    try:
        loaded: object = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        _fail("Candidate v0.4 handoff is not valid JSON")
    mapping = _mapping(loaded, "dataset handoff")
    _exact_fields(mapping, _HANDOFF_FIELDS, "dataset handoff")
    manifest = V04DatasetHandoffManifest(
        schema_version=_string(mapping, "schema_version"),
        repository=_string(mapping, "repository"),
        source_commit=_string(mapping, "source_commit"),
        workflow_name=_string(mapping, "workflow_name"),
        workflow_run_id=_integer(mapping, "workflow_run_id"),
        workflow_run_attempt=_integer(mapping, "workflow_run_attempt"),
        job_name=_string(mapping, "job_name"),
        provider=_string(mapping, "provider"),
        symbol=_string(mapping, "symbol"),
        base_asset=_string(mapping, "base_asset"),
        quote_asset=_string(mapping, "quote_asset"),
        interval=_string(mapping, "interval"),
        start=_string(mapping, "start"),
        end_exclusive=_string(mapping, "end_exclusive"),
        run_id=_string(mapping, "run_id"),
        dataset_id=_string(mapping, "dataset_id"),
        dataset_schema_version=_string(mapping, "dataset_schema_version"),
        closure_manifest_path=_string(mapping, "closure_manifest_path"),
        closure_manifest_sha256=_string(mapping, "closure_manifest_sha256"),
        exclusion_manifest_path=_string(mapping, "exclusion_manifest_path"),
        exclusion_manifest_sha256=_string(mapping, "exclusion_manifest_sha256"),
        segment_manifest_path=_string(mapping, "segment_manifest_path"),
        segment_manifest_sha256=_string(mapping, "segment_manifest_sha256"),
        closure_count=_integer(mapping, "closure_count"),
        exclusion_count=_integer(mapping, "exclusion_count"),
        segment_count=_integer(mapping, "segment_count"),
        closure_ids=_strings(mapping, "closure_ids"),
        excluded_provider_rows=_excluded_rows(mapping),
        segment_boundary_indices=_integers(mapping, "segment_boundary_indices"),
        candle_count=_integer(mapping, "candle_count"),
        first_open_time=_string(mapping, "first_open_time"),
        last_open_time=_string(mapping, "last_open_time"),
        replay_status=_string(mapping, "replay_status"),
        verification_status=_string(mapping, "verification_status"),
        files=_files(mapping),
        inventory_root_sha256=_string(mapping, "inventory_root_sha256"),
    )
    if serialize_v0_4_dataset_handoff(manifest) != raw:
        _fail("Candidate v0.4 handoff encoding is not canonical")
    return manifest


__all__ = [
    "V04DatasetHandoffManifest",
    "V04Stage1ExpectedShape",
    "expected_v0_4_stage1_shape",
    "load_v0_4_dataset_handoff",
    "serialize_v0_4_dataset_handoff",
]
