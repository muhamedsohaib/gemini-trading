"""Canonical evidence contracts for sealed historical-validation handoffs."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import cast

from gemini_trading.research.serialization import canonical_json_bytes
from gemini_trading.strategy.errors import DatasetHandoffError, HistoricalValidationError

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_GIT_COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")
_IDENTITY_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_SCHEMA_VERSION = "sealed-dataset-handoff-v1"
_REPOSITORY = "muhamedsohaib/gemini-trading"
_WORKFLOW_NAME = "sealed-btcusdt-dataset"
_JOB_NAME = "dataset"
_PROVIDER = "binance_spot"
_SYMBOL = "BTCUSDT"
_BASE_ASSET = "BTC"
_QUOTE_ASSET = "USDT"
_INTERVAL = "4h"
_START = "2018-01-01T00:00:00Z"
_END_EXCLUSIVE = "2026-07-01T00:00:00Z"
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
    "candle_count",
    "first_open_time",
    "last_open_time",
    "replay_status",
    "verification_status",
    "files",
    "inventory_root_sha256",
}
_FILE_FIELDS = {"path", "size_bytes", "sha256"}


def _require_sha256(value: str, field_name: str) -> str:
    if _SHA256_PATTERN.fullmatch(value) is None:
        raise DatasetHandoffError(f"invalid {field_name}")
    return value


def _require_positive_int(value: int, field_name: str) -> int:
    if isinstance(value, bool) or value < 1:
        raise DatasetHandoffError(f"invalid {field_name}")
    return value


def _require_identity(value: str, field_name: str) -> str:
    if _IDENTITY_PATTERN.fullmatch(value) is None or ".." in value:
        raise DatasetHandoffError(f"invalid {field_name}")
    return value


@dataclass(frozen=True, slots=True)
class ArtifactInventoryEntry:
    """One content-addressed file inside a workflow artifact."""

    path: str
    size_bytes: int
    sha256: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "path", validate_artifact_relative_path(self.path))
        if isinstance(self.size_bytes, bool) or self.size_bytes < 0:
            raise HistoricalValidationError("invalid artifact size")
        if _SHA256_PATTERN.fullmatch(self.sha256) is None:
            raise HistoricalValidationError("invalid artifact SHA-256")


def validate_artifact_relative_path(value: str) -> str:
    """Validate and normalize one portable artifact-relative POSIX path."""

    path = PurePosixPath(value)
    if (
        not value
        or value != path.as_posix()
        or "\\" in value
        or path.is_absolute()
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise HistoricalValidationError("invalid artifact-relative path")
    return path.as_posix()


def build_artifact_inventory(
    root: Path,
    relative_paths: tuple[str, ...],
) -> tuple[ArtifactInventoryEntry, ...]:
    """Build a deterministic inventory from exact artifact-relative paths."""

    normalized = tuple(validate_artifact_relative_path(item) for item in relative_paths)
    if len(set(normalized)) != len(normalized):
        raise HistoricalValidationError("duplicate artifact-relative path")
    root_resolved = Path(root).resolve(strict=False)
    entries: list[ArtifactInventoryEntry] = []
    for relative in sorted(normalized):
        candidate = (root_resolved / relative).resolve(strict=False)
        try:
            candidate.relative_to(root_resolved)
        except ValueError:
            raise HistoricalValidationError(
                "artifact-relative path escaped artifact root"
            ) from None
        try:
            content = candidate.read_bytes()
        except OSError:
            raise HistoricalValidationError(f"unable to read artifact file: {relative}") from None
        entries.append(
            ArtifactInventoryEntry(
                path=relative,
                size_bytes=len(content),
                sha256=hashlib.sha256(content).hexdigest(),
            )
        )
    return tuple(entries)


def _inventory_payload(entries: tuple[ArtifactInventoryEntry, ...]) -> dict[str, object]:
    return {
        "schema_version": "artifact-inventory-v1",
        "files": [
            {
                "path": item.path,
                "size_bytes": item.size_bytes,
                "sha256": item.sha256,
            }
            for item in entries
        ],
    }


def inventory_root_sha256(entries: tuple[ArtifactInventoryEntry, ...]) -> str:
    """Return the deterministic root identity of an ordered file inventory."""

    if tuple(item.path for item in entries) != tuple(sorted(item.path for item in entries)):
        raise HistoricalValidationError("artifact inventory is not sorted")
    if len({item.path for item in entries}) != len(entries):
        raise HistoricalValidationError("duplicate artifact-relative path")
    return hashlib.sha256(canonical_json_bytes(_inventory_payload(entries))).hexdigest()


@dataclass(frozen=True, slots=True)
class DatasetHandoffManifest:
    """Strict identity and inventory contract passed from Stage 1 to Stage 2."""

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
    candle_count: int
    first_open_time: str
    last_open_time: str
    replay_status: str
    verification_status: str
    files: tuple[ArtifactInventoryEntry, ...]
    inventory_root_sha256: str

    def __post_init__(self) -> None:
        if self.schema_version != _SCHEMA_VERSION:
            raise DatasetHandoffError("unsupported dataset handoff schema")
        if self.repository != _REPOSITORY:
            raise DatasetHandoffError("dataset handoff repository mismatch")
        if _GIT_COMMIT_PATTERN.fullmatch(self.source_commit) is None:
            raise DatasetHandoffError("invalid source commit")
        if self.workflow_name != _WORKFLOW_NAME or self.job_name != _JOB_NAME:
            raise DatasetHandoffError("dataset handoff workflow identity mismatch")
        _require_positive_int(self.workflow_run_id, "workflow run ID")
        _require_positive_int(self.workflow_run_attempt, "workflow run attempt")
        if self.provider != _PROVIDER:
            raise DatasetHandoffError("dataset handoff provider mismatch")
        if (self.symbol, self.base_asset, self.quote_asset, self.interval) != (
            _SYMBOL,
            _BASE_ASSET,
            _QUOTE_ASSET,
            _INTERVAL,
        ):
            raise DatasetHandoffError("dataset handoff market scope mismatch")
        if (self.start, self.end_exclusive) != (_START, _END_EXCLUSIVE):
            raise DatasetHandoffError("dataset handoff historical window mismatch")
        _require_identity(self.run_id, "retrieval run ID")
        _require_sha256(self.dataset_id, "dataset ID")
        _require_positive_int(self.candle_count, "candle count")
        if self.first_open_time != _START or self.last_open_time != "2026-06-30T20:00:00Z":
            raise DatasetHandoffError("dataset handoff candle boundary mismatch")
        if self.replay_status != "completed" or self.verification_status != "verified":
            raise DatasetHandoffError("dataset handoff is not verified")
        if not self.files:
            raise DatasetHandoffError("dataset handoff file inventory is empty")
        if tuple(item.path for item in self.files) != tuple(
            sorted(item.path for item in self.files)
        ):
            raise DatasetHandoffError("dataset handoff file inventory is not sorted")
        if len({item.path for item in self.files}) != len(self.files):
            raise DatasetHandoffError("duplicate artifact-relative path")
        _require_sha256(self.inventory_root_sha256, "inventory root")
        if inventory_root_sha256(self.files) != self.inventory_root_sha256:
            raise DatasetHandoffError("dataset inventory root mismatch")


def _handoff_payload(manifest: DatasetHandoffManifest) -> dict[str, object]:
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


def serialize_dataset_handoff(manifest: DatasetHandoffManifest) -> bytes:
    """Serialize a handoff using canonical JSON bytes."""

    return canonical_json_bytes(_handoff_payload(manifest))


def _mapping(value: object, description: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise DatasetHandoffError(f"invalid {description}")
    raw = cast(dict[object, object], value)
    if not all(isinstance(key, str) for key in raw):
        raise DatasetHandoffError(f"invalid {description}")
    return cast(dict[str, object], raw)


def _exact_fields(mapping: dict[str, object], expected: set[str], description: str) -> None:
    if set(mapping) != expected:
        raise DatasetHandoffError(f"invalid {description} fields")


def _str(mapping: dict[str, object], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str):
        raise DatasetHandoffError(f"invalid dataset handoff field: {key}")
    return value


def _int(mapping: dict[str, object], key: str) -> int:
    value = mapping.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise DatasetHandoffError(f"invalid dataset handoff field: {key}")
    return value


def load_dataset_handoff(raw: bytes) -> DatasetHandoffManifest:
    """Parse exact canonical handoff bytes and reject alternate encodings or fields."""

    try:
        loaded: object = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise DatasetHandoffError("invalid dataset handoff JSON") from None
    mapping = _mapping(loaded, "dataset handoff")
    _exact_fields(mapping, _ALLOWED_FIELDS, "dataset handoff")
    raw_files = mapping.get("files")
    if not isinstance(raw_files, list):
        raise DatasetHandoffError("invalid dataset handoff field: files")
    files: list[ArtifactInventoryEntry] = []
    for raw_file in cast(list[object], raw_files):
        file_mapping = _mapping(raw_file, "dataset handoff file")
        _exact_fields(file_mapping, _FILE_FIELDS, "dataset handoff file")
        files.append(
            ArtifactInventoryEntry(
                path=_str(file_mapping, "path"),
                size_bytes=_int(file_mapping, "size_bytes"),
                sha256=_str(file_mapping, "sha256"),
            )
        )
    manifest = DatasetHandoffManifest(
        schema_version=_str(mapping, "schema_version"),
        repository=_str(mapping, "repository"),
        source_commit=_str(mapping, "source_commit"),
        workflow_name=_str(mapping, "workflow_name"),
        workflow_run_id=_int(mapping, "workflow_run_id"),
        workflow_run_attempt=_int(mapping, "workflow_run_attempt"),
        job_name=_str(mapping, "job_name"),
        provider=_str(mapping, "provider"),
        symbol=_str(mapping, "symbol"),
        base_asset=_str(mapping, "base_asset"),
        quote_asset=_str(mapping, "quote_asset"),
        interval=_str(mapping, "interval"),
        start=_str(mapping, "start"),
        end_exclusive=_str(mapping, "end_exclusive"),
        run_id=_str(mapping, "run_id"),
        dataset_id=_str(mapping, "dataset_id"),
        candle_count=_int(mapping, "candle_count"),
        first_open_time=_str(mapping, "first_open_time"),
        last_open_time=_str(mapping, "last_open_time"),
        replay_status=_str(mapping, "replay_status"),
        verification_status=_str(mapping, "verification_status"),
        files=tuple(files),
        inventory_root_sha256=_str(mapping, "inventory_root_sha256"),
    )
    if serialize_dataset_handoff(manifest) != raw:
        raise DatasetHandoffError("dataset handoff encoding is not canonical")
    return manifest


def verify_dataset_handoff(
    manifest: DatasetHandoffManifest,
    artifact_root: Path,
    *,
    expected_commit: str | None = None,
    expected_dataset_id: str | None = None,
    expected_run_id: int | None = None,
) -> None:
    """Recompute the complete handoff inventory and verify expected identities."""

    if expected_commit is not None and manifest.source_commit != expected_commit:
        raise DatasetHandoffError("source commit mismatch")
    if expected_dataset_id is not None and manifest.dataset_id != expected_dataset_id:
        raise DatasetHandoffError("dataset identity mismatch")
    if expected_run_id is not None and manifest.workflow_run_id != expected_run_id:
        raise DatasetHandoffError("source workflow run mismatch")
    try:
        rebuilt = build_artifact_inventory(
            artifact_root,
            tuple(item.path for item in manifest.files),
        )
    except HistoricalValidationError as error:
        raise DatasetHandoffError(str(error)) from None
    if rebuilt != manifest.files:
        raise DatasetHandoffError("dataset artifact inventory mismatch")
    if inventory_root_sha256(rebuilt) != manifest.inventory_root_sha256:
        raise DatasetHandoffError("dataset inventory root mismatch")


__all__ = [
    "ArtifactInventoryEntry",
    "DatasetHandoffManifest",
    "build_artifact_inventory",
    "inventory_root_sha256",
    "load_dataset_handoff",
    "serialize_dataset_handoff",
    "validate_artifact_relative_path",
    "verify_dataset_handoff",
]
