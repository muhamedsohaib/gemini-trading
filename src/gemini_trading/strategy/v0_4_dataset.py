"""Version-isolated canonical dataset identity and verification for Candidate v0.4."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Never, cast

from gemini_trading.research.serialization import canonical_json_bytes
from gemini_trading.strategy.errors import DatasetHandoffError
from gemini_trading.strategy.handoff import validate_artifact_relative_path
from gemini_trading.strategy.v0_4_stage1 import build_v0_4_closure_manifest
from gemini_trading.strategy.v0_4_stage1_handoff import (
    V04DatasetHandoffManifest,
    V04Stage1ExpectedShape,
    expected_v0_4_stage1_shape,
)

_SCHEMA_VERSION = "candidate-v0.4-candle-dataset-v1"
_PROVIDER = "binance_spot"
_SYMBOL = "BTCUSDT"
_BASE_ASSET = "BTC"
_QUOTE_ASSET = "USDT"
_INTERVAL = "1h"
_START = "2018-01-01T00:00:00Z"
_END_EXCLUSIVE = "2026-08-01T00:00:00Z"
_FIRST_OPEN = "2018-01-01T00:00:00Z"
_LAST_OPEN = "2026-07-31T23:00:00Z"
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_DATASET_FIELDS = {
    "schema_version",
    "dataset_id",
    "provider",
    "symbol",
    "base_asset",
    "quote_asset",
    "interval",
    "start",
    "end_exclusive",
    "candle_count",
    "first_open_time",
    "last_open_time",
    "canonical_candles_path",
    "canonical_candles_sha256",
    "source_closure_manifest_sha256",
    "closure_manifest_path",
    "closure_manifest_sha256",
    "closure_count",
    "exclusion_manifest_path",
    "exclusion_manifest_sha256",
    "exclusion_count",
    "segment_manifest_path",
    "segment_manifest_sha256",
    "segment_count",
}


def _fail(message: str) -> Never:
    raise DatasetHandoffError(message)


def _require_sha256(value: str, field_name: str) -> None:
    if _SHA256_PATTERN.fullmatch(value) is None:
        _fail(f"invalid Candidate v0.4 {field_name}")


def _safe_relative(path: str) -> str:
    return validate_artifact_relative_path(path)


def _canonical_paths(dataset_id: str) -> tuple[str, str, str, str, str]:
    prefix = f"data/canonical/{dataset_id}"
    return (
        f"{prefix}/manifest.json",
        f"{prefix}/candles.jsonl",
        f"{prefix}/exchange-closures.json",
        f"{prefix}/candle-exclusions.json",
        f"{prefix}/candle-segments.json",
    )


def _identity_payload(
    *,
    canonical_candles_sha256: str,
    source_closure_manifest_sha256: str,
    closure_manifest_sha256: str,
    exclusion_manifest_sha256: str,
    segment_manifest_sha256: str,
    shape: V04Stage1ExpectedShape,
) -> dict[str, object]:
    return {
        "schema_version": _SCHEMA_VERSION,
        "provider": _PROVIDER,
        "symbol": _SYMBOL,
        "base_asset": _BASE_ASSET,
        "quote_asset": _QUOTE_ASSET,
        "interval": _INTERVAL,
        "start": _START,
        "end_exclusive": _END_EXCLUSIVE,
        "candle_count": shape.candle_count,
        "first_open_time": shape.first_open_time,
        "last_open_time": shape.last_open_time,
        "canonical_candles_sha256": canonical_candles_sha256,
        "source_closure_manifest_sha256": source_closure_manifest_sha256,
        "closure_manifest_sha256": closure_manifest_sha256,
        "closure_count": shape.closure_count,
        "exclusion_manifest_sha256": exclusion_manifest_sha256,
        "exclusion_count": shape.exclusion_count,
        "segment_manifest_sha256": segment_manifest_sha256,
        "segment_count": shape.segment_count,
    }


def _dataset_id_from_payload(payload: dict[str, object]) -> str:
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


@dataclass(frozen=True, slots=True)
class V04DatasetManifest:
    """Canonical v0.4 dataset identity without weakening the shared v4 manifest."""

    schema_version: str
    dataset_id: str
    provider: str
    symbol: str
    base_asset: str
    quote_asset: str
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

    def __post_init__(self) -> None:
        if self.schema_version != _SCHEMA_VERSION:
            _fail("unsupported Candidate v0.4 dataset schema")
        _require_sha256(self.dataset_id, "dataset ID")
        if (
            self.provider,
            self.symbol,
            self.base_asset,
            self.quote_asset,
            self.interval,
        ) != (_PROVIDER, _SYMBOL, _BASE_ASSET, _QUOTE_ASSET, _INTERVAL):
            _fail("Candidate v0.4 dataset market scope mismatch")
        if (self.start, self.end_exclusive) != (_START, _END_EXCLUSIVE):
            _fail("Candidate v0.4 dataset historical window mismatch")
        if (
            isinstance(self.candle_count, bool)
            or self.candle_count < 1
            or isinstance(self.closure_count, bool)
            or self.closure_count < 1
            or isinstance(self.exclusion_count, bool)
            or self.exclusion_count < 0
            or isinstance(self.segment_count, bool)
            or self.segment_count < 1
        ):
            _fail("Candidate v0.4 dataset evidence counts are invalid")
        if self.exclusion_count > self.closure_count:
            _fail("Candidate v0.4 dataset exclusion count exceeds closure count")
        if self.segment_count != self.closure_count + 1:
            _fail("Candidate v0.4 dataset segment count mismatch")
        if (self.first_open_time, self.last_open_time) != (_FIRST_OPEN, _LAST_OPEN):
            _fail("Candidate v0.4 dataset candle boundaries changed")
        for field_name in (
            "canonical_candles_sha256",
            "source_closure_manifest_sha256",
            "closure_manifest_sha256",
            "exclusion_manifest_sha256",
            "segment_manifest_sha256",
        ):
            _require_sha256(getattr(self, field_name), field_name.replace("_", " "))
        manifest_path, candles_path, closure_path, exclusion_path, segment_path = _canonical_paths(
            self.dataset_id
        )
        del manifest_path
        expected_paths = (candles_path, closure_path, exclusion_path, segment_path)
        actual_paths = (
            self.canonical_candles_path,
            self.closure_manifest_path,
            self.exclusion_manifest_path,
            self.segment_manifest_path,
        )
        if tuple(_safe_relative(path) for path in actual_paths) != expected_paths:
            _fail("Candidate v0.4 dataset artifact layout changed")
        identity = _dataset_id_from_payload(
            {
                "schema_version": self.schema_version,
                "provider": self.provider,
                "symbol": self.symbol,
                "base_asset": self.base_asset,
                "quote_asset": self.quote_asset,
                "interval": self.interval,
                "start": self.start,
                "end_exclusive": self.end_exclusive,
                "candle_count": self.candle_count,
                "first_open_time": self.first_open_time,
                "last_open_time": self.last_open_time,
                "canonical_candles_sha256": self.canonical_candles_sha256,
                "source_closure_manifest_sha256": self.source_closure_manifest_sha256,
                "closure_manifest_sha256": self.closure_manifest_sha256,
                "closure_count": self.closure_count,
                "exclusion_manifest_sha256": self.exclusion_manifest_sha256,
                "exclusion_count": self.exclusion_count,
                "segment_manifest_sha256": self.segment_manifest_sha256,
                "segment_count": self.segment_count,
            }
        )
        if identity != self.dataset_id:
            _fail("Candidate v0.4 dataset identity mismatch")


def build_v0_4_dataset_manifest(
    *,
    canonical_candles_sha256: str,
    source_closure_manifest_sha256: str,
    closure_manifest_sha256: str,
    exclusion_manifest_sha256: str,
    segment_manifest_sha256: str,
    shape: V04Stage1ExpectedShape,
) -> V04DatasetManifest:
    """Build one content-addressed Candidate v0.4 dataset manifest."""

    for field_name, value in (
        ("canonical candles SHA-256", canonical_candles_sha256),
        ("source closure manifest SHA-256", source_closure_manifest_sha256),
        ("closure manifest SHA-256", closure_manifest_sha256),
        ("exclusion manifest SHA-256", exclusion_manifest_sha256),
        ("segment manifest SHA-256", segment_manifest_sha256),
    ):
        _require_sha256(value, field_name)
    payload = _identity_payload(
        canonical_candles_sha256=canonical_candles_sha256,
        source_closure_manifest_sha256=source_closure_manifest_sha256,
        closure_manifest_sha256=closure_manifest_sha256,
        exclusion_manifest_sha256=exclusion_manifest_sha256,
        segment_manifest_sha256=segment_manifest_sha256,
        shape=shape,
    )
    dataset_id = _dataset_id_from_payload(payload)
    _, candles_path, closure_path, exclusion_path, segment_path = _canonical_paths(dataset_id)
    return V04DatasetManifest(
        schema_version=_SCHEMA_VERSION,
        dataset_id=dataset_id,
        provider=_PROVIDER,
        symbol=_SYMBOL,
        base_asset=_BASE_ASSET,
        quote_asset=_QUOTE_ASSET,
        interval=_INTERVAL,
        start=_START,
        end_exclusive=_END_EXCLUSIVE,
        candle_count=shape.candle_count,
        first_open_time=shape.first_open_time,
        last_open_time=shape.last_open_time,
        canonical_candles_path=candles_path,
        canonical_candles_sha256=canonical_candles_sha256,
        source_closure_manifest_sha256=source_closure_manifest_sha256,
        closure_manifest_path=closure_path,
        closure_manifest_sha256=closure_manifest_sha256,
        closure_count=shape.closure_count,
        exclusion_manifest_path=exclusion_path,
        exclusion_manifest_sha256=exclusion_manifest_sha256,
        exclusion_count=shape.exclusion_count,
        segment_manifest_path=segment_path,
        segment_manifest_sha256=segment_manifest_sha256,
        segment_count=shape.segment_count,
    )


def _dataset_payload(manifest: V04DatasetManifest) -> dict[str, object]:
    return {
        "schema_version": manifest.schema_version,
        "dataset_id": manifest.dataset_id,
        "provider": manifest.provider,
        "symbol": manifest.symbol,
        "base_asset": manifest.base_asset,
        "quote_asset": manifest.quote_asset,
        "interval": manifest.interval,
        "start": manifest.start,
        "end_exclusive": manifest.end_exclusive,
        "candle_count": manifest.candle_count,
        "first_open_time": manifest.first_open_time,
        "last_open_time": manifest.last_open_time,
        "canonical_candles_path": manifest.canonical_candles_path,
        "canonical_candles_sha256": manifest.canonical_candles_sha256,
        "source_closure_manifest_sha256": manifest.source_closure_manifest_sha256,
        "closure_manifest_path": manifest.closure_manifest_path,
        "closure_manifest_sha256": manifest.closure_manifest_sha256,
        "closure_count": manifest.closure_count,
        "exclusion_manifest_path": manifest.exclusion_manifest_path,
        "exclusion_manifest_sha256": manifest.exclusion_manifest_sha256,
        "exclusion_count": manifest.exclusion_count,
        "segment_manifest_path": manifest.segment_manifest_path,
        "segment_manifest_sha256": manifest.segment_manifest_sha256,
        "segment_count": manifest.segment_count,
    }


def serialize_v0_4_dataset_manifest(manifest: V04DatasetManifest) -> bytes:
    """Serialize one v0.4 dataset manifest canonically."""

    return canonical_json_bytes(_dataset_payload(manifest))


def _mapping(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        _fail("Candidate v0.4 dataset manifest must be an object")
    raw = cast(dict[object, object], value)
    if not all(isinstance(key, str) for key in raw):
        _fail("Candidate v0.4 dataset manifest fields are invalid")
    return cast(dict[str, object], raw)


def _string(mapping: dict[str, object], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str):
        _fail(f"invalid Candidate v0.4 dataset field: {key}")
    return value


def _integer(mapping: dict[str, object], key: str) -> int:
    value = mapping.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        _fail(f"invalid Candidate v0.4 dataset field: {key}")
    return value


def load_v0_4_dataset_manifest(raw: bytes) -> V04DatasetManifest:
    """Load only canonical Candidate v0.4 dataset-manifest bytes."""

    try:
        loaded: object = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        _fail("Candidate v0.4 dataset manifest is not valid JSON")
    mapping = _mapping(loaded)
    if set(mapping) != _DATASET_FIELDS:
        _fail("Candidate v0.4 dataset manifest fields are invalid")
    manifest = V04DatasetManifest(
        schema_version=_string(mapping, "schema_version"),
        dataset_id=_string(mapping, "dataset_id"),
        provider=_string(mapping, "provider"),
        symbol=_string(mapping, "symbol"),
        base_asset=_string(mapping, "base_asset"),
        quote_asset=_string(mapping, "quote_asset"),
        interval=_string(mapping, "interval"),
        start=_string(mapping, "start"),
        end_exclusive=_string(mapping, "end_exclusive"),
        candle_count=_integer(mapping, "candle_count"),
        first_open_time=_string(mapping, "first_open_time"),
        last_open_time=_string(mapping, "last_open_time"),
        canonical_candles_path=_string(mapping, "canonical_candles_path"),
        canonical_candles_sha256=_string(mapping, "canonical_candles_sha256"),
        source_closure_manifest_sha256=_string(mapping, "source_closure_manifest_sha256"),
        closure_manifest_path=_string(mapping, "closure_manifest_path"),
        closure_manifest_sha256=_string(mapping, "closure_manifest_sha256"),
        closure_count=_integer(mapping, "closure_count"),
        exclusion_manifest_path=_string(mapping, "exclusion_manifest_path"),
        exclusion_manifest_sha256=_string(mapping, "exclusion_manifest_sha256"),
        exclusion_count=_integer(mapping, "exclusion_count"),
        segment_manifest_path=_string(mapping, "segment_manifest_path"),
        segment_manifest_sha256=_string(mapping, "segment_manifest_sha256"),
        segment_count=_integer(mapping, "segment_count"),
    )
    if serialize_v0_4_dataset_manifest(manifest) != raw:
        _fail("Candidate v0.4 dataset manifest encoding is not canonical")
    return manifest


def _artifact_path(root: Path, relative: str) -> Path:
    safe = _safe_relative(relative)
    resolved_root = root.resolve(strict=False)
    path = (resolved_root / safe).resolve(strict=False)
    try:
        path.relative_to(resolved_root)
    except ValueError:
        _fail("Candidate v0.4 artifact path escaped the Stage 1 root")
    return path


def _read_artifact(root: Path, relative: str) -> bytes:
    path = _artifact_path(root, relative)
    try:
        return path.read_bytes()
    except OSError:
        _fail("Candidate v0.4 Stage 1 artifact is missing")


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _verify_inventory(handoff: V04DatasetHandoffManifest, artifact_root: Path) -> None:
    expected_paths = {item.path for item in handoff.files}
    for item in handoff.files:
        raw = _read_artifact(artifact_root, item.path)
        if len(raw) != item.size_bytes or _sha(raw) != item.sha256:
            _fail("Candidate v0.4 Stage 1 inventory mismatch")
    required = {
        f"data/canonical/{handoff.dataset_id}/manifest.json",
        f"data/canonical/{handoff.dataset_id}/candles.jsonl",
        handoff.closure_manifest_path,
        handoff.exclusion_manifest_path,
        handoff.segment_manifest_path,
    }
    if not required <= expected_paths:
        _fail("Candidate v0.4 Stage 1 inventory is incomplete")


def verify_v0_4_dataset_handoff(
    handoff: V04DatasetHandoffManifest,
    artifact_root: Path,
    *,
    project_root: Path,
    expected_commit: str,
    expected_dataset_id: str,
    expected_run_id: int,
) -> None:
    """Verify one v0.4 Stage 1 handoff against frozen source-linked evidence."""

    if handoff.source_commit != expected_commit:
        _fail("Candidate v0.4 Stage 1 source commit mismatch")
    if handoff.dataset_id != expected_dataset_id:
        _fail("Candidate v0.4 Stage 1 dataset ID mismatch")
    if handoff.workflow_run_id != expected_run_id:
        _fail("Candidate v0.4 Stage 1 workflow run mismatch")

    shape = expected_v0_4_stage1_shape(project_root)
    closure_manifest, closure_raw = build_v0_4_closure_manifest(project_root)
    if (
        handoff.closure_count != shape.closure_count
        or handoff.exclusion_count != shape.exclusion_count
        or handoff.segment_count != shape.segment_count
        or handoff.closure_ids != shape.closure_ids
        or handoff.segment_boundary_indices != shape.segment_boundary_indices
        or handoff.candle_count != shape.candle_count
        or handoff.first_open_time != shape.first_open_time
        or handoff.last_open_time != shape.last_open_time
    ):
        _fail("Candidate v0.4 Stage 1 derived evidence shape mismatch")
    excluded_ids = tuple(item.closure_id for item in handoff.excluded_provider_rows)
    if excluded_ids != shape.partial_closure_ids:
        _fail("Candidate v0.4 Stage 1 exclusion does not match a declared partial closure")
    if _sha(closure_raw) != handoff.closure_manifest_sha256:
        _fail("Candidate v0.4 Stage 1 closure manifest identity mismatch")
    if _read_artifact(artifact_root, handoff.closure_manifest_path) != closure_raw:
        _fail("Candidate v0.4 Stage 1 closure manifest bytes changed")

    _verify_inventory(handoff, artifact_root)
    manifest_path, _, _, _, _ = _canonical_paths(handoff.dataset_id)
    dataset = load_v0_4_dataset_manifest(_read_artifact(artifact_root, manifest_path))
    if dataset.dataset_id != handoff.dataset_id:
        _fail("Candidate v0.4 Stage 1 dataset manifest ID mismatch")
    if dataset.source_closure_manifest_sha256 != closure_manifest.source_manifest_sha256:
        _fail("Candidate v0.4 Stage 1 source closure identity mismatch")
    if (
        dataset.closure_manifest_path != handoff.closure_manifest_path
        or dataset.closure_manifest_sha256 != handoff.closure_manifest_sha256
        or dataset.closure_count != handoff.closure_count
        or dataset.exclusion_manifest_path != handoff.exclusion_manifest_path
        or dataset.exclusion_manifest_sha256 != handoff.exclusion_manifest_sha256
        or dataset.exclusion_count != handoff.exclusion_count
        or dataset.segment_manifest_path != handoff.segment_manifest_path
        or dataset.segment_manifest_sha256 != handoff.segment_manifest_sha256
        or dataset.segment_count != handoff.segment_count
        or dataset.candle_count != handoff.candle_count
        or dataset.first_open_time != handoff.first_open_time
        or dataset.last_open_time != handoff.last_open_time
    ):
        _fail("Candidate v0.4 Stage 1 dataset manifest does not match the handoff")
    for relative, expected_sha in (
        (dataset.canonical_candles_path, dataset.canonical_candles_sha256),
        (dataset.closure_manifest_path, dataset.closure_manifest_sha256),
        (dataset.exclusion_manifest_path, dataset.exclusion_manifest_sha256),
        (dataset.segment_manifest_path, dataset.segment_manifest_sha256),
    ):
        if _sha(_read_artifact(artifact_root, relative)) != expected_sha:
            _fail("Candidate v0.4 Stage 1 dataset content identity mismatch")


__all__ = [
    "V04DatasetManifest",
    "build_v0_4_dataset_manifest",
    "load_v0_4_dataset_manifest",
    "serialize_v0_4_dataset_manifest",
    "verify_v0_4_dataset_handoff",
]
