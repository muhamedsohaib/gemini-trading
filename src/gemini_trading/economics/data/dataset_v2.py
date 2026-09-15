"""Content-addressed admission and identity for Economic Data Fabric v2."""

from dataclasses import dataclass
from datetime import UTC, date, datetime
from hashlib import sha256
from typing import Final

from gemini_trading.economics.data.availability import EconomicAvailabilityEvidence
from gemini_trading.economics.data.observation_v2 import (
    EconomicObservationV2,
    economic_observation_version_id,
)
from gemini_trading.economics.data.publication import (
    EconomicPublicationEvent,
    RevisionClass,
)
from gemini_trading.economics.data.serialization import serialize_series_registry
from gemini_trading.economics.data.serialization_v2 import (
    serialize_availability_evidence,
    serialize_observations_v2,
    serialize_publication_events,
)
from gemini_trading.economics.data.series import EconomicSeriesRegistry
from gemini_trading.economics.data.storage import RawEvidenceInventory
from gemini_trading.research.serialization import canonical_json_bytes

ECONOMIC_DATASET_SCHEMA_V2: Final[str] = "economic-dataset-v2"


class EconomicDatasetV2Error(ValueError):
    """Raised when v2 economic dataset admission or identity is invalid."""


@dataclass(frozen=True, slots=True)
class EconomicDatasetManifestV2:
    schema_version: str
    dataset_id: str
    canonical_observations_sha256: str
    publication_events_sha256: str
    availability_evidence_sha256: str
    series_registry_sha256: str
    raw_inventory_root_sha256: str
    observation_count: int
    publication_event_count: int
    availability_evidence_count: int
    series_count: int
    minimum_observation_time: datetime
    maximum_observation_time: datetime
    minimum_reference_period_start: date
    maximum_reference_period_end: date
    minimum_exact_available_time: datetime | None
    maximum_exact_available_time: datetime | None


@dataclass(frozen=True, slots=True)
class EconomicDatasetV2:
    manifest: EconomicDatasetManifestV2
    registry: EconomicSeriesRegistry
    observations: tuple[EconomicObservationV2, ...]
    publication_events: tuple[EconomicPublicationEvent, ...]
    availability_evidence: tuple[EconomicAvailabilityEvidence, ...]
    raw_inventory: RawEvidenceInventory
    series_registry_bytes: bytes
    canonical_observation_bytes: bytes
    publication_event_bytes: bytes
    availability_evidence_bytes: bytes


def _utc(value: datetime) -> datetime:
    return value.astimezone(UTC)


def _validate_unique_ids(
    observations: tuple[EconomicObservationV2, ...],
    events: tuple[EconomicPublicationEvent, ...],
    evidence: tuple[EconomicAvailabilityEvidence, ...],
) -> tuple[
    dict[str, EconomicObservationV2],
    dict[str, EconomicPublicationEvent],
    dict[str, EconomicAvailabilityEvidence],
]:
    observation_map = {row.version_id: row for row in observations}
    event_map = {row.event_id: row for row in events}
    evidence_map = {row.evidence_id: row for row in evidence}
    if len(observation_map) != len(observations):
        raise EconomicDatasetV2Error("duplicate observation version identity")
    if len(event_map) != len(events):
        raise EconomicDatasetV2Error("duplicate publication event identity")
    if len(evidence_map) != len(evidence):
        raise EconomicDatasetV2Error("duplicate availability evidence identity")
    return observation_map, event_map, evidence_map


def _validate_event_graph(events: dict[str, EconomicPublicationEvent]) -> None:
    for event in events.values():
        predecessor = event.predecessor_event_id
        if predecessor is not None and predecessor not in events:
            raise EconomicDatasetV2Error("publication event predecessor is missing")
    for event_id in events:
        seen: set[str] = set()
        cursor: str | None = event_id
        while cursor is not None:
            if cursor in seen:
                raise EconomicDatasetV2Error("publication event predecessor cycle detected")
            seen.add(cursor)
            cursor = events[cursor].predecessor_event_id


def _validate_evidence_closure(
    events: dict[str, EconomicPublicationEvent],
    evidence: dict[str, EconomicAvailabilityEvidence],
    raw_digests: frozenset[str],
) -> None:
    for row in evidence.values():
        if row.publication_event_id not in events:
            raise EconomicDatasetV2Error(
                "availability evidence references unknown publication event"
            )
        if row.raw_sha256 not in raw_digests:
            raise EconomicDatasetV2Error("availability evidence is not closed by raw evidence")
    for event in events.values():
        if event.raw_sha256 not in raw_digests:
            raise EconomicDatasetV2Error("publication event is not closed by raw evidence")
        for evidence_id in event.availability_evidence_ids:
            item = evidence.get(evidence_id)
            if item is None:
                raise EconomicDatasetV2Error("publication event availability evidence is missing")
            if item.publication_event_id != event.event_id:
                raise EconomicDatasetV2Error("availability evidence/event linkage mismatch")
        admitted = event.availability_evidence_id
        if admitted is not None and admitted not in evidence:
            raise EconomicDatasetV2Error("admitted availability evidence is missing")


def _validate_observation_closure(
    registry: EconomicSeriesRegistry,
    observations: tuple[EconomicObservationV2, ...],
    events: dict[str, EconomicPublicationEvent],
    evidence: dict[str, EconomicAvailabilityEvidence],
    raw_digests: frozenset[str],
) -> None:
    registered = {definition.series_id for definition in registry.definitions}
    for row in observations:
        if row.series_id not in registered:
            raise EconomicDatasetV2Error(
                f"observation series missing from registry: {row.series_id}"
            )
        definition = registry.by_id(row.series_id)
        if (row.unit, row.scale, row.frequency) != (
            definition.unit,
            definition.scale,
            definition.frequency,
        ):
            raise EconomicDatasetV2Error("observation semantics do not match series registry")
        if row.raw_sha256 not in raw_digests:
            raise EconomicDatasetV2Error("observation is not closed by raw evidence")
        event = events.get(row.publication_event_id)
        if event is None:
            raise EconomicDatasetV2Error("observation references unknown publication event")
        if (
            row.availability_evidence_id is not None
            and row.availability_evidence_id not in evidence
        ):
            raise EconomicDatasetV2Error("observation availability evidence is missing")
        if row.available_time != event.available_time or row.available_date != event.available_date:
            raise EconomicDatasetV2Error("observation/event admitted availability mismatch")
        if row.availability_evidence_id != event.availability_evidence_id:
            raise EconomicDatasetV2Error("observation/event availability evidence mismatch")
        if row.availability_channel != event.availability_channel:
            raise EconomicDatasetV2Error("observation/event availability channel mismatch")
        if row.availability_precision is not event.availability_precision:
            raise EconomicDatasetV2Error("observation/event availability precision mismatch")
        if row.publication_sequence is not event.publication_sequence:
            raise EconomicDatasetV2Error("observation/event publication sequence mismatch")
        if row.revision_class is not event.revision_class:
            raise EconomicDatasetV2Error("observation/event revision class mismatch")
        if economic_observation_version_id(row) != row.version_id:
            raise EconomicDatasetV2Error("observation version_id does not match semantic identity")


def _validate_observation_graph(observations: dict[str, EconomicObservationV2]) -> None:
    for row in observations.values():
        predecessor_id = row.predecessor_version_id
        if row.revision_class is RevisionClass.INITIAL:
            if predecessor_id is not None:
                raise EconomicDatasetV2Error("initial observation cannot have predecessor")
            continue
        if predecessor_id is None:
            raise EconomicDatasetV2Error("revised observation predecessor is required")
        predecessor = observations.get(predecessor_id)
        if predecessor is None:
            raise EconomicDatasetV2Error("observation predecessor is missing")
        if predecessor.series_id != row.series_id:
            raise EconomicDatasetV2Error("observation predecessor series mismatch")
        if predecessor.reference_period_start != row.reference_period_start:
            raise EconomicDatasetV2Error("observation predecessor reference period mismatch")
        if predecessor.reference_period_end != row.reference_period_end:
            raise EconomicDatasetV2Error("observation predecessor reference period mismatch")
    for version_id in observations:
        seen: set[str] = set()
        cursor: str | None = version_id
        while cursor is not None:
            if cursor in seen:
                raise EconomicDatasetV2Error("observation predecessor cycle detected")
            seen.add(cursor)
            cursor = observations[cursor].predecessor_version_id


def _identity_payload(
    *,
    canonical_observations_sha256: str,
    publication_events_sha256: str,
    availability_evidence_sha256: str,
    series_registry_sha256: str,
    raw_inventory_root_sha256: str,
    observation_count: int,
    publication_event_count: int,
    availability_evidence_count: int,
    series_count: int,
    minimum_observation_time: datetime,
    maximum_observation_time: datetime,
    minimum_reference_period_start: date,
    maximum_reference_period_end: date,
    minimum_exact_available_time: datetime | None,
    maximum_exact_available_time: datetime | None,
) -> dict[str, object]:
    return {
        "schema_version": ECONOMIC_DATASET_SCHEMA_V2,
        "canonical_observations_sha256": canonical_observations_sha256,
        "publication_events_sha256": publication_events_sha256,
        "availability_evidence_sha256": availability_evidence_sha256,
        "series_registry_sha256": series_registry_sha256,
        "raw_inventory_root_sha256": raw_inventory_root_sha256,
        "observation_count": observation_count,
        "publication_event_count": publication_event_count,
        "availability_evidence_count": availability_evidence_count,
        "series_count": series_count,
        "minimum_observation_time": minimum_observation_time.isoformat(),
        "maximum_observation_time": maximum_observation_time.isoformat(),
        "minimum_reference_period_start": minimum_reference_period_start.isoformat(),
        "maximum_reference_period_end": maximum_reference_period_end.isoformat(),
        "minimum_exact_available_time": (
            None
            if minimum_exact_available_time is None
            else minimum_exact_available_time.isoformat()
        ),
        "maximum_exact_available_time": (
            None
            if maximum_exact_available_time is None
            else maximum_exact_available_time.isoformat()
        ),
    }


def build_economic_dataset_v2(
    *,
    registry: EconomicSeriesRegistry,
    observations: tuple[EconomicObservationV2, ...],
    publication_events: tuple[EconomicPublicationEvent, ...],
    availability_evidence: tuple[EconomicAvailabilityEvidence, ...],
    raw_inventory: RawEvidenceInventory,
) -> EconomicDatasetV2:
    if not observations:
        raise EconomicDatasetV2Error("economic dataset v2 requires observations")
    if not publication_events:
        raise EconomicDatasetV2Error("economic dataset v2 requires publication events")

    observation_map, event_map, evidence_map = _validate_unique_ids(
        observations,
        publication_events,
        availability_evidence,
    )
    _validate_event_graph(event_map)
    _validate_evidence_closure(event_map, evidence_map, raw_inventory.raw_digests)
    _validate_observation_closure(
        registry,
        observations,
        event_map,
        evidence_map,
        raw_inventory.raw_digests,
    )
    _validate_observation_graph(observation_map)

    ordered_observations = tuple(
        sorted(
            observations,
            key=lambda row: (
                row.series_id,
                row.reference_period_start,
                row.reference_period_end,
                row.version_id,
            ),
        )
    )
    ordered_events = tuple(sorted(publication_events, key=lambda row: row.event_id))
    ordered_evidence = tuple(sorted(availability_evidence, key=lambda row: row.evidence_id))

    observation_bytes = serialize_observations_v2(ordered_observations)
    event_bytes = serialize_publication_events(ordered_events)
    evidence_bytes = serialize_availability_evidence(ordered_evidence)
    registry_bytes = serialize_series_registry(registry)

    observation_sha = sha256(observation_bytes).hexdigest()
    event_sha = sha256(event_bytes).hexdigest()
    evidence_sha = sha256(evidence_bytes).hexdigest()
    registry_sha = sha256(registry_bytes).hexdigest()
    raw_root = raw_inventory.inventory_root_sha256

    minimum_observation_time = min(_utc(row.observation_time) for row in ordered_observations)
    maximum_observation_time = max(_utc(row.observation_time) for row in ordered_observations)
    minimum_reference_period_start = min(row.reference_period_start for row in ordered_observations)
    maximum_reference_period_end = max(row.reference_period_end for row in ordered_observations)
    exact_available_times = tuple(
        _utc(row.available_time) for row in ordered_observations if row.available_time is not None
    )
    minimum_exact_available_time = min(exact_available_times) if exact_available_times else None
    maximum_exact_available_time = max(exact_available_times) if exact_available_times else None
    series_count = len({row.series_id for row in ordered_observations})

    identity_payload = _identity_payload(
        canonical_observations_sha256=observation_sha,
        publication_events_sha256=event_sha,
        availability_evidence_sha256=evidence_sha,
        series_registry_sha256=registry_sha,
        raw_inventory_root_sha256=raw_root,
        observation_count=len(ordered_observations),
        publication_event_count=len(ordered_events),
        availability_evidence_count=len(ordered_evidence),
        series_count=series_count,
        minimum_observation_time=minimum_observation_time,
        maximum_observation_time=maximum_observation_time,
        minimum_reference_period_start=minimum_reference_period_start,
        maximum_reference_period_end=maximum_reference_period_end,
        minimum_exact_available_time=minimum_exact_available_time,
        maximum_exact_available_time=maximum_exact_available_time,
    )
    dataset_id = sha256(canonical_json_bytes(identity_payload)).hexdigest()
    manifest = EconomicDatasetManifestV2(
        schema_version=ECONOMIC_DATASET_SCHEMA_V2,
        dataset_id=dataset_id,
        canonical_observations_sha256=observation_sha,
        publication_events_sha256=event_sha,
        availability_evidence_sha256=evidence_sha,
        series_registry_sha256=registry_sha,
        raw_inventory_root_sha256=raw_root,
        observation_count=len(ordered_observations),
        publication_event_count=len(ordered_events),
        availability_evidence_count=len(ordered_evidence),
        series_count=series_count,
        minimum_observation_time=minimum_observation_time,
        maximum_observation_time=maximum_observation_time,
        minimum_reference_period_start=minimum_reference_period_start,
        maximum_reference_period_end=maximum_reference_period_end,
        minimum_exact_available_time=minimum_exact_available_time,
        maximum_exact_available_time=maximum_exact_available_time,
    )
    return EconomicDatasetV2(
        manifest=manifest,
        registry=registry,
        observations=ordered_observations,
        publication_events=ordered_events,
        availability_evidence=ordered_evidence,
        raw_inventory=raw_inventory,
        series_registry_bytes=registry_bytes,
        canonical_observation_bytes=observation_bytes,
        publication_event_bytes=event_bytes,
        availability_evidence_bytes=evidence_bytes,
    )


__all__ = [
    "ECONOMIC_DATASET_SCHEMA_V2",
    "EconomicDatasetManifestV2",
    "EconomicDatasetV2",
    "EconomicDatasetV2Error",
    "build_economic_dataset_v2",
]
