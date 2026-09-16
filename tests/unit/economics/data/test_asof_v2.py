from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from gemini_trading.economics.data.asof_v2 import (
    latest_visible_vintages_v2,
    observations_as_of_date_v2,
    observations_as_of_v2,
)
from gemini_trading.economics.data.availability import AvailabilityPrecision
from gemini_trading.economics.data.observation import EconomicDataError
from gemini_trading.economics.data.observation_v2 import EconomicObservationV2
from gemini_trading.economics.data.publication import PublicationSequence, RevisionClass

RELEASE = datetime(2026, 8, 12, 12, 30, tzinfo=UTC)


def _row(**overrides: object) -> EconomicObservationV2:
    values: dict[str, object] = {
        "schema_version": "economic-observation-v2",
        "version_id": "",
        "series_id": "macro.us.cpi.all_items.index",
        "observation_time": datetime(2026, 7, 1, tzinfo=UTC),
        "reference_period_start": date(2026, 7, 1),
        "reference_period_end": date(2026, 7, 31),
        "available_time": RELEASE,
        "available_date": None,
        "vintage_time": RELEASE,
        "vintage_date": None,
        "retrieved_time": RELEASE + timedelta(minutes=1),
        "source_id": "bls.cpi",
        "value": Decimal("324.100"),
        "unit": "index",
        "scale": Decimal("1"),
        "frequency": "monthly",
        "publication_event_id": "cpi-release",
        "availability_evidence_id": "cpi-time",
        "availability_channel": "official_publisher",
        "availability_precision": AvailabilityPrecision.EXACT_MINUTE,
        "provider_native_source_id": "CUUR0000SA0",
        "source_version": None,
        "publication_sequence": PublicationSequence.INITIAL,
        "revision_class": RevisionClass.INITIAL,
        "predecessor_version_id": None,
        "raw_sha256": "a" * 64,
    }
    values.update(overrides)
    return EconomicObservationV2(**values)  # type: ignore[arg-type]


@dataclass(frozen=True, slots=True)
class _DatasetView:
    observations: tuple[EconomicObservationV2, ...]


def _dataset(*rows: EconomicObservationV2) -> _DatasetView:
    return _DatasetView(observations=tuple(rows))


def test_exact_release_boundary_is_closed_on_right() -> None:
    dataset = _dataset(_row())
    assert observations_as_of_v2(dataset, RELEASE - timedelta(microseconds=1)) == ()
    assert len(observations_as_of_v2(dataset, RELEASE)) == 1
    assert len(observations_as_of_v2(dataset, RELEASE + timedelta(microseconds=1))) == 1


def test_date_only_is_rejected_from_exact_intraday_path() -> None:
    row = _row(
        available_time=None,
        available_date=date(2026, 8, 12),
        vintage_time=None,
        vintage_date=date(2026, 8, 12),
        availability_precision=AvailabilityPrecision.DATE_ONLY,
    )
    assert observations_as_of_v2(_dataset(row), RELEASE + timedelta(days=1)) == ()


def test_coarse_date_path_is_explicit_and_excludes_same_day() -> None:
    row = _row(
        available_time=None,
        available_date=date(2026, 8, 12),
        vintage_time=None,
        vintage_date=date(2026, 8, 12),
        availability_precision=AvailabilityPrecision.DATE_ONLY,
    )
    dataset = _dataset(row)
    assert observations_as_of_date_v2(dataset, date(2026, 8, 12)) == ()
    assert observations_as_of_date_v2(dataset, date(2026, 8, 13)) == (row,)


def test_latest_visible_vintage_groups_by_reference_interval() -> None:
    initial = _row()
    revised = _row(
        value=Decimal("324.200"),
        available_time=RELEASE + timedelta(days=30),
        vintage_time=RELEASE + timedelta(days=30),
        retrieved_time=RELEASE + timedelta(days=30, minutes=1),
        publication_event_id="cpi-revision",
        availability_evidence_id="cpi-revision-time",
        publication_sequence=PublicationSequence.ROUTINE_REVISION,
        revision_class=RevisionClass.ROUTINE_REVISION,
        predecessor_version_id=initial.version_id,
    )
    dataset = _dataset(initial, revised)
    assert latest_visible_vintages_v2(dataset, RELEASE) == (initial,)
    assert latest_visible_vintages_v2(dataset, RELEASE + timedelta(days=30)) == (revised,)


def test_tied_visible_versions_fail_closed() -> None:
    first = _row()
    second = _row(value=Decimal("324.200"), raw_sha256="b" * 64)
    with pytest.raises(EconomicDataError, match="tied visible vintages"):
        latest_visible_vintages_v2(_dataset(first, second), RELEASE)
