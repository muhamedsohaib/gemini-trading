"""Provider-free deterministic replay for Economic Data Fabric v2."""

import json
from datetime import UTC, date, datetime
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from typing import cast

from gemini_trading.economics.data.availability import (
    AvailabilityPrecision,
    AvailabilityStatus,
    EconomicAvailabilityEvidence,
)
from gemini_trading.economics.data.dataset import _jsonl, _load_inventory, _load_registry
from gemini_trading.economics.data.dataset_v2 import (
    EconomicDatasetV2,
    EconomicDatasetV2Error,
    _manifest_payload_v2,
    build_economic_dataset_v2,
)
from gemini_trading.economics.data.observation_v2 import EconomicObservationV2
from gemini_trading.economics.data.publication import (
    EconomicPublicationEvent,
    PublicationSequence,
    RevisionClass,
)
from gemini_trading.research.serialization import canonical_json_bytes


def _parse_utc(value: object, field_name: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise EconomicDatasetV2Error(f"{field_name} must be canonical UTC text")
    try:
        return datetime.fromisoformat(f"{value[:-1]}+00:00").astimezone(UTC)
    except ValueError:
        raise EconomicDatasetV2Error(f"{field_name} is not a valid timestamp") from None


def _optional_utc(value: object, field_name: str) -> datetime | None:
    return None if value is None else _parse_utc(value, field_name)


def _parse_date(value: object, field_name: str) -> date:
    if not isinstance(value, str):
        raise EconomicDatasetV2Error(f"{field_name} must be ISO calendar date text")
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise EconomicDatasetV2Error(f"{field_name} is not a valid calendar date") from None


def _optional_date(value: object, field_name: str) -> date | None:
    return None if value is None else _parse_date(value, field_name)


def _optional_str(value: object) -> str | None:
    return None if value is None else str(value)


def _load_evidence(path: Path) -> tuple[EconomicAvailabilityEvidence, ...]:
    rows: list[EconomicAvailabilityEvidence] = []
    for row in _jsonl(path):
        try:
            rows.append(
                EconomicAvailabilityEvidence(
                    schema_version=str(row["schema_version"]),
                    evidence_id=str(row["evidence_id"]),
                    publication_event_id=str(row["publication_event_id"]),
                    source_id=str(row["source_id"]),
                    consumer_class=str(row["consumer_class"]),
                    availability_channel=str(row["availability_channel"]),
                    availability_precision=AvailabilityPrecision(
                        str(row["availability_precision"])
                    ),
                    available_time=_optional_utc(row["available_time"], "available_time"),
                    available_date=_optional_date(row["available_date"], "available_date"),
                    interval_start=_optional_utc(row["interval_start"], "interval_start"),
                    interval_end=_optional_utc(row["interval_end"], "interval_end"),
                    source_timezone=_optional_str(row["source_timezone"]),
                    source_utc_offset_minutes=(
                        None
                        if row["source_utc_offset_minutes"] is None
                        else int(cast(int | str, row["source_utc_offset_minutes"]))
                    ),
                    retrieved_time=_parse_utc(row["retrieved_time"], "retrieved_time"),
                    raw_sha256=str(row["raw_sha256"]),
                )
            )
        except (KeyError, ValueError, ArithmeticError):
            raise EconomicDatasetV2Error("economic availability evidence row is invalid") from None
    return tuple(rows)


def _load_events(path: Path) -> tuple[EconomicPublicationEvent, ...]:
    events: list[EconomicPublicationEvent] = []
    for row in _jsonl(path):
        try:
            evidence_ids = row["availability_evidence_ids"]
            if not isinstance(evidence_ids, list):
                raise ValueError("availability_evidence_ids must be a list")
            events.append(
                EconomicPublicationEvent(
                    schema_version=str(row["schema_version"]),
                    event_id=str(row["event_id"]),
                    publisher=str(row["publisher"]),
                    source_id=str(row["source_id"]),
                    event_type=str(row["event_type"]),
                    scheduled_time=_optional_utc(row["scheduled_time"], "scheduled_time"),
                    published_time=_optional_utc(row["published_time"], "published_time"),
                    available_time=_optional_utc(row["available_time"], "available_time"),
                    available_date=_optional_date(row["available_date"], "available_date"),
                    consumer_class=str(row["consumer_class"]),
                    availability_channel=str(row["availability_channel"]),
                    availability_precision=AvailabilityPrecision(
                        str(row["availability_precision"])
                    ),
                    availability_evidence_ids=tuple(str(value) for value in evidence_ids),
                    availability_evidence_id=_optional_str(row["availability_evidence_id"]),
                    availability_status=AvailabilityStatus(str(row["availability_status"])),
                    publication_sequence=PublicationSequence(str(row["publication_sequence"])),
                    revision_class=RevisionClass(str(row["revision_class"])),
                    provider_native_publication_sequence=_optional_str(
                        row["provider_native_publication_sequence"]
                    ),
                    provider_native_event_id=_optional_str(row["provider_native_event_id"]),
                    provider_native_source_id=_optional_str(row["provider_native_source_id"]),
                    source_version=_optional_str(row["source_version"]),
                    predecessor_event_id=_optional_str(row["predecessor_event_id"]),
                    retrieved_time=_parse_utc(row["retrieved_time"], "retrieved_time"),
                    raw_sha256=str(row["raw_sha256"]),
                )
            )
        except (KeyError, ValueError, ArithmeticError):
            raise EconomicDatasetV2Error("economic publication event row is invalid") from None
    return tuple(events)


def _load_observations(path: Path) -> tuple[EconomicObservationV2, ...]:
    observations: list[EconomicObservationV2] = []
    for row in _jsonl(path):
        try:
            observations.append(
                EconomicObservationV2(
                    schema_version=str(row["schema_version"]),
                    version_id=str(row["version_id"]),
                    series_id=str(row["series_id"]),
                    observation_time=_parse_utc(row["observation_time"], "observation_time"),
                    reference_period_start=_parse_date(
                        row["reference_period_start"], "reference_period_start"
                    ),
                    reference_period_end=_parse_date(
                        row["reference_period_end"], "reference_period_end"
                    ),
                    available_time=_optional_utc(row["available_time"], "available_time"),
                    available_date=_optional_date(row["available_date"], "available_date"),
                    vintage_time=_optional_utc(row["vintage_time"], "vintage_time"),
                    vintage_date=_optional_date(row["vintage_date"], "vintage_date"),
                    retrieved_time=_parse_utc(row["retrieved_time"], "retrieved_time"),
                    source_id=str(row["source_id"]),
                    value=Decimal(str(row["value"])),
                    unit=str(row["unit"]),
                    scale=Decimal(str(row["scale"])),
                    frequency=str(row["frequency"]),
                    publication_event_id=str(row["publication_event_id"]),
                    availability_evidence_id=_optional_str(row["availability_evidence_id"]),
                    availability_channel=str(row["availability_channel"]),
                    availability_precision=AvailabilityPrecision(
                        str(row["availability_precision"])
                    ),
                    provider_native_source_id=_optional_str(row["provider_native_source_id"]),
                    source_version=_optional_str(row["source_version"]),
                    publication_sequence=PublicationSequence(str(row["publication_sequence"])),
                    revision_class=RevisionClass(str(row["revision_class"])),
                    predecessor_version_id=_optional_str(row["predecessor_version_id"]),
                    raw_sha256=str(row["raw_sha256"]),
                )
            )
        except (KeyError, ValueError, ArithmeticError):
            raise EconomicDatasetV2Error("economic observation v2 row is invalid") from None
    return tuple(observations)


def _validate_raw(root: Path, inventory) -> None:  # type: ignore[no-untyped-def]
    for receipt in inventory.receipts:
        path = root / receipt.relative_path
        if not path.is_file():
            raise EconomicDatasetV2Error(f"raw evidence is missing: {receipt.relative_path}")
        payload = path.read_bytes()
        if len(payload) != receipt.byte_length or sha256(payload).hexdigest() != receipt.sha256:
            raise EconomicDatasetV2Error(f"raw evidence digest mismatch: {receipt.relative_path}")


def replay_economic_bundle_v2(root: Path) -> EconomicDatasetV2:
    """Reconstruct one v2 dataset using only its sealed bundle bytes."""

    registry_path = root / "registry" / "series.jsonl"
    observations_path = root / "canonical" / "observations-v2.jsonl"
    events_path = root / "events" / "publication-events.jsonl"
    evidence_path = root / "availability" / "evidence.jsonl"
    inventory_path = root / "inventory" / "raw-evidence.jsonl"
    manifest_path = root / "manifest.json"

    registry = _load_registry(registry_path)
    observations = _load_observations(observations_path)
    events = _load_events(events_path)
    evidence = _load_evidence(evidence_path)
    inventory = _load_inventory(inventory_path)
    _validate_raw(root, inventory)
    dataset = build_economic_dataset_v2(
        registry=registry,
        observations=observations,
        publication_events=events,
        availability_evidence=evidence,
        raw_inventory=inventory,
    )
    if registry_path.read_bytes() != dataset.series_registry_bytes:
        raise EconomicDatasetV2Error("series registry bytes are not canonical")
    if observations_path.read_bytes() != dataset.canonical_observation_bytes:
        raise EconomicDatasetV2Error("observation v2 bytes are not canonical")
    if events_path.read_bytes() != dataset.publication_event_bytes:
        raise EconomicDatasetV2Error("publication event bytes are not canonical")
    if evidence_path.read_bytes() != dataset.availability_evidence_bytes:
        raise EconomicDatasetV2Error("availability evidence bytes are not canonical")
    if inventory_path.read_bytes() != dataset.raw_inventory.canonical_bytes:
        raise EconomicDatasetV2Error("raw inventory bytes are not canonical")

    if not manifest_path.is_file():
        raise EconomicDatasetV2Error("economic v2 bundle manifest is missing")
    try:
        loaded = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise EconomicDatasetV2Error("economic v2 bundle manifest is invalid JSON") from None
    expected = json.loads(canonical_json_bytes(_manifest_payload_v2(dataset.manifest)))
    if loaded != expected:
        raise EconomicDatasetV2Error("economic v2 bundle manifest does not match dataset identity")
    return dataset


__all__ = ["replay_economic_bundle_v2"]
