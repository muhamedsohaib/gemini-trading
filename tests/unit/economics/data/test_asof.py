"""As-of no-leakage visibility for Economic Data Fabric v1."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from hashlib import sha256

import pytest

from gemini_trading.economics.data.asof import (
    latest_visible_vintages,
    observations_as_of,
)
from gemini_trading.economics.data.dataset import EconomicDataset, build_economic_dataset
from gemini_trading.economics.data.observation import (
    EconomicChronologyError,
    EconomicDataError,
    EconomicObservation,
)
from gemini_trading.economics.data.series import (
    EconomicDomain,
    EconomicSeriesDefinition,
    EconomicSeriesRegistry,
    RevisionPolicy,
)
from gemini_trading.economics.data.storage import RawEvidenceInventory, RawEvidenceReceipt

_SERIES_ID = "macro.test.revisioned.index"
_OBSERVATION_TIME = datetime(2026, 1, 1, tzinfo=UTC)
_INITIAL_AVAILABLE = datetime(2026, 2, 1, 12, tzinfo=UTC)
_REVISED_AVAILABLE = datetime(2026, 3, 1, 12, tzinfo=UTC)


def _receipt(receipt_id: str, payload: bytes) -> RawEvidenceReceipt:
    return RawEvidenceReceipt(
        schema_version="economic-raw-receipt-v1",
        source_id="fixture.macro.v1",
        receipt_id=receipt_id,
        relative_path=f"raw/fixture.macro.v1/{receipt_id}.bin",
        byte_length=len(payload),
        sha256=sha256(payload).hexdigest(),
    )


def _row(
    *,
    value: Decimal,
    available_time: datetime,
    payload: bytes,
    release_id: str,
    source_id: str = "fixture.macro.v1",
    observation_time: datetime = _OBSERVATION_TIME,
) -> EconomicObservation:
    return EconomicObservation(
        schema_version="economic-observation-v1",
        series_id=_SERIES_ID,
        observation_time=observation_time,
        available_time=available_time,
        vintage_time=available_time,
        retrieved_time=available_time + timedelta(minutes=1),
        source_id=source_id,
        value=value,
        unit="index",
        scale=Decimal("1"),
        frequency="monthly",
        release_id=release_id,
        raw_sha256=sha256(payload).hexdigest(),
    )


def _dataset(*extra_rows: EconomicObservation) -> EconomicDataset:
    initial_payload = b"initial"
    revised_payload = b"revised"
    initial = _row(
        value=Decimal("100.0"),
        available_time=_INITIAL_AVAILABLE,
        payload=initial_payload,
        release_id="initial",
    )
    revised = _row(
        value=Decimal("101.0"),
        available_time=_REVISED_AVAILABLE,
        payload=revised_payload,
        release_id="revision-1",
    )
    registry = EconomicSeriesRegistry(
        (
            EconomicSeriesDefinition(
                schema_version="economic-series-v1",
                series_id=_SERIES_ID,
                title="Synthetic Revisioned Index",
                domain=EconomicDomain.MACRO,
                unit="index",
                scale=Decimal("1"),
                frequency="monthly",
                observation_semantics="reference period start",
                availability_semantics="public release timestamp",
                revision_policy=RevisionPolicy.REVISIONED,
            ),
        )
    )
    receipts = [
        _receipt("initial", initial_payload),
        _receipt("revised", revised_payload),
    ]
    for index, row in enumerate(extra_rows, start=1):
        receipts.append(
            RawEvidenceReceipt(
                schema_version="economic-raw-receipt-v1",
                source_id=row.source_id,
                receipt_id=f"extra-{index}",
                relative_path=f"raw/{row.source_id}/extra-{index}.bin",
                byte_length=1,
                sha256=row.raw_sha256,
            )
        )
    return build_economic_dataset(
        registry=registry,
        observations=(initial, revised, *extra_rows),
        raw_inventory=RawEvidenceInventory(tuple(receipts)),
    )


def test_latest_visible_vintage_hides_future_revision() -> None:
    dataset = _dataset()

    pre_revision = latest_visible_vintages(
        dataset,
        datetime(2026, 2, 15, tzinfo=UTC),
    )
    post_revision = latest_visible_vintages(
        dataset,
        datetime(2026, 3, 15, tzinfo=UTC),
    )

    assert len(pre_revision) == 1
    assert pre_revision[0].value == Decimal("100.0")
    assert pre_revision[0].available_time == _INITIAL_AVAILABLE
    assert len(post_revision) == 1
    assert post_revision[0].value == Decimal("101.0")
    assert post_revision[0].available_time == _REVISED_AVAILABLE


def test_available_one_microsecond_after_cutoff_is_invisible() -> None:
    dataset = _dataset()
    cutoff = _REVISED_AVAILABLE - timedelta(microseconds=1)

    visible = observations_as_of(dataset, cutoff)
    latest = latest_visible_vintages(dataset, cutoff)

    assert tuple(row.value for row in visible) == (Decimal("100.0"),)
    assert tuple(row.value for row in latest) == (Decimal("100.0"),)


def test_observations_as_of_uses_available_time_not_retrieved_or_vintage_time() -> None:
    dataset = _dataset()
    visible = observations_as_of(dataset, _INITIAL_AVAILABLE)

    assert len(visible) == 1
    assert visible[0].value == Decimal("100.0")


def test_series_filter_is_applied_without_full_dataset_fallback() -> None:
    dataset = _dataset()

    visible = observations_as_of(
        dataset,
        datetime(2026, 4, 1, tzinfo=UTC),
        series_id="macro.unknown.index",
    )
    latest = latest_visible_vintages(
        dataset,
        datetime(2026, 4, 1, tzinfo=UTC),
        series_id="macro.unknown.index",
    )

    assert visible == ()
    assert latest == ()


def test_visibility_rejects_naive_cutoff() -> None:
    dataset = _dataset()
    naive = datetime(2026, 2, 15)

    with pytest.raises(EconomicChronologyError, match="cutoff"):
        observations_as_of(dataset, naive)
    with pytest.raises(EconomicChronologyError, match="cutoff"):
        latest_visible_vintages(dataset, naive)


def test_latest_visible_vintage_rejects_conflicting_tie() -> None:
    payload = b"x"
    tied = _row(
        value=Decimal("999.0"),
        available_time=_REVISED_AVAILABLE,
        payload=payload,
        release_id="competing-revision",
        source_id="fixture.competing.v1",
    )
    dataset = _dataset(tied)

    with pytest.raises(EconomicDataError, match="tied visible vintages"):
        latest_visible_vintages(dataset, datetime(2026, 3, 15, tzinfo=UTC))


def test_latest_visible_vintages_are_canonically_ordered() -> None:
    second_payload = b"y"
    second = EconomicObservation(
        schema_version="economic-observation-v1",
        series_id=_SERIES_ID,
        observation_time=datetime(2026, 2, 1, tzinfo=UTC),
        available_time=datetime(2026, 3, 5, tzinfo=UTC),
        vintage_time=datetime(2026, 3, 5, tzinfo=UTC),
        retrieved_time=datetime(2026, 3, 5, 0, 1, tzinfo=UTC),
        source_id="fixture.macro.v1",
        value=Decimal("102.0"),
        unit="index",
        scale=Decimal("1"),
        frequency="monthly",
        release_id="feb-initial",
        raw_sha256=sha256(second_payload).hexdigest(),
    )
    dataset = _dataset(second)

    latest = latest_visible_vintages(dataset, datetime(2026, 3, 15, tzinfo=UTC))

    assert tuple(row.observation_time for row in latest) == (
        datetime(2026, 1, 1, tzinfo=UTC),
        datetime(2026, 2, 1, tzinfo=UTC),
    )
