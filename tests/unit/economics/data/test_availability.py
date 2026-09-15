from datetime import UTC, date, datetime

import pytest

from gemini_trading.economics.data.availability import (
    ECONOMIC_AVAILABILITY_EVIDENCE_SCHEMA_V1,
    AvailabilityPrecision,
    EconomicAvailabilityEvidence,
)
from gemini_trading.economics.data.observation import (
    EconomicChronologyError,
    EconomicDataError,
)


def _evidence(**overrides: object) -> EconomicAvailabilityEvidence:
    values: dict[str, object] = {
        "schema_version": "economic-availability-evidence-v1",
        "evidence_id": "bls-cpi-2026-08-release-time",
        "publication_event_id": "bls-cpi-2026-08",
        "source_id": "bls.news-release",
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


def test_schema_constant_is_frozen() -> None:
    assert ECONOMIC_AVAILABILITY_EVIDENCE_SCHEMA_V1 == "economic-availability-evidence-v1"


def test_exact_minute_evidence_accepts_evidenced_instant() -> None:
    row = _evidence()
    assert row.available_time == datetime(2026, 8, 12, 12, 30, tzinfo=UTC)
    assert row.available_date is None


def test_date_only_evidence_does_not_fabricate_instant() -> None:
    row = _evidence(
        availability_precision=AvailabilityPrecision.DATE_ONLY,
        available_time=None,
        available_date=date(2026, 8, 12),
    )
    assert row.available_time is None
    assert row.available_date == date(2026, 8, 12)


def test_inferred_interval_requires_ordered_aware_bounds() -> None:
    row = _evidence(
        availability_precision=AvailabilityPrecision.INFERRED_INTERVAL,
        available_time=None,
        interval_start=datetime(2026, 8, 12, 12, 30, tzinfo=UTC),
        interval_end=datetime(2026, 8, 12, 12, 35, tzinfo=UTC),
        retrieved_time=datetime(2026, 8, 12, 12, 36, tzinfo=UTC),
    )
    assert row.interval_start is not None
    assert row.interval_end is not None


def test_unknown_precision_rejects_fabricated_instant() -> None:
    with pytest.raises(EconomicDataError, match="UNKNOWN"):
        _evidence(availability_precision=AvailabilityPrecision.UNKNOWN)


def test_date_only_rejects_available_time() -> None:
    with pytest.raises(EconomicDataError, match="DATE_ONLY"):
        _evidence(
            availability_precision=AvailabilityPrecision.DATE_ONLY,
            available_date=date(2026, 8, 12),
        )


def test_exact_minute_rejects_false_second_precision() -> None:
    with pytest.raises(EconomicDataError, match="EXACT_MINUTE"):
        _evidence(available_time=datetime(2026, 8, 12, 12, 30, 1, tzinfo=UTC))


def test_retrieved_time_cannot_precede_exact_availability() -> None:
    with pytest.raises(EconomicChronologyError, match="retrieved_time"):
        _evidence(retrieved_time=datetime(2026, 8, 12, 12, 29, tzinfo=UTC))


def test_inferred_interval_rejects_reversed_bounds() -> None:
    with pytest.raises(EconomicChronologyError, match="interval"):
        _evidence(
            availability_precision=AvailabilityPrecision.INFERRED_INTERVAL,
            available_time=None,
            interval_start=datetime(2026, 8, 12, 12, 35, tzinfo=UTC),
            interval_end=datetime(2026, 8, 12, 12, 30, tzinfo=UTC),
        )


@pytest.mark.parametrize("field", ["evidence_id", "publication_event_id", "source_id"])
def test_required_identity_fields_are_nonblank(field: str) -> None:
    with pytest.raises(EconomicDataError, match=field):
        _evidence(**{field: "   "})


def test_raw_digest_must_be_lowercase_sha256() -> None:
    with pytest.raises(EconomicDataError, match="raw_sha256"):
        _evidence(raw_sha256="A" * 64)
