"""Content-addressed immutable datasets for Economic Data Fabric v1."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from typing import Final, cast

from gemini_trading.economics.data.observation import EconomicObservation
from gemini_trading.economics.data.serialization import (
    observation_identity_key,
    serialize_observations,
    serialize_series_registry,
)
from gemini_trading.economics.data.series import (
    EconomicDomain,
    EconomicSeriesDefinition,
    EconomicSeriesRegistry,
    RevisionPolicy,
)
from gemini_trading.economics.data.storage import (
    ECONOMIC_RAW_RECEIPT_SCHEMA_V1,
    RawEvidenceInventory,
    RawEvidenceReceipt,
)
from gemini_trading.research.serialization import canonical_json_bytes

ECONOMIC_DATASET_SCHEMA_V1: Final[str] = "economic-dataset-v1"


class EconomicDatasetError(ValueError):
    """Raised when economic dataset identity or bundle evidence is invalid."""


@dataclass(frozen=True, slots=True)
class EconomicDatasetManifest:
    """Immutable content identity and bounds for one economic dataset."""

    schema_version: str
    dataset_id: str
    canonical_observations_sha256: str
    series_registry_sha256: str
    raw_inventory_root_sha256: str
    observation_count: int
    series_count: int
    minimum_observation_time: datetime
    maximum_observation_time: datetime
    minimum_available_time: datetime
    maximum_available_time: datetime


@dataclass(frozen=True, slots=True)
class EconomicDataset:
    """Canonical in-memory representation of one closed economic dataset."""

    manifest: EconomicDatasetManifest
    registry: EconomicSeriesRegistry
    observations: tuple[EconomicObservation, ...]
    raw_inventory: RawEvidenceInventory
    series_registry_bytes: bytes
    canonical_observation_bytes: bytes


def _utc(value: datetime) -> datetime:
    return value.astimezone(UTC)


def _identity_payload(
    *,
    canonical_observations_sha256: str,
    series_registry_sha256: str,
    raw_inventory_root_sha256: str,
    observation_count: int,
    series_count: int,
    minimum_observation_time: datetime,
    maximum_observation_time: datetime,
    minimum_available_time: datetime,
    maximum_available_time: datetime,
) -> dict[str, object]:
    return {
        "schema_version": ECONOMIC_DATASET_SCHEMA_V1,
        "canonical_observations_sha256": canonical_observations_sha256,
        "series_registry_sha256": series_registry_sha256,
        "raw_inventory_root_sha256": raw_inventory_root_sha256,
        "observation_count": observation_count,
        "series_count": series_count,
        "minimum_observation_time": minimum_observation_time,
        "maximum_observation_time": maximum_observation_time,
        "minimum_available_time": minimum_available_time,
        "maximum_available_time": maximum_available_time,
    }


def _manifest_payload(manifest: EconomicDatasetManifest) -> dict[str, object]:
    return {
        "schema_version": manifest.schema_version,
        "dataset_id": manifest.dataset_id,
        "canonical_observations_sha256": manifest.canonical_observations_sha256,
        "series_registry_sha256": manifest.series_registry_sha256,
        "raw_inventory_root_sha256": manifest.raw_inventory_root_sha256,
        "observation_count": manifest.observation_count,
        "series_count": manifest.series_count,
        "minimum_observation_time": manifest.minimum_observation_time,
        "maximum_observation_time": manifest.maximum_observation_time,
        "minimum_available_time": manifest.minimum_available_time,
        "maximum_available_time": manifest.maximum_available_time,
    }


def _validate_semantics(
    registry: EconomicSeriesRegistry,
    observations: tuple[EconomicObservation, ...],
    raw_inventory: RawEvidenceInventory,
) -> None:
    if not observations:
        raise EconomicDatasetError("economic dataset requires at least one observation")

    registry_ids = {definition.series_id for definition in registry.definitions}
    raw_digests = raw_inventory.raw_digests

    for row in observations:
        if row.series_id not in registry_ids:
            raise EconomicDatasetError(
                f"observation series is missing from series registry: {row.series_id}"
            )
        definition = registry.by_id(row.series_id)
        if (
            row.unit != definition.unit
            or row.scale != definition.scale
            or row.frequency != definition.frequency
        ):
            raise EconomicDatasetError(
                f"observation semantics do not match series registry: {row.series_id}"
            )
        if row.raw_sha256 not in raw_digests:
            raise EconomicDatasetError(
                f"observation is not closed by raw evidence: {row.series_id}"
            )


def build_economic_dataset(
    *,
    registry: EconomicSeriesRegistry,
    observations: tuple[EconomicObservation, ...],
    raw_inventory: RawEvidenceInventory,
) -> EconomicDataset:
    """Build one deterministic dataset and its content identity."""

    _validate_semantics(registry, observations, raw_inventory)

    ordered = tuple(
        sorted(
            observations,
            key=lambda row: (*observation_identity_key(row), row.raw_sha256),
        )
    )
    canonical_observation_bytes = serialize_observations(ordered)
    series_registry_bytes = serialize_series_registry(registry)

    canonical_observations_sha256 = sha256(canonical_observation_bytes).hexdigest()
    series_registry_sha256 = sha256(series_registry_bytes).hexdigest()
    raw_inventory_root_sha256 = raw_inventory.inventory_root_sha256

    minimum_observation_time = min(_utc(row.observation_time) for row in ordered)
    maximum_observation_time = max(_utc(row.observation_time) for row in ordered)
    minimum_available_time = min(_utc(row.available_time) for row in ordered)
    maximum_available_time = max(_utc(row.available_time) for row in ordered)
    series_count = len({row.series_id for row in ordered})

    identity_payload = _identity_payload(
        canonical_observations_sha256=canonical_observations_sha256,
        series_registry_sha256=series_registry_sha256,
        raw_inventory_root_sha256=raw_inventory_root_sha256,
        observation_count=len(ordered),
        series_count=series_count,
        minimum_observation_time=minimum_observation_time,
        maximum_observation_time=maximum_observation_time,
        minimum_available_time=minimum_available_time,
        maximum_available_time=maximum_available_time,
    )
    dataset_id = sha256(canonical_json_bytes(identity_payload)).hexdigest()
    manifest = EconomicDatasetManifest(
        schema_version=ECONOMIC_DATASET_SCHEMA_V1,
        dataset_id=dataset_id,
        canonical_observations_sha256=canonical_observations_sha256,
        series_registry_sha256=series_registry_sha256,
        raw_inventory_root_sha256=raw_inventory_root_sha256,
        observation_count=len(ordered),
        series_count=series_count,
        minimum_observation_time=minimum_observation_time,
        maximum_observation_time=maximum_observation_time,
        minimum_available_time=minimum_available_time,
        maximum_available_time=maximum_available_time,
    )
    return EconomicDataset(
        manifest=manifest,
        registry=registry,
        observations=ordered,
        raw_inventory=raw_inventory,
        series_registry_bytes=series_registry_bytes,
        canonical_observation_bytes=canonical_observation_bytes,
    )


def _write_immutable(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != payload:
            raise EconomicDatasetError(f"conflicting existing bytes: {path}")
        return
    try:
        with path.open("xb") as handle:
            handle.write(payload)
    except FileExistsError:
        if path.read_bytes() != payload:
            raise EconomicDatasetError(f"conflicting existing bytes: {path}") from None


def write_economic_bundle(
    root: Path,
    dataset: EconomicDataset,
    *,
    raw_source_root: Path,
) -> EconomicDatasetManifest:
    """Write one immutable provider-free bundle without mutable aliases."""

    planned: list[tuple[Path, bytes]] = []
    for receipt in dataset.raw_inventory.receipts:
        source = raw_source_root / receipt.relative_path
        if not source.is_file():
            raise EconomicDatasetError(f"raw evidence source is missing: {receipt.relative_path}")
        payload = source.read_bytes()
        if len(payload) != receipt.byte_length or sha256(payload).hexdigest() != receipt.sha256:
            raise EconomicDatasetError(
                f"raw evidence source digest mismatch: {receipt.relative_path}"
            )
        planned.append((root / receipt.relative_path, payload))

    planned.extend(
        (
            (root / "registry" / "series.jsonl", dataset.series_registry_bytes),
            (root / "canonical" / "observations.jsonl", dataset.canonical_observation_bytes),
            (root / "inventory" / "raw-evidence.jsonl", dataset.raw_inventory.canonical_bytes),
            (root / "manifest.json", canonical_json_bytes(_manifest_payload(dataset.manifest))),
        )
    )

    for target, payload in planned:
        if target.exists() and target.read_bytes() != payload:
            raise EconomicDatasetError(f"conflicting existing bytes: {target}")
    for target, payload in planned:
        _write_immutable(target, payload)
    return dataset.manifest


def _parse_utc(value: object, field_name: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise EconomicDatasetError(f"{field_name} must be canonical UTC text")
    try:
        parsed = datetime.fromisoformat(f"{value[:-1]}+00:00")
    except ValueError:
        raise EconomicDatasetError(f"{field_name} is not a valid timestamp") from None
    return parsed.astimezone(UTC)


def _jsonl(path: Path) -> tuple[dict[str, object], ...]:
    if not path.is_file():
        raise EconomicDatasetError(f"economic bundle file is missing: {path.name}")
    rows: list[dict[str, object]] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            loaded = json.loads(line)
            if not isinstance(loaded, dict):
                raise EconomicDatasetError("economic JSONL row must be an object")
            rows.append(cast(dict[str, object], loaded))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise EconomicDatasetError(f"economic bundle JSON is invalid: {path.name}") from None
    if not rows:
        raise EconomicDatasetError(f"economic bundle file is empty: {path.name}")
    return tuple(rows)


def _load_registry(path: Path) -> EconomicSeriesRegistry:
    definitions: list[EconomicSeriesDefinition] = []
    for row in _jsonl(path):
        try:
            definitions.append(
                EconomicSeriesDefinition(
                    schema_version=str(row["schema_version"]),
                    series_id=str(row["series_id"]),
                    title=str(row["title"]),
                    domain=EconomicDomain(str(row["domain"])),
                    unit=str(row["unit"]),
                    scale=Decimal(str(row["scale"])),
                    frequency=str(row["frequency"]),
                    observation_semantics=str(row["observation_semantics"]),
                    availability_semantics=str(row["availability_semantics"]),
                    revision_policy=RevisionPolicy(str(row["revision_policy"])),
                )
            )
        except (KeyError, ValueError, ArithmeticError):
            raise EconomicDatasetError("economic series registry row is invalid") from None
    return EconomicSeriesRegistry(tuple(definitions))


def _load_observations(path: Path) -> tuple[EconomicObservation, ...]:
    observations: list[EconomicObservation] = []
    for row in _jsonl(path):
        try:
            raw_vintage = row["vintage_time"]
            raw_release = row["release_id"]
            observations.append(
                EconomicObservation(
                    schema_version=str(row["schema_version"]),
                    series_id=str(row["series_id"]),
                    observation_time=_parse_utc(row["observation_time"], "observation_time"),
                    available_time=_parse_utc(row["available_time"], "available_time"),
                    vintage_time=(
                        None if raw_vintage is None else _parse_utc(raw_vintage, "vintage_time")
                    ),
                    retrieved_time=_parse_utc(row["retrieved_time"], "retrieved_time"),
                    source_id=str(row["source_id"]),
                    value=Decimal(str(row["value"])),
                    unit=str(row["unit"]),
                    scale=Decimal(str(row["scale"])),
                    frequency=str(row["frequency"]),
                    release_id=None if raw_release is None else str(raw_release),
                    raw_sha256=str(row["raw_sha256"]),
                )
            )
        except (KeyError, ValueError, ArithmeticError):
            raise EconomicDatasetError("economic observation row is invalid") from None
    return tuple(observations)


def _load_inventory(path: Path) -> RawEvidenceInventory:
    receipts: list[RawEvidenceReceipt] = []
    for row in _jsonl(path):
        try:
            receipts.append(
                RawEvidenceReceipt(
                    schema_version=str(row["schema_version"]),
                    source_id=str(row["source_id"]),
                    receipt_id=str(row["receipt_id"]),
                    relative_path=str(row["relative_path"]),
                    byte_length=int(cast(int | str, row["byte_length"])),
                    sha256=str(row["sha256"]),
                )
            )
        except (KeyError, ValueError, ArithmeticError):
            raise EconomicDatasetError("economic raw inventory row is invalid") from None
    return RawEvidenceInventory(tuple(receipts))


def _validate_raw_bundle(root: Path, inventory: RawEvidenceInventory) -> None:
    for receipt in inventory.receipts:
        path = root / receipt.relative_path
        if not path.is_file():
            raise EconomicDatasetError(f"raw evidence is missing: {receipt.relative_path}")
        payload = path.read_bytes()
        if len(payload) != receipt.byte_length or sha256(payload).hexdigest() != receipt.sha256:
            raise EconomicDatasetError(f"raw evidence digest mismatch: {receipt.relative_path}")


def load_economic_bundle(root: Path) -> EconomicDataset:
    """Load and recompute one immutable economic bundle without provider access."""

    registry_path = root / "registry" / "series.jsonl"
    observations_path = root / "canonical" / "observations.jsonl"
    inventory_path = root / "inventory" / "raw-evidence.jsonl"
    manifest_path = root / "manifest.json"

    registry = _load_registry(registry_path)
    observations = _load_observations(observations_path)
    inventory = _load_inventory(inventory_path)
    _validate_raw_bundle(root, inventory)

    dataset = build_economic_dataset(
        registry=registry,
        observations=observations,
        raw_inventory=inventory,
    )

    if registry_path.read_bytes() != dataset.series_registry_bytes:
        raise EconomicDatasetError("series registry bytes are not canonical")
    if observations_path.read_bytes() != dataset.canonical_observation_bytes:
        raise EconomicDatasetError("observation bytes are not canonical")
    if inventory_path.read_bytes() != dataset.raw_inventory.canonical_bytes:
        raise EconomicDatasetError("raw inventory bytes are not canonical")

    if not manifest_path.is_file():
        raise EconomicDatasetError("economic bundle manifest is missing")
    try:
        manifest_loaded = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise EconomicDatasetError("economic bundle manifest is invalid JSON") from None
    if not isinstance(manifest_loaded, dict):
        raise EconomicDatasetError("economic bundle manifest must be an object")
    expected = json.loads(canonical_json_bytes(_manifest_payload(dataset.manifest)))
    if manifest_loaded != expected:
        raise EconomicDatasetError("economic bundle manifest does not match dataset identity")

    return dataset


__all__ = [
    "ECONOMIC_DATASET_SCHEMA_V1",
    "EconomicDataset",
    "EconomicDatasetError",
    "EconomicDatasetManifest",
    "build_economic_dataset",
    "load_economic_bundle",
    "write_economic_bundle",
]
