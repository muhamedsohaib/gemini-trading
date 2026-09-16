from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from hashlib import sha256

import pytest

from gemini_trading.economics.data.availability import (
    AvailabilityPrecision,
    AvailabilityStatus,
    EconomicAvailabilityEvidence,
)
from gemini_trading.economics.data.dataset_v2 import (
    EconomicDatasetV2Error,
    build_economic_dataset_v2,
)
from gemini_trading.economics.data.observation_v2 import EconomicObservationV2
from gemini_trading.economics.data.publication import (
    EconomicPublicationEvent,
    PublicationSequence,
    RevisionClass,
)
from gemini_trading.economics.data.series import (
    EconomicDomain,
    EconomicSeriesDefinition,
    EconomicSeriesRegistry,
    RevisionPolicy,
)
from gemini_trading.economics.data.storage import RawEvidenceInventory, RawEvidenceReceipt

_AVAIL_1 = b"availability-1"
_EVENT_1 = b"event-1"
_OBS_1 = b"observation-1"
_AVAIL_2 = b"availability-2"
_EVENT_2 = b"event-2"
_OBS_2 = b"observation-2"


def _digest(payload: bytes) -> str:
    return sha256(payload).hexdigest()


def _receipt(receipt_id: str, payload: bytes) -> RawEvidenceReceipt:
    return RawEvidenceReceipt(
        schema_version="economic-raw-receipt-v1",
        source_id="fixture.v2",
        receipt_id=receipt_id,
        relative_path=f"raw/fixture.v2/{receipt_id}.bin",
        byte_length=len(payload),
        sha256=_digest(payload),
    )


def _registry() -> EconomicSeriesRegistry:
    return EconomicSeriesRegistry(
        (
            EconomicSeriesDefinition(
                schema_version="economic-series-v1",
                series_id="macro.us.cpi",
                title="CPI",
                domain=EconomicDomain.MACRO,
                unit="index",
                scale=Decimal("1"),
                frequency="monthly",
                observation_semantics="calendar month",
                availability_semantics="publication event",
                revision_policy=RevisionPolicy.REVISIONED,
            ),
            EconomicSeriesDefinition(
                schema_version="economic-series-v1",
                series_id="macro.us.cpi.core",
                title="Core CPI",
                domain=EconomicDomain.MACRO,
                unit="index",
                scale=Decimal("1"),
                frequency="monthly",
                observation_semantics="calendar month",
                availability_semantics="publication event",
                revision_policy=RevisionPolicy.REVISIONED,
            ),
        )
    )


def _evidence(
    evidence_id: str = "evidence-1",
    event_id: str = "event-1",
    when: datetime = datetime(2026, 8, 12, 12, 30, tzinfo=UTC),
    raw: bytes = _AVAIL_1,
) -> EconomicAvailabilityEvidence:
    return EconomicAvailabilityEvidence(
        schema_version="economic-availability-evidence-v1",
        evidence_id=evidence_id,
        publication_event_id=event_id,
        source_id="fixture.v2",
        consumer_class="public",
        availability_channel="official_publisher",
        availability_precision=AvailabilityPrecision.EXACT_MINUTE,
        available_time=when,
        available_date=None,
        interval_start=None,
        interval_end=None,
        source_timezone="UTC",
        source_utc_offset_minutes=0,
        retrieved_time=when.replace(minute=when.minute + 1),
        raw_sha256=_digest(raw),
    )


def _event(
    event_id: str = "event-1",
    evidence_id: str = "evidence-1",
    when: datetime = datetime(2026, 8, 12, 12, 30, tzinfo=UTC),
    raw: bytes = _EVENT_1,
    sequence: PublicationSequence = PublicationSequence.INITIAL,
    revision: RevisionClass = RevisionClass.INITIAL,
    predecessor_event_id: str | None = None,
) -> EconomicPublicationEvent:
    return EconomicPublicationEvent(
        schema_version="economic-publication-event-v1",
        event_id=event_id,
        publisher="Fixture Agency",
        source_id="fixture.v2",
        event_type="CPI_RELEASE",
        scheduled_time=when,
        published_time=when,
        available_time=when,
        available_date=None,
        consumer_class="public",
        availability_channel="official_publisher",
        availability_precision=AvailabilityPrecision.EXACT_MINUTE,
        availability_evidence_ids=(evidence_id,),
        availability_evidence_id=evidence_id,
        availability_status=AvailabilityStatus.RESOLVED,
        publication_sequence=sequence,
        revision_class=revision,
        provider_native_publication_sequence=sequence.value,
        provider_native_event_id=event_id,
        provider_native_source_id="CPI",
        source_version=None,
        predecessor_event_id=predecessor_event_id,
        retrieved_time=when.replace(minute=when.minute + 1),
        raw_sha256=_digest(raw),
    )


def _observation(
    series_id: str = "macro.us.cpi",
    event_id: str = "event-1",
    evidence_id: str = "evidence-1",
    when: datetime = datetime(2026, 8, 12, 12, 30, tzinfo=UTC),
    raw: bytes = _OBS_1,
    value: Decimal = Decimal("324.100"),
    sequence: PublicationSequence = PublicationSequence.INITIAL,
    revision: RevisionClass = RevisionClass.INITIAL,
    predecessor_version_id: str | None = None,
    source_version: str | None = None,
) -> EconomicObservationV2:
    return EconomicObservationV2(
        schema_version="economic-observation-v2",
        version_id="",
        series_id=series_id,
        observation_time=datetime(2026, 7, 1, tzinfo=UTC),
        reference_period_start=datetime(2026, 7, 1).date(),
        reference_period_end=datetime(2026, 7, 31).date(),
        available_time=when,
        available_date=None,
        vintage_time=when,
        vintage_date=None,
        retrieved_time=when.replace(minute=when.minute + 1),
        source_id="fixture.v2",
        value=value,
        unit="index",
        scale=Decimal("1"),
        frequency="monthly",
        publication_event_id=event_id,
        availability_evidence_id=evidence_id,
        availability_channel="official_publisher",
        availability_precision=AvailabilityPrecision.EXACT_MINUTE,
        provider_native_source_id="CPI",
        source_version=source_version,
        publication_sequence=sequence,
        revision_class=revision,
        predecessor_version_id=predecessor_version_id,
        raw_sha256=_digest(raw),
    )


def _inventory(*payloads: tuple[str, bytes]) -> RawEvidenceInventory:
    return RawEvidenceInventory(
        tuple(_receipt(receipt_id, payload) for receipt_id, payload in payloads)
    )


def _build_initial(*observations: EconomicObservationV2):
    evidence = _evidence()
    event = _event()
    rows = observations or (_observation(),)
    inventory = _inventory(
        ("availability-1", _AVAIL_1),
        ("event-1", _EVENT_1),
        ("observation-1", _OBS_1),
    )
    return build_economic_dataset_v2(
        registry=_registry(),
        observations=tuple(rows),
        publication_events=(event,),
        availability_evidence=(evidence,),
        raw_inventory=inventory,
    )


def test_one_publication_event_can_publish_multiple_observations() -> None:
    dataset = _build_initial(
        _observation("macro.us.cpi"),
        _observation("macro.us.cpi.core", raw=_OBS_1, value=Decimal("330.200")),
    )
    assert len(dataset.observations) == 2
    assert len(dataset.publication_events) == 1


def test_input_permutation_does_not_change_dataset_identity() -> None:
    first = _build_initial(
        _observation("macro.us.cpi"),
        _observation("macro.us.cpi.core", value=Decimal("330.200")),
    )
    second = _build_initial(
        _observation("macro.us.cpi.core", value=Decimal("330.200")),
        _observation("macro.us.cpi"),
    )
    assert first.manifest.dataset_id == second.manifest.dataset_id


def test_observation_event_precision_mismatch_fails_closed() -> None:
    row = _observation()
    evidence = _evidence()
    event = _event()
    object.__setattr__(row, "availability_precision", AvailabilityPrecision.EXACT_SECOND)
    with pytest.raises(EconomicDatasetV2Error, match="precision"):
        build_economic_dataset_v2(
            registry=_registry(),
            observations=(row,),
            publication_events=(event,),
            availability_evidence=(evidence,),
            raw_inventory=_inventory(
                ("availability-1", _AVAIL_1),
                ("event-1", _EVENT_1),
                ("observation-1", _OBS_1),
            ),
        )


def test_missing_event_evidence_link_fails_closed() -> None:
    with pytest.raises(EconomicDatasetV2Error, match="availability evidence"):
        build_economic_dataset_v2(
            registry=_registry(),
            observations=(_observation(),),
            publication_events=(_event(),),
            availability_evidence=(),
            raw_inventory=_inventory(
                ("event-1", _EVENT_1),
                ("observation-1", _OBS_1),
            ),
        )


def _build_revision(*, revised_series: str = "macro.us.cpi"):
    initial_evidence = _evidence()
    initial_event = _event()
    initial = _observation()
    revised_when = datetime(2026, 9, 12, 12, 30, tzinfo=UTC)
    revised_evidence = _evidence("evidence-2", "event-2", revised_when, _AVAIL_2)
    revised_event = _event(
        "event-2",
        "evidence-2",
        revised_when,
        _EVENT_2,
        PublicationSequence.ROUTINE_REVISION,
        RevisionClass.ROUTINE_REVISION,
        "event-1",
    )
    revised = _observation(
        revised_series,
        "event-2",
        "evidence-2",
        revised_when,
        _OBS_2,
        Decimal("324.200"),
        PublicationSequence.ROUTINE_REVISION,
        RevisionClass.ROUTINE_REVISION,
        initial.version_id,
    )
    inventory = _inventory(
        ("availability-1", _AVAIL_1),
        ("event-1", _EVENT_1),
        ("observation-1", _OBS_1),
        ("availability-2", _AVAIL_2),
        ("event-2", _EVENT_2),
        ("observation-2", _OBS_2),
    )
    return build_economic_dataset_v2(
        registry=_registry(),
        observations=(initial, revised),
        publication_events=(initial_event, revised_event),
        availability_evidence=(initial_evidence, revised_evidence),
        raw_inventory=inventory,
    )


def test_valid_revision_chain_is_admitted() -> None:
    dataset = _build_revision()
    assert len(dataset.observations) == 2


def test_cross_series_predecessor_link_fails_closed() -> None:
    with pytest.raises(EconomicDatasetV2Error, match="predecessor"):
        _build_revision(revised_series="macro.us.cpi.core")


def test_missing_observation_predecessor_fails_closed() -> None:
    initial = _observation()
    revised_when = datetime(2026, 9, 12, 12, 30, tzinfo=UTC)
    revised = _observation(
        when=revised_when,
        event_id="event-2",
        evidence_id="evidence-2",
        raw=_OBS_2,
        value=Decimal("324.200"),
        sequence=PublicationSequence.ROUTINE_REVISION,
        revision=RevisionClass.ROUTINE_REVISION,
        predecessor_version_id="f" * 64,
    )
    revised_evidence = _evidence("evidence-2", "event-2", revised_when, _AVAIL_2)
    revised_event = _event(
        "event-2",
        "evidence-2",
        revised_when,
        _EVENT_2,
        PublicationSequence.ROUTINE_REVISION,
        RevisionClass.ROUTINE_REVISION,
        "event-1",
    )
    with pytest.raises(EconomicDatasetV2Error, match="predecessor"):
        build_economic_dataset_v2(
            registry=_registry(),
            observations=(initial, revised),
            publication_events=(_event(), revised_event),
            availability_evidence=(_evidence(), revised_evidence),
            raw_inventory=_inventory(
                ("availability-1", _AVAIL_1),
                ("event-1", _EVENT_1),
                ("observation-1", _OBS_1),
                ("availability-2", _AVAIL_2),
                ("event-2", _EVENT_2),
                ("observation-2", _OBS_2),
            ),
        )


def test_publication_event_predecessor_cycle_fails_closed() -> None:
    event_a = _event(event_id="event-a", evidence_id="evidence-a", predecessor_event_id="event-b")
    event_b = _event(event_id="event-b", evidence_id="evidence-b", predecessor_event_id="event-a")
    evidence_a = _evidence("evidence-a", "event-a")
    evidence_b = _evidence("evidence-b", "event-b")
    row = _observation(event_id="event-a", evidence_id="evidence-a")
    with pytest.raises(EconomicDatasetV2Error, match="cycle"):
        build_economic_dataset_v2(
            registry=_registry(),
            observations=(row,),
            publication_events=(event_a, event_b),
            availability_evidence=(evidence_a, evidence_b),
            raw_inventory=_inventory(
                ("availability-1", _AVAIL_1),
                ("event-1", _EVENT_1),
                ("observation-1", _OBS_1),
            ),
        )


def test_source_version_changes_dataset_identity() -> None:
    base = _build_initial()
    changed = _build_initial(_observation(source_version="provider-v2"))
    assert changed.manifest.dataset_id != base.manifest.dataset_id


def test_raw_inventory_change_changes_dataset_identity() -> None:
    base = _build_initial()
    extra_payload = b"retained-extra-evidence"
    changed = build_economic_dataset_v2(
        registry=_registry(),
        observations=(_observation(),),
        publication_events=(_event(),),
        availability_evidence=(_evidence(),),
        raw_inventory=_inventory(
            ("availability-1", _AVAIL_1),
            ("event-1", _EVENT_1),
            ("observation-1", _OBS_1),
            ("extra", extra_payload),
        ),
    )
    assert changed.manifest.dataset_id != base.manifest.dataset_id


def test_observation_event_sequence_mismatch_fails_closed() -> None:
    row = _observation()
    object.__setattr__(row, "publication_sequence", PublicationSequence.OTHER)
    with pytest.raises(EconomicDatasetV2Error, match="publication sequence"):
        build_economic_dataset_v2(
            registry=_registry(),
            observations=(row,),
            publication_events=(_event(),),
            availability_evidence=(_evidence(),),
            raw_inventory=_inventory(
                ("availability-1", _AVAIL_1),
                ("event-1", _EVENT_1),
                ("observation-1", _OBS_1),
            ),
        )


def test_observation_event_revision_class_mismatch_fails_closed() -> None:
    row = _observation()
    object.__setattr__(row, "revision_class", RevisionClass.OTHER)
    with pytest.raises(EconomicDatasetV2Error, match="revision class"):
        build_economic_dataset_v2(
            registry=_registry(),
            observations=(row,),
            publication_events=(_event(),),
            availability_evidence=(_evidence(),),
            raw_inventory=_inventory(
                ("availability-1", _AVAIL_1),
                ("event-1", _EVENT_1),
                ("observation-1", _OBS_1),
            ),
        )


def test_observation_event_available_time_mismatch_fails_closed() -> None:
    row = _observation()
    assert row.available_time is not None
    object.__setattr__(row, "available_time", row.available_time + timedelta(minutes=1))
    with pytest.raises(EconomicDatasetV2Error, match="admitted availability"):
        build_economic_dataset_v2(
            registry=_registry(),
            observations=(row,),
            publication_events=(_event(),),
            availability_evidence=(_evidence(),),
            raw_inventory=_inventory(
                ("availability-1", _AVAIL_1),
                ("event-1", _EVENT_1),
                ("observation-1", _OBS_1),
            ),
        )


def test_missing_observation_raw_ancestry_fails_closed() -> None:
    with pytest.raises(EconomicDatasetV2Error, match="observation is not closed"):
        build_economic_dataset_v2(
            registry=_registry(),
            observations=(_observation(),),
            publication_events=(_event(),),
            availability_evidence=(_evidence(),),
            raw_inventory=_inventory(
                ("availability-1", _AVAIL_1),
                ("event-1", _EVENT_1),
            ),
        )


def test_cross_reference_period_predecessor_link_fails_closed() -> None:
    dataset = _build_revision()
    revised = next(
        row for row in dataset.observations if row.revision_class is RevisionClass.ROUTINE_REVISION
    )
    changed = replace(
        revised,
        version_id="",
        reference_period_start=date(2026, 6, 1),
        reference_period_end=date(2026, 6, 30),
    )
    initial = next(
        row for row in dataset.observations if row.revision_class is RevisionClass.INITIAL
    )
    with pytest.raises(EconomicDatasetV2Error, match="reference period"):
        build_economic_dataset_v2(
            registry=dataset.registry,
            observations=(initial, changed),
            publication_events=dataset.publication_events,
            availability_evidence=dataset.availability_evidence,
            raw_inventory=dataset.raw_inventory,
        )


def test_availability_timing_change_changes_dataset_identity() -> None:
    base = _build_initial()
    shifted = datetime(2026, 8, 13, 12, 30, tzinfo=UTC)
    changed = build_economic_dataset_v2(
        registry=_registry(),
        observations=(_observation(when=shifted),),
        publication_events=(_event(when=shifted),),
        availability_evidence=(_evidence(when=shifted),),
        raw_inventory=base.raw_inventory,
    )
    assert changed.manifest.dataset_id != base.manifest.dataset_id


def test_event_lineage_change_changes_dataset_identity() -> None:
    base = _build_revision()
    revised_event = next(
        event
        for event in base.publication_events
        if event.revision_class is RevisionClass.ROUTINE_REVISION
    )
    changed_event = replace(revised_event, predecessor_event_id=None)
    changed = build_economic_dataset_v2(
        registry=base.registry,
        observations=base.observations,
        publication_events=tuple(
            changed_event if event.event_id == revised_event.event_id else event
            for event in base.publication_events
        ),
        availability_evidence=base.availability_evidence,
        raw_inventory=base.raw_inventory,
    )
    assert changed.manifest.dataset_id != base.manifest.dataset_id


def test_resolved_event_admitted_evidence_must_match_selected_availability() -> None:
    mismatched = _evidence(when=datetime(2026, 8, 12, 12, 31, tzinfo=UTC))
    with pytest.raises(EconomicDatasetV2Error, match="admitted availability evidence"):
        build_economic_dataset_v2(
            registry=_registry(),
            observations=(_observation(),),
            publication_events=(_event(),),
            availability_evidence=(mismatched,),
            raw_inventory=_inventory(
                ("availability-1", _AVAIL_1),
                ("event-1", _EVENT_1),
                ("observation-1", _OBS_1),
            ),
        )


def test_resolved_event_rejects_competing_exact_evidence_for_same_channel() -> None:
    competing = _evidence(
        "evidence-2",
        "event-1",
        datetime(2026, 8, 12, 12, 31, tzinfo=UTC),
        _AVAIL_2,
    )
    event = replace(_event(), availability_evidence_ids=("evidence-1", "evidence-2"))
    with pytest.raises(EconomicDatasetV2Error, match="conflicting exact availability evidence"):
        build_economic_dataset_v2(
            registry=_registry(),
            observations=(_observation(),),
            publication_events=(event,),
            availability_evidence=(_evidence(), competing),
            raw_inventory=_inventory(
                ("availability-1", _AVAIL_1),
                ("availability-2", _AVAIL_2),
                ("event-1", _EVENT_1),
                ("observation-1", _OBS_1),
            ),
        )


def test_resolved_event_allows_extra_date_only_evidence_without_promoting_it() -> None:
    coarse = replace(
        _evidence("evidence-2", "event-1", raw=_AVAIL_2),
        availability_precision=AvailabilityPrecision.DATE_ONLY,
        available_time=None,
        available_date=date(2026, 8, 12),
    )
    event = replace(_event(), availability_evidence_ids=("evidence-1", "evidence-2"))
    dataset = build_economic_dataset_v2(
        registry=_registry(),
        observations=(_observation(),),
        publication_events=(event,),
        availability_evidence=(_evidence(), coarse),
        raw_inventory=_inventory(
            ("availability-1", _AVAIL_1),
            ("availability-2", _AVAIL_2),
            ("event-1", _EVENT_1),
            ("observation-1", _OBS_1),
        ),
    )
    assert dataset.manifest.availability_evidence_count == 2
    assert dataset.publication_events[0].availability_evidence_id == "evidence-1"
