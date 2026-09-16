from datetime import UTC, date, datetime

import pytest

from gemini_trading.economics.data.availability import (
    AvailabilityPrecision,
    AvailabilityStatus,
)
from gemini_trading.economics.data.observation import EconomicDataError
from gemini_trading.economics.data.publication import (
    ECONOMIC_PUBLICATION_EVENT_SCHEMA_V1,
    EconomicPublicationEvent,
    PublicationSequence,
    RevisionClass,
)


def _event(**overrides: object) -> EconomicPublicationEvent:
    values: dict[str, object] = {
        "schema_version": "economic-publication-event-v1",
        "event_id": "bls-cpi-2026-08",
        "publisher": "Bureau of Labor Statistics",
        "source_id": "bls.news-release",
        "event_type": "CPI_RELEASE",
        "scheduled_time": datetime(2026, 8, 12, 12, 30, tzinfo=UTC),
        "published_time": datetime(2026, 8, 12, 12, 30, tzinfo=UTC),
        "available_time": datetime(2026, 8, 12, 12, 30, tzinfo=UTC),
        "available_date": None,
        "consumer_class": "public",
        "availability_channel": "official_publisher",
        "availability_precision": AvailabilityPrecision.EXACT_MINUTE,
        "availability_evidence_ids": ("bls-cpi-time",),
        "availability_evidence_id": "bls-cpi-time",
        "availability_status": AvailabilityStatus.RESOLVED,
        "publication_sequence": PublicationSequence.INITIAL,
        "revision_class": RevisionClass.INITIAL,
        "provider_native_publication_sequence": "News Release",
        "provider_native_event_id": "USDL-26-0001",
        "provider_native_source_id": "CPI",
        "source_version": None,
        "predecessor_event_id": None,
        "retrieved_time": datetime(2026, 8, 12, 12, 31, tzinfo=UTC),
        "raw_sha256": "b" * 64,
    }
    values.update(overrides)
    return EconomicPublicationEvent(**values)  # type: ignore[arg-type]


def test_schema_constant_is_frozen() -> None:
    assert ECONOMIC_PUBLICATION_EVENT_SCHEMA_V1 == "economic-publication-event-v1"


def test_resolved_exact_event_has_single_admitted_evidence() -> None:
    event = _event(availability_evidence_ids=("bls-cpi-time", "archive"))
    assert event.availability_evidence_id == "bls-cpi-time"
    assert event.availability_status is AvailabilityStatus.RESOLVED


def test_resolved_date_only_event_keeps_date_without_instant() -> None:
    event = _event(
        availability_precision=AvailabilityPrecision.DATE_ONLY,
        available_time=None,
        available_date=date(2026, 8, 12),
    )
    assert event.available_time is None
    assert event.available_date == date(2026, 8, 12)


def test_conflicted_event_cannot_carry_admitted_availability() -> None:
    event = _event(
        availability_status=AvailabilityStatus.CONFLICTED,
        availability_precision=AvailabilityPrecision.UNKNOWN,
        available_time=None,
        availability_evidence_ids=("official", "archive"),
        availability_evidence_id=None,
    )
    assert event.available_time is None
    assert event.availability_evidence_id is None


def test_conflicted_event_rejects_exact_admission() -> None:
    with pytest.raises(EconomicDataError, match="CONFLICTED"):
        _event(availability_status=AvailabilityStatus.CONFLICTED)


def test_resolved_event_requires_singular_evidence_to_be_declared() -> None:
    with pytest.raises(EconomicDataError, match="availability_evidence_id"):
        _event(availability_evidence_id="missing")


def test_duplicate_evidence_ids_are_rejected() -> None:
    with pytest.raises(EconomicDataError, match="duplicate"):
        _event(availability_evidence_ids=("same", "same"), availability_evidence_id="same")


def test_correction_is_not_an_economic_revision() -> None:
    correction = _event(
        event_id="bls-cpi-correction",
        publication_sequence=PublicationSequence.CORRECTION,
        revision_class=RevisionClass.CORRECTION,
        predecessor_event_id="bls-cpi-2026-08",
    )
    assert correction.revision_class is RevisionClass.CORRECTION
    assert correction.revision_class is not RevisionClass.ROUTINE_REVISION


def test_unknown_event_cannot_claim_resolved_evidence() -> None:
    with pytest.raises(EconomicDataError, match="UNKNOWN"):
        _event(
            availability_status=AvailabilityStatus.UNKNOWN,
            availability_precision=AvailabilityPrecision.UNKNOWN,
            available_time=None,
        )
