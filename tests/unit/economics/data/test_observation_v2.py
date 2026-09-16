from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from gemini_trading.economics.data.availability import AvailabilityPrecision
from gemini_trading.economics.data.observation import (
    EconomicChronologyError,
    EconomicDataError,
)
from gemini_trading.economics.data.observation_v2 import (
    ECONOMIC_OBSERVATION_SCHEMA_V2,
    EconomicObservationV2,
    economic_observation_version_id,
)
from gemini_trading.economics.data.publication import (
    PublicationSequence,
    RevisionClass,
)


def _row(**overrides: object) -> EconomicObservationV2:
    values: dict[str, object] = {
        "schema_version": "economic-observation-v2",
        "version_id": "",
        "series_id": "macro.us.cpi.all_items.index",
        "observation_time": datetime(2026, 7, 1, tzinfo=UTC),
        "reference_period_start": date(2026, 7, 1),
        "reference_period_end": date(2026, 7, 31),
        "available_time": datetime(2026, 8, 12, 12, 30, tzinfo=UTC),
        "available_date": None,
        "vintage_time": datetime(2026, 8, 12, 12, 30, tzinfo=UTC),
        "vintage_date": None,
        "retrieved_time": datetime(2026, 8, 12, 12, 31, tzinfo=UTC),
        "source_id": "bls.cpi",
        "value": Decimal("324.100"),
        "unit": "index",
        "scale": Decimal("1"),
        "frequency": "monthly",
        "publication_event_id": "bls-cpi-2026-08",
        "availability_evidence_id": "bls-cpi-time",
        "availability_channel": "official_publisher",
        "availability_precision": AvailabilityPrecision.EXACT_MINUTE,
        "provider_native_source_id": "CUUR0000SA0",
        "source_version": None,
        "publication_sequence": PublicationSequence.INITIAL,
        "revision_class": RevisionClass.INITIAL,
        "predecessor_version_id": None,
        "raw_sha256": "c" * 64,
    }
    values.update(overrides)
    return EconomicObservationV2(**values)  # type: ignore[arg-type]


def test_schema_constant_is_frozen() -> None:
    assert ECONOMIC_OBSERVATION_SCHEMA_V2 == "economic-observation-v2"


def test_interval_reference_period_is_explicit_calendar_range() -> None:
    row = _row()
    assert row.reference_period_start == date(2026, 7, 1)
    assert row.reference_period_end == date(2026, 7, 31)
    assert row.version_id == economic_observation_version_id(row)


def test_date_only_availability_keeps_available_time_empty() -> None:
    row = _row(
        available_time=None,
        available_date=date(2026, 8, 12),
        availability_precision=AvailabilityPrecision.DATE_ONLY,
        availability_evidence_id="archive-date",
    )
    assert row.available_time is None
    assert row.available_date == date(2026, 8, 12)


def test_vintage_date_is_distinct_from_available_date() -> None:
    row = _row(
        vintage_time=None,
        vintage_date=date(2026, 8, 12),
    )
    assert row.vintage_time is None
    assert row.vintage_date == date(2026, 8, 12)


def test_reference_period_must_be_ordered() -> None:
    with pytest.raises(EconomicChronologyError, match="reference period"):
        _row(
            reference_period_start=date(2026, 7, 31),
            reference_period_end=date(2026, 7, 1),
        )


def test_exact_availability_rejects_missing_instant() -> None:
    with pytest.raises(EconomicDataError, match="exact availability"):
        _row(available_time=None)


def test_date_only_availability_rejects_exact_instant() -> None:
    with pytest.raises(EconomicDataError, match="DATE_ONLY"):
        _row(
            availability_precision=AvailabilityPrecision.DATE_ONLY,
            available_date=date(2026, 8, 12),
        )


def test_unknown_availability_rejects_fabricated_instant() -> None:
    with pytest.raises(EconomicDataError, match="UNKNOWN"):
        _row(availability_precision=AvailabilityPrecision.UNKNOWN)


def test_version_id_is_deterministic_sha256_identity() -> None:
    first = _row()
    second = _row()
    assert first.version_id == second.version_id
    assert len(first.version_id) == 64
    assert set(first.version_id) <= set("0123456789abcdef")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("value", Decimal("324.200")),
        ("available_time", datetime(2026, 8, 12, 12, 31, tzinfo=UTC)),
        ("revision_class", RevisionClass.ROUTINE_REVISION),
        ("source_version", "2026.08"),
    ],
)
def test_version_id_changes_for_meaningful_semantics(field: str, value: object) -> None:
    assert _row(**{field: value}).version_id != _row().version_id


def test_supplied_incorrect_version_id_is_rejected() -> None:
    with pytest.raises(EconomicDataError, match="version_id"):
        _row(version_id="0" * 64)


def test_revision_predecessor_identity_is_preserved() -> None:
    predecessor = _row()
    revised = _row(
        value=Decimal("324.200"),
        publication_sequence=PublicationSequence.ROUTINE_REVISION,
        revision_class=RevisionClass.ROUTINE_REVISION,
        predecessor_version_id=predecessor.version_id,
    )
    assert revised.predecessor_version_id == predecessor.version_id
