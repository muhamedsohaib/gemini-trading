from datetime import UTC, datetime
from decimal import Decimal
from hashlib import sha256
from pathlib import Path

from gemini_trading.economics.data.availability import (
    AvailabilityPrecision,
    AvailabilityStatus,
    EconomicAvailabilityEvidence,
)
from gemini_trading.economics.data.dataset_v2 import EconomicDatasetV2, build_economic_dataset_v2
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

AVAIL_1 = b"availability-1"
EVENT_1 = b"event-1"
OBS_1 = b"observation-1"
AVAIL_2 = b"availability-2"
EVENT_2 = b"event-2"
OBS_2 = b"observation-2"


def digest(payload: bytes) -> str:
    return sha256(payload).hexdigest()


def receipt(receipt_id: str, payload: bytes) -> RawEvidenceReceipt:
    return RawEvidenceReceipt(
        schema_version="economic-raw-receipt-v1",
        source_id="fixture.v2",
        receipt_id=receipt_id,
        relative_path=f"raw/fixture.v2/{receipt_id}.bin",
        byte_length=len(payload),
        sha256=digest(payload),
    )


def registry() -> EconomicSeriesRegistry:
    definitions: list[EconomicSeriesDefinition] = []
    for series_id, title in (
        ("macro.us.cpi", "CPI"),
        ("macro.us.cpi.core", "Core CPI"),
    ):
        definitions.append(
            EconomicSeriesDefinition(
                schema_version="economic-series-v1",
                series_id=series_id,
                title=title,
                domain=EconomicDomain.MACRO,
                unit="index",
                scale=Decimal("1"),
                frequency="monthly",
                observation_semantics="calendar month",
                availability_semantics="publication event",
                revision_policy=RevisionPolicy.REVISIONED,
            )
        )
    return EconomicSeriesRegistry(tuple(definitions))


def evidence(
    evidence_id: str = "evidence-1",
    event_id: str = "event-1",
    when: datetime = datetime(2026, 8, 12, 12, 30, tzinfo=UTC),
    raw: bytes = AVAIL_1,
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
        raw_sha256=digest(raw),
    )


def event(
    event_id: str = "event-1",
    evidence_id: str = "evidence-1",
    when: datetime = datetime(2026, 8, 12, 12, 30, tzinfo=UTC),
    raw: bytes = EVENT_1,
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
        raw_sha256=digest(raw),
    )


def observation(
    series_id: str = "macro.us.cpi",
    event_id: str = "event-1",
    evidence_id: str = "evidence-1",
    when: datetime = datetime(2026, 8, 12, 12, 30, tzinfo=UTC),
    raw: bytes = OBS_1,
    value: Decimal = Decimal("324.100"),
    sequence: PublicationSequence = PublicationSequence.INITIAL,
    revision: RevisionClass = RevisionClass.INITIAL,
    predecessor_version_id: str | None = None,
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
        source_version=None,
        publication_sequence=sequence,
        revision_class=revision,
        predecessor_version_id=predecessor_version_id,
        raw_sha256=digest(raw),
    )


def inventory(*payloads: tuple[str, bytes]) -> RawEvidenceInventory:
    return RawEvidenceInventory(
        tuple(receipt(receipt_id, payload) for receipt_id, payload in payloads)
    )


def build_initial(*observations: EconomicObservationV2) -> EconomicDatasetV2:
    rows = observations or (observation(),)
    return build_economic_dataset_v2(
        registry=registry(),
        observations=tuple(rows),
        publication_events=(event(),),
        availability_evidence=(evidence(),),
        raw_inventory=inventory(
            ("availability-1", AVAIL_1),
            ("event-1", EVENT_1),
            ("observation-1", OBS_1),
        ),
    )


def build_revision() -> EconomicDatasetV2:
    initial = observation()
    revised_when = datetime(2026, 9, 12, 12, 30, tzinfo=UTC)
    revised_evidence = evidence("evidence-2", "event-2", revised_when, AVAIL_2)
    revised_event = event(
        "event-2",
        "evidence-2",
        revised_when,
        EVENT_2,
        PublicationSequence.ROUTINE_REVISION,
        RevisionClass.ROUTINE_REVISION,
        "event-1",
    )
    revised = observation(
        event_id="event-2",
        evidence_id="evidence-2",
        when=revised_when,
        raw=OBS_2,
        value=Decimal("324.200"),
        sequence=PublicationSequence.ROUTINE_REVISION,
        revision=RevisionClass.ROUTINE_REVISION,
        predecessor_version_id=initial.version_id,
    )
    return build_economic_dataset_v2(
        registry=registry(),
        observations=(initial, revised),
        publication_events=(event(), revised_event),
        availability_evidence=(evidence(), revised_evidence),
        raw_inventory=inventory(
            ("availability-1", AVAIL_1),
            ("event-1", EVENT_1),
            ("observation-1", OBS_1),
            ("availability-2", AVAIL_2),
            ("event-2", EVENT_2),
            ("observation-2", OBS_2),
        ),
    )


DEFAULT_RAW_PAYLOADS: dict[str, bytes] = {
    "availability-1": AVAIL_1,
    "event-1": EVENT_1,
    "observation-1": OBS_1,
    "availability-2": AVAIL_2,
    "event-2": EVENT_2,
    "observation-2": OBS_2,
}


def materialize_raw(
    root: Path,
    dataset: EconomicDatasetV2,
    *,
    payloads: dict[str, bytes] | None = None,
) -> None:
    source_payloads = DEFAULT_RAW_PAYLOADS if payloads is None else payloads
    for raw_receipt in dataset.raw_inventory.receipts:
        target = root / raw_receipt.relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            payload = source_payloads[raw_receipt.receipt_id]
        except KeyError:
            raise AssertionError(f"missing fixture payload for {raw_receipt.receipt_id}") from None
        target.write_bytes(payload)


__all__ = [
    "AVAIL_1",
    "AVAIL_2",
    "DEFAULT_RAW_PAYLOADS",
    "EVENT_1",
    "EVENT_2",
    "OBS_1",
    "OBS_2",
    "build_initial",
    "build_revision",
    "digest",
    "event",
    "evidence",
    "inventory",
    "materialize_raw",
    "observation",
    "receipt",
    "registry",
]
