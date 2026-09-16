from datetime import UTC, date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from gemini_trading.economics.data.availability import (
    AvailabilityPrecision,
    AvailabilityStatus,
    EconomicAvailabilityEvidence,
)
from gemini_trading.economics.data.observation import EconomicDataError
from gemini_trading.economics.data.observation_v2 import EconomicObservationV2
from gemini_trading.economics.data.publication import (
    EconomicPublicationEvent,
    PublicationSequence,
    RevisionClass,
)
from gemini_trading.economics.data.serialization_v2 import (
    serialize_availability_evidence,
    serialize_observations_v2,
    serialize_publication_events,
)


def _evidence(evidence_id: str = "time", **overrides: object) -> EconomicAvailabilityEvidence:
    values: dict[str, object] = {
        "schema_version": "economic-availability-evidence-v1",
        "evidence_id": evidence_id,
        "publication_event_id": "event",
        "source_id": "official",
        "consumer_class": "public",
        "availability_channel": "official_publisher",
        "availability_precision": AvailabilityPrecision.EXACT_MINUTE,
        "available_time": datetime(2026, 8, 12, 12, 30, tzinfo=UTC),
        "available_date": None,
        "interval_start": None,
        "interval_end": None,
        "source_timezone": "America/New_York",
        "source_utc_offset_minutes": -240,
        "retrieved_time": datetime(2026, 8, 12, 12, 31, tzinfo=UTC),
        "raw_sha256": "a" * 64,
    }
    values.update(overrides)
    return EconomicAvailabilityEvidence(**values)  # type: ignore[arg-type]


def _event(event_id: str = "event", **overrides: object) -> EconomicPublicationEvent:
    values: dict[str, object] = {
        "schema_version": "economic-publication-event-v1",
        "event_id": event_id,
        "publisher": "BLS",
        "source_id": "official",
        "event_type": "CPI_RELEASE",
        "scheduled_time": datetime(2026, 8, 12, 12, 30, tzinfo=UTC),
        "published_time": datetime(2026, 8, 12, 12, 30, tzinfo=UTC),
        "available_time": datetime(2026, 8, 12, 12, 30, tzinfo=UTC),
        "available_date": None,
        "consumer_class": "public",
        "availability_channel": "official_publisher",
        "availability_precision": AvailabilityPrecision.EXACT_MINUTE,
        "availability_evidence_ids": ("time",),
        "availability_evidence_id": "time",
        "availability_status": AvailabilityStatus.RESOLVED,
        "publication_sequence": PublicationSequence.INITIAL,
        "revision_class": RevisionClass.INITIAL,
        "provider_native_publication_sequence": "News Release",
        "provider_native_event_id": "native-event",
        "provider_native_source_id": "CPI",
        "source_version": None,
        "predecessor_event_id": None,
        "retrieved_time": datetime(2026, 8, 12, 12, 31, tzinfo=UTC),
        "raw_sha256": "b" * 64,
    }
    values.update(overrides)
    return EconomicPublicationEvent(**values)  # type: ignore[arg-type]


def _observation(series_id: str = "macro.us.cpi", **overrides: object) -> EconomicObservationV2:
    values: dict[str, object] = {
        "schema_version": "economic-observation-v2",
        "version_id": "",
        "series_id": series_id,
        "observation_time": datetime(2026, 7, 1, tzinfo=UTC),
        "reference_period_start": date(2026, 7, 1),
        "reference_period_end": date(2026, 7, 31),
        "available_time": datetime(2026, 8, 12, 12, 30, tzinfo=UTC),
        "available_date": None,
        "vintage_time": datetime(2026, 8, 12, 12, 30, tzinfo=UTC),
        "vintage_date": None,
        "retrieved_time": datetime(2026, 8, 12, 12, 31, tzinfo=UTC),
        "source_id": "official",
        "value": Decimal("324.100"),
        "unit": "index",
        "scale": Decimal("1"),
        "frequency": "monthly",
        "publication_event_id": "event",
        "availability_evidence_id": "time",
        "availability_channel": "official_publisher",
        "availability_precision": AvailabilityPrecision.EXACT_MINUTE,
        "provider_native_source_id": "CPI",
        "source_version": None,
        "publication_sequence": PublicationSequence.INITIAL,
        "revision_class": RevisionClass.INITIAL,
        "predecessor_version_id": None,
        "raw_sha256": "c" * 64,
    }
    values.update(overrides)
    return EconomicObservationV2(**values)  # type: ignore[arg-type]


def test_observation_bytes_are_input_order_independent() -> None:
    first = _observation("macro.a")
    second = _observation("macro.b")
    assert serialize_observations_v2((first, second)) == serialize_observations_v2((second, first))


def test_date_only_serialization_never_fabricates_midnight() -> None:
    evidence = _evidence(
        availability_precision=AvailabilityPrecision.DATE_ONLY,
        available_time=None,
        available_date=date(2026, 8, 12),
    )
    encoded = serialize_availability_evidence((evidence,)).decode()
    assert '"available_date":"2026-08-12"' in encoded
    assert '"available_time":null' in encoded
    assert "2026-08-12T00:00" not in encoded


def test_utc_normalization_is_deterministic() -> None:
    dubai = timezone(timedelta(hours=4))
    event = _event(
        scheduled_time=datetime(2026, 8, 12, 16, 30, tzinfo=dubai),
        published_time=datetime(2026, 8, 12, 16, 30, tzinfo=dubai),
        available_time=datetime(2026, 8, 12, 16, 30, tzinfo=dubai),
        retrieved_time=datetime(2026, 8, 12, 16, 31, tzinfo=dubai),
    )
    encoded = serialize_publication_events((event,)).decode()
    assert "2026-08-12T12:30:00.000000Z" in encoded


def test_decimal_value_is_non_scientific_and_optionals_are_explicit() -> None:
    encoded = serialize_observations_v2((_observation(),)).decode()
    assert '"value":"324.100"' in encoded
    assert '"source_version":null' in encoded


def test_duplicate_logical_identities_fail_closed() -> None:
    with pytest.raises(EconomicDataError, match="duplicate"):
        serialize_availability_evidence((_evidence(), _evidence()))
    with pytest.raises(EconomicDataError, match="duplicate"):
        serialize_publication_events((_event(), _event()))
    row = _observation()
    with pytest.raises(EconomicDataError, match="duplicate"):
        serialize_observations_v2((row, row))


def test_publication_evidence_id_order_is_canonical() -> None:
    first = _event(availability_evidence_ids=("a", "b"), availability_evidence_id="a")
    second = _event(availability_evidence_ids=("b", "a"), availability_evidence_id="a")
    assert serialize_publication_events((first,)) == serialize_publication_events((second,))
