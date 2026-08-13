"""Version-isolated Stage 1 dataset contract for Candidate v0.3."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from gemini_trading.data.exchange_closures import (
    ExchangeClosureManifest,
    load_exchange_closure_manifest,
    load_fixed_btcusdt_closure_manifest,
    serialize_exchange_closure_manifest,
)
from gemini_trading.data.exclusions import load_candle_exclusion_manifest
from gemini_trading.data.segments import load_candle_segment_manifest
from gemini_trading.data.storage.local_immutable import LocalImmutableStore, write_immutable
from gemini_trading.data.verification.service import VerificationService
from gemini_trading.research.dataset_reader import VerifiedDataset, load_verified_dataset
from gemini_trading.research.serialization import canonical_json_bytes
from gemini_trading.strategy.errors import DatasetHandoffError, HistoricalValidationError
from gemini_trading.strategy.handoff import (
    ArtifactInventoryEntry,
    ExcludedProviderRow,
    build_artifact_inventory,
    inventory_root_sha256,
    validate_artifact_relative_path,
)
from gemini_trading.strategy.sealed_dataset_identity import (
    EXPECTED_BOUNDARIES,
    EXPECTED_CLOSURE_IDS,
    EXPECTED_COUNTS,
    EXPECTED_EXCLUDED_PROVIDER_ROWS,
)

V03_STAGE1_START = datetime(2018, 1, 1, tzinfo=UTC)
V03_STAGE1_END_EXCLUSIVE = datetime(2026, 8, 1, tzinfo=UTC)
V03_EXPECTED_CANDLE_COUNT = 18_768
V03_EXPECTED_FIRST_OPEN_TIME = "2018-01-01T00:00:00Z"
V03_EXPECTED_LAST_OPEN_TIME = "2026-07-31T20:00:00Z"

_SCHEMA_VERSION = "candidate-v0.3-dataset-handoff-v1"
_REPOSITORY = "muhamedsohaib/gemini-trading"
_WORKFLOW_NAME = "candidate-v0.3-stage1"
_JOB_NAME = "dataset"
_PROVIDER = "binance_spot"
_SYMBOL = "BTCUSDT"
_BASE_ASSET = "BTC"
_QUOTE_ASSET = "USDT"
_INTERVAL = "4h"
_START_TEXT = "2018-01-01T00:00:00Z"
_END_TEXT = "2026-08-01T00:00:00Z"
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_GIT_COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")
_IDENTITY_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_HANDOFF_NAME = "dataset-handoff.json"
_ALLOWED_FIELDS = {
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


def _utc_text(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _require_sha256(value: str, field_name: str) -> None:
    if _SHA256_PATTERN.fullmatch(value) is None:
        raise DatasetHandoffError(f"invalid v0.3 Stage 1 {field_name}")


def _require_positive_int(value: int, field_name: str) -> None:
    if isinstance(value, bool) or value < 1:
        raise DatasetHandoffError(f"invalid v0.3 Stage 1 {field_name}")


def _require_identity(value: str, field_name: str) -> None:
    if _IDENTITY_PATTERN.fullmatch(value) is None or ".." in value:
        raise DatasetHandoffError(f"invalid v0.3 Stage 1 {field_name}")


def build_v0_3_closure_manifest(
    project_root: Path,
) -> tuple[ExchangeClosureManifest, bytes]:
    """Extend only the approved retrieval boundary while preserving closure declarations."""

    base, _ = load_fixed_btcusdt_closure_manifest(project_root)
    if base.start_time != V03_STAGE1_START:
        raise DatasetHandoffError("v0.3 Stage 1 start boundary changed")
    if base.end_time > V03_STAGE1_END_EXCLUSIVE:
        raise DatasetHandoffError("v0.3 Stage 1 base closure window exceeds the locked cutoff")
    manifest = replace(base, end_time=V03_STAGE1_END_EXCLUSIVE)
    raw = serialize_exchange_closure_manifest(manifest)
    return manifest, raw


def assert_v0_3_dataset_identity(dataset: VerifiedDataset, project_root: Path) -> None:
    """Require the exact Candidate v0.3 development dataset shape and closure evidence."""

    expected_closure, expected_closure_bytes = build_v0_3_closure_manifest(project_root)
    if dataset.manifest.schema_version != "candle-dataset-v4":
        raise DatasetHandoffError("v0.3 Stage 1 requires candle-dataset-v4")
    if (
        dataset.manifest.start_time != V03_STAGE1_START
        or dataset.manifest.end_time != V03_STAGE1_END_EXCLUSIVE
    ):
        raise DatasetHandoffError("v0.3 Stage 1 historical window mismatch")
    if len(dataset.candles) != V03_EXPECTED_CANDLE_COUNT:
        raise DatasetHandoffError("v0.3 Stage 1 candle count mismatch")
    if not dataset.candles:
        raise DatasetHandoffError("v0.3 Stage 1 dataset is empty")
    if _utc_text(dataset.candles[0].open_time) != V03_EXPECTED_FIRST_OPEN_TIME:
        raise DatasetHandoffError("v0.3 Stage 1 first candle changed")
    if _utc_text(dataset.candles[-1].open_time) != V03_EXPECTED_LAST_OPEN_TIME:
        raise DatasetHandoffError("v0.3 Stage 1 last candle changed")
    if any(candle.open_time >= V03_STAGE1_END_EXCLUSIVE for candle in dataset.candles):
        raise DatasetHandoffError("v0.3 Stage 1 contains post-cutoff candles")
    if (
        dataset.closure_manifest is None
        or dataset.exclusion_manifest is None
        or dataset.segment_manifest is None
    ):
        raise DatasetHandoffError("v0.3 Stage 1 supporting evidence is incomplete")
    actual_closure_bytes = serialize_exchange_closure_manifest(dataset.closure_manifest)
    if actual_closure_bytes != expected_closure_bytes:
        raise DatasetHandoffError("v0.3 Stage 1 closure evidence changed")
    if dataset.closure_manifest != expected_closure:
        raise DatasetHandoffError("v0.3 Stage 1 closure declarations changed")
    closure_sha = hashlib.sha256(expected_closure_bytes).hexdigest()
    if dataset.manifest.closure_manifest_sha256 != closure_sha:
        raise DatasetHandoffError("v0.3 Stage 1 closure manifest identity changed")
    counts = (
        dataset.manifest.closure_count,
        dataset.manifest.exclusion_count,
        dataset.manifest.segment_count,
    )
    if counts != EXPECTED_COUNTS:
        raise DatasetHandoffError("v0.3 Stage 1 closure/exclusion/segment counts changed")
    closure_ids = tuple(item.closure_id for item in dataset.closure_manifest.closures)
    if closure_ids != EXPECTED_CLOSURE_IDS:
        raise DatasetHandoffError("v0.3 Stage 1 closure IDs changed")
    excluded_rows = tuple(
        ExcludedProviderRow(item.closure_id, item.provider_row_sha256)
        for item in dataset.exclusion_manifest.exclusions
    )
    if excluded_rows != EXPECTED_EXCLUDED_PROVIDER_ROWS:
        raise DatasetHandoffError("v0.3 Stage 1 excluded provider rows changed")
    if dataset.segment_manifest.boundary_indices != EXPECTED_BOUNDARIES:
        raise DatasetHandoffError("v0.3 Stage 1 segment boundaries changed")


@dataclass(frozen=True, slots=True)
class V03DatasetHandoffManifest:
    """Strict Stage 1 handoff isolated from the legacy sealed dataset identity."""

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
        if self.schema_version != _SCHEMA_VERSION:
            raise DatasetHandoffError("unsupported v0.3 Stage 1 handoff schema")
        if self.repository != _REPOSITORY:
            raise DatasetHandoffError("v0.3 Stage 1 handoff repository mismatch")
        if _GIT_COMMIT_PATTERN.fullmatch(self.source_commit) is None:
            raise DatasetHandoffError("invalid v0.3 Stage 1 source commit")
        if self.workflow_name != _WORKFLOW_NAME or self.job_name != _JOB_NAME:
            raise DatasetHandoffError("v0.3 Stage 1 workflow identity mismatch")
        _require_positive_int(self.workflow_run_id, "workflow run ID")
        _require_positive_int(self.workflow_run_attempt, "workflow run attempt")
        if self.provider != _PROVIDER:
            raise DatasetHandoffError("v0.3 Stage 1 provider mismatch")
        if (self.symbol, self.base_asset, self.quote_asset, self.interval) != (
            _SYMBOL,
            _BASE_ASSET,
            _QUOTE_ASSET,
            _INTERVAL,
        ):
            raise DatasetHandoffError("v0.3 Stage 1 market scope mismatch")
        if (self.start, self.end_exclusive) != (_START_TEXT, _END_TEXT):
            raise DatasetHandoffError("v0.3 Stage 1 historical window mismatch")
        _require_identity(self.run_id, "retrieval run ID")
        _require_sha256(self.dataset_id, "dataset ID")
        if self.dataset_schema_version != "candle-dataset-v4":
            raise DatasetHandoffError("v0.3 Stage 1 requires candle-dataset-v4")
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
        if (self.closure_count, self.exclusion_count, self.segment_count) != EXPECTED_COUNTS:
            raise DatasetHandoffError("v0.3 Stage 1 evidence counts mismatch")
        if self.closure_ids != EXPECTED_CLOSURE_IDS:
            raise DatasetHandoffError("v0.3 Stage 1 closure IDs mismatch")
        if self.excluded_provider_rows != EXPECTED_EXCLUDED_PROVIDER_ROWS:
            raise DatasetHandoffError("v0.3 Stage 1 excluded provider rows mismatch")
        if self.segment_boundary_indices != EXPECTED_BOUNDARIES:
            raise DatasetHandoffError("v0.3 Stage 1 segment boundaries mismatch")
        if self.candle_count != V03_EXPECTED_CANDLE_COUNT:
            raise DatasetHandoffError("v0.3 Stage 1 candle count mismatch")
        if (
            self.first_open_time != V03_EXPECTED_FIRST_OPEN_TIME
            or self.last_open_time != V03_EXPECTED_LAST_OPEN_TIME
        ):
            raise DatasetHandoffError("v0.3 Stage 1 candle boundary mismatch")
        if self.replay_status != "completed" or self.verification_status != "verified":
            raise DatasetHandoffError("v0.3 Stage 1 is not verified")
        if not self.files:
            raise DatasetHandoffError("v0.3 Stage 1 artifact inventory is empty")
        if tuple(item.path for item in self.files) != tuple(sorted(item.path for item in self.files)):
            raise DatasetHandoffError("v0.3 Stage 1 artifact inventory is not sorted")
        if len({item.path for item in self.files}) != len(self.files):
            raise DatasetHandoffError("duplicate v0.3 Stage 1 artifact path")
        _require_sha256(self.inventory_root_sha256, "inventory root")
        if inventory_root_sha256(self.files) != self.inventory_root_sha256:
            raise DatasetHandoffError("v0.3 Stage 1 inventory root mismatch")


def _handoff_payload(manifest: V03DatasetHandoffManifest) -> dict[str, object]:
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


def serialize_v0_3_dataset_handoff(manifest: V03DatasetHandoffManifest) -> bytes:
    """Serialize the exact Candidate v0.3 Stage 1 handoff canonically."""

    return canonical_json_bytes(_handoff_payload(manifest))


def _mapping(value: object, description: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise DatasetHandoffError(f"invalid v0.3 Stage 1 {description}")
    raw = cast(dict[object, object], value)
    if not all(isinstance(key, str) for key in raw):
        raise DatasetHandoffError(f"invalid v0.3 Stage 1 {description}")
    return cast(dict[str, object], raw)


def _exact_fields(mapping: dict[str, object], expected: set[str], description: str) -> None:
    if set(mapping) != expected:
        raise DatasetHandoffError(f"invalid v0.3 Stage 1 {description} fields")


def _string(mapping: dict[str, object], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str):
        raise DatasetHandoffError(f"invalid v0.3 Stage 1 field: {key}")
    return value


def _integer(mapping: dict[str, object], key: str) -> int:
    value = mapping.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise DatasetHandoffError(f"invalid v0.3 Stage 1 field: {key}")
    return value


def _strings(mapping: dict[str, object], key: str) -> tuple[str, ...]:
    value = mapping.get(key)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise DatasetHandoffError(f"invalid v0.3 Stage 1 field: {key}")
    return tuple(cast(list[str], value))


def _integers(mapping: dict[str, object], key: str) -> tuple[int, ...]:
    value = mapping.get(key)
    if not isinstance(value, list):
        raise DatasetHandoffError(f"invalid v0.3 Stage 1 field: {key}")
    raw = cast(list[object], value)
    if not all(isinstance(item, int) and not isinstance(item, bool) for item in raw):
        raise DatasetHandoffError(f"invalid v0.3 Stage 1 field: {key}")
    return tuple(cast(list[int], raw))


def load_v0_3_dataset_handoff(raw: bytes) -> V03DatasetHandoffManifest:
    """Parse exact v0.3 handoff bytes and reject alternate encodings or fields."""

    try:
        loaded: object = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise DatasetHandoffError("invalid v0.3 Stage 1 handoff JSON") from None
    mapping = _mapping(loaded, "handoff")
    _exact_fields(mapping, _ALLOWED_FIELDS, "handoff")
    raw_files = mapping.get("files")
    if not isinstance(raw_files, list):
        raise DatasetHandoffError("invalid v0.3 Stage 1 field: files")
    files: list[ArtifactInventoryEntry] = []
    for value in cast(list[object], raw_files):
        item = _mapping(value, "artifact file")
        _exact_fields(item, _FILE_FIELDS, "artifact file")
        files.append(
            ArtifactInventoryEntry(
                path=_string(item, "path"),
                size_bytes=_integer(item, "size_bytes"),
                sha256=_string(item, "sha256"),
            )
        )
    raw_rows = mapping.get("excluded_provider_rows")
    if not isinstance(raw_rows, list):
        raise DatasetHandoffError("invalid v0.3 Stage 1 field: excluded_provider_rows")
    excluded_rows: list[ExcludedProviderRow] = []
    for value in cast(list[object], raw_rows):
        item = _mapping(value, "excluded provider row")
        _exact_fields(item, _EXCLUDED_ROW_FIELDS, "excluded provider row")
        excluded_rows.append(
            ExcludedProviderRow(
                closure_id=_string(item, "closure_id"),
                provider_row_sha256=_string(item, "provider_row_sha256"),
            )
        )
    manifest = V03DatasetHandoffManifest(
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
        excluded_provider_rows=tuple(excluded_rows),
        segment_boundary_indices=_integers(mapping, "segment_boundary_indices"),
        candle_count=_integer(mapping, "candle_count"),
        first_open_time=_string(mapping, "first_open_time"),
        last_open_time=_string(mapping, "last_open_time"),
        replay_status=_string(mapping, "replay_status"),
        verification_status=_string(mapping, "verification_status"),
        files=tuple(files),
        inventory_root_sha256=_string(mapping, "inventory_root_sha256"),
    )
    if serialize_v0_3_dataset_handoff(manifest) != raw:
        raise DatasetHandoffError("v0.3 Stage 1 handoff encoding is not canonical")
    return manifest


def _handoff_path(output_root: Path, dataset_id: str) -> Path:
    return (
        output_root
        / "data"
        / "historical-validation"
        / "handoff"
        / dataset_id
        / _HANDOFF_NAME
    )


def create_v0_3_dataset_handoff(
    *,
    project_root: Path,
    output_root: Path,
    run_id: str,
    dataset_id: str,
    source_commit: str,
    workflow_run_id: int,
    workflow_run_attempt: int,
) -> tuple[V03DatasetHandoffManifest, Path]:
    """Build and persist one exact verified Candidate v0.3 Stage 1 handoff."""

    store = LocalImmutableStore(output_root)
    verification = VerificationService(raw_store=store, canonical_store=store).verify(
        dataset_id, run_id
    )
    dataset = load_verified_dataset(store, dataset_id, require_v4=True)
    assert_v0_3_dataset_identity(dataset, project_root)
    if verification.candle_count != V03_EXPECTED_CANDLE_COUNT:
        raise DatasetHandoffError("v0.3 Stage 1 verification candle count changed")
    raw_root = output_root / "data" / "raw" / "binance_spot" / run_id
    canonical_root = output_root / "data" / "canonical" / dataset_id
    relative_paths = tuple(
        sorted(
            path.relative_to(output_root).as_posix()
            for base in (raw_root, canonical_root)
            for path in base.rglob("*")
            if path.is_file()
        )
    )
    try:
        files = build_artifact_inventory(output_root, relative_paths)
    except HistoricalValidationError as error:
        raise DatasetHandoffError(str(error)) from None
    if (
        dataset.closure_manifest is None
        or dataset.exclusion_manifest is None
        or dataset.segment_manifest is None
        or dataset.manifest.closure_manifest_sha256 is None
        or dataset.manifest.exclusion_manifest_sha256 is None
        or dataset.manifest.segment_manifest_sha256 is None
    ):
        raise DatasetHandoffError("v0.3 Stage 1 supporting identity is incomplete")
    excluded_rows = tuple(
        ExcludedProviderRow(item.closure_id, item.provider_row_sha256)
        for item in dataset.exclusion_manifest.exclusions
    )
    manifest = V03DatasetHandoffManifest(
        schema_version=_SCHEMA_VERSION,
        repository=_REPOSITORY,
        source_commit=source_commit,
        workflow_name=_WORKFLOW_NAME,
        workflow_run_id=workflow_run_id,
        workflow_run_attempt=workflow_run_attempt,
        job_name=_JOB_NAME,
        provider=dataset.manifest.provider,
        symbol=dataset.manifest.instrument.symbol,
        base_asset=dataset.manifest.instrument.base_asset,
        quote_asset=dataset.manifest.instrument.quote_asset,
        interval=dataset.manifest.timeframe.value,
        start=_utc_text(dataset.manifest.start_time),
        end_exclusive=_utc_text(dataset.manifest.end_time),
        run_id=run_id,
        dataset_id=dataset_id,
        dataset_schema_version=dataset.manifest.schema_version,
        closure_manifest_path=(canonical_root / "exchange-closures.json")
        .relative_to(output_root)
        .as_posix(),
        closure_manifest_sha256=dataset.manifest.closure_manifest_sha256,
        exclusion_manifest_path=(canonical_root / "candle-exclusions.json")
        .relative_to(output_root)
        .as_posix(),
        exclusion_manifest_sha256=dataset.manifest.exclusion_manifest_sha256,
        segment_manifest_path=(canonical_root / "candle-segments.json")
        .relative_to(output_root)
        .as_posix(),
        segment_manifest_sha256=dataset.manifest.segment_manifest_sha256,
        closure_count=dataset.manifest.closure_count,
        exclusion_count=dataset.manifest.exclusion_count,
        segment_count=dataset.manifest.segment_count,
        closure_ids=tuple(item.closure_id for item in dataset.closure_manifest.closures),
        excluded_provider_rows=excluded_rows,
        segment_boundary_indices=dataset.segment_manifest.boundary_indices,
        candle_count=verification.candle_count,
        first_open_time=_utc_text(dataset.manifest.first_open_time),
        last_open_time=_utc_text(dataset.manifest.last_open_time),
        replay_status="completed",
        verification_status="verified",
        files=files,
        inventory_root_sha256=inventory_root_sha256(files),
    )
    path = _handoff_path(output_root, dataset_id)
    write_immutable(path, serialize_v0_3_dataset_handoff(manifest))
    verify_v0_3_dataset_handoff(
        manifest,
        output_root,
        project_root=project_root,
        expected_commit=source_commit,
        expected_dataset_id=dataset_id,
        expected_run_id=workflow_run_id,
    )
    return manifest, path


def verify_v0_3_dataset_handoff(
    manifest: V03DatasetHandoffManifest,
    artifact_root: Path,
    *,
    project_root: Path,
    expected_commit: str | None = None,
    expected_dataset_id: str | None = None,
    expected_run_id: int | None = None,
) -> None:
    """Independently recompute the complete v0.3 Stage 1 handoff inventory."""

    if expected_commit is not None and manifest.source_commit != expected_commit:
        raise DatasetHandoffError("v0.3 Stage 1 source commit mismatch")
    if expected_dataset_id is not None and manifest.dataset_id != expected_dataset_id:
        raise DatasetHandoffError("v0.3 Stage 1 dataset identity mismatch")
    if expected_run_id is not None and manifest.workflow_run_id != expected_run_id:
        raise DatasetHandoffError("v0.3 Stage 1 workflow run mismatch")
    expected_closure, expected_closure_bytes = build_v0_3_closure_manifest(project_root)
    try:
        closure_bytes = (artifact_root / manifest.closure_manifest_path).read_bytes()
        exclusion_bytes = (artifact_root / manifest.exclusion_manifest_path).read_bytes()
        segment_bytes = (artifact_root / manifest.segment_manifest_path).read_bytes()
    except OSError:
        raise DatasetHandoffError("v0.3 Stage 1 supporting evidence is missing") from None
    if closure_bytes != expected_closure_bytes:
        raise DatasetHandoffError("v0.3 Stage 1 closure bytes changed")
    if hashlib.sha256(closure_bytes).hexdigest() != manifest.closure_manifest_sha256:
        raise DatasetHandoffError("v0.3 Stage 1 closure manifest hash mismatch")
    if hashlib.sha256(exclusion_bytes).hexdigest() != manifest.exclusion_manifest_sha256:
        raise DatasetHandoffError("v0.3 Stage 1 exclusion manifest hash mismatch")
    if hashlib.sha256(segment_bytes).hexdigest() != manifest.segment_manifest_sha256:
        raise DatasetHandoffError("v0.3 Stage 1 segment manifest hash mismatch")
    try:
        closure_manifest = load_exchange_closure_manifest(closure_bytes)
        exclusion_manifest = load_candle_exclusion_manifest(exclusion_bytes)
        segment_manifest = load_candle_segment_manifest(segment_bytes)
    except Exception:
        raise DatasetHandoffError("unable to verify v0.3 Stage 1 supporting evidence") from None
    if closure_manifest != expected_closure:
        raise DatasetHandoffError("v0.3 Stage 1 closure declarations changed")
    if tuple(item.closure_id for item in closure_manifest.closures) != manifest.closure_ids:
        raise DatasetHandoffError("v0.3 Stage 1 closure ID mismatch")
    excluded_rows = tuple(
        ExcludedProviderRow(item.closure_id, item.provider_row_sha256)
        for item in exclusion_manifest.exclusions
    )
    if excluded_rows != manifest.excluded_provider_rows:
        raise DatasetHandoffError("v0.3 Stage 1 excluded row identity mismatch")
    if segment_manifest.boundary_indices != manifest.segment_boundary_indices:
        raise DatasetHandoffError("v0.3 Stage 1 segment boundary mismatch")
    if len(segment_manifest.segments) != manifest.segment_count:
        raise DatasetHandoffError("v0.3 Stage 1 segment count mismatch")
    try:
        rebuilt = build_artifact_inventory(
            artifact_root,
            tuple(item.path for item in manifest.files),
        )
    except HistoricalValidationError as error:
        raise DatasetHandoffError(str(error)) from None
    if rebuilt != manifest.files:
        raise DatasetHandoffError("v0.3 Stage 1 artifact inventory mismatch")
    if inventory_root_sha256(rebuilt) != manifest.inventory_root_sha256:
        raise DatasetHandoffError("v0.3 Stage 1 inventory root mismatch")


__all__ = [
    "V03DatasetHandoffManifest",
    "V03_EXPECTED_CANDLE_COUNT",
    "V03_EXPECTED_FIRST_OPEN_TIME",
    "V03_EXPECTED_LAST_OPEN_TIME",
    "V03_STAGE1_END_EXCLUSIVE",
    "V03_STAGE1_START",
    "assert_v0_3_dataset_identity",
    "build_v0_3_closure_manifest",
    "create_v0_3_dataset_handoff",
    "load_v0_3_dataset_handoff",
    "serialize_v0_3_dataset_handoff",
    "verify_v0_3_dataset_handoff",
]
