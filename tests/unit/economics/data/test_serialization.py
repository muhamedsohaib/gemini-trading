"""Deterministic byte contracts for Economic Data Fabric v1."""

import json
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from gemini_trading.economics.data.observation import (
    EconomicDataError,
    EconomicObservation,
)
from gemini_trading.economics.data.serialization import (
    observation_identity_key,
    serialize_observations,
    serialize_series_registry,
)
from gemini_trading.economics.data.series import (
    EconomicDomain,
    EconomicSeriesDefinition,
    EconomicSeriesRegistry,
    RevisionPolicy,
)


def _observation(
    *,
    series_id: str = "macro.us.cpi.all_items.index",
    observation_time: datetime = datetime(2026, 7, 1, tzinfo=UTC),
    available_time: datetime = datetime(2026, 8, 12, 12, 30, tzinfo=UTC),
    vintage_time: datetime | None = datetime(2026, 8, 12, 12, 30, tzinfo=UTC),
    retrieved_time: datetime = datetime(2026, 8, 12, 12, 31, tzinfo=UTC),
    source_id: str = "fixture.macro.v1",
    value: Decimal = Decimal("324.100"),
    unit: str = "index",
    scale: Decimal = Decimal("1"),
    frequency: str = "monthly",
    release_id: str | None = "cpi-2026-08",
    raw_sha256: str = "a" * 64,
) -> EconomicObservation:
    return EconomicObservation(
        schema_version="economic-observation-v1",
        series_id=series_id,
        observation_time=observation_time,
        available_time=available_time,
        vintage_time=vintage_time,
        retrieved_time=retrieved_time,
        source_id=source_id,
        value=value,
        unit=unit,
        scale=scale,
        frequency=frequency,
        release_id=release_id,
        raw_sha256=raw_sha256,
    )


def _registry() -> EconomicSeriesRegistry:
    return EconomicSeriesRegistry(
        (
            EconomicSeriesDefinition(
                schema_version="economic-series-v1",
                series_id="market.usd.dxy.index",
                title="US Dollar Index",
                domain=EconomicDomain.MARKET,
                unit="index",
                scale=Decimal("1"),
                frequency="daily",
                observation_semantics="market observation timestamp",
                availability_semantics="public market availability timestamp",
                revision_policy=RevisionPolicy.NONE,
            ),
            EconomicSeriesDefinition(
                schema_version="economic-series-v1",
                series_id="macro.us.cpi.all_items.index",
                title="US CPI All Items",
                domain=EconomicDomain.MACRO,
                unit="index",
                scale=Decimal("1"),
                frequency="monthly",
                observation_semantics="reference-month start",
                availability_semantics="public release timestamp",
                revision_policy=RevisionPolicy.REVISIONED,
            ),
        )
    )


def test_observation_identity_normalizes_timezone_for_comparison() -> None:
    dubai = timezone(timedelta(hours=4))
    utc_row = _observation()
    dubai_row = _observation(
        observation_time=datetime(2026, 7, 1, 4, tzinfo=dubai),
        available_time=datetime(2026, 8, 12, 16, 30, tzinfo=dubai),
        vintage_time=datetime(2026, 8, 12, 16, 30, tzinfo=dubai),
        retrieved_time=datetime(2026, 8, 12, 16, 31, tzinfo=dubai),
    )

    assert observation_identity_key(utc_row) == observation_identity_key(dubai_row)


def test_observations_serialize_in_canonical_order_not_input_order() -> None:
    macro = _observation()
    market = _observation(
        series_id="market.usd.dxy.index",
        observation_time=datetime(2026, 8, 12, 12, 29, tzinfo=UTC),
        available_time=datetime(2026, 8, 12, 12, 30, tzinfo=UTC),
        vintage_time=None,
        retrieved_time=datetime(2026, 8, 12, 12, 30, 1, tzinfo=UTC),
        source_id="fixture.market.v1",
        value=Decimal("99.1250"),
        frequency="daily",
        release_id=None,
        raw_sha256="b" * 64,
    )

    first = serialize_observations((market, macro))
    second = serialize_observations((macro, market))

    assert first == second
    rows = [json.loads(line) for line in first.decode("utf-8").splitlines()]
    assert [row["series_id"] for row in rows] == [
        "macro.us.cpi.all_items.index",
        "market.usd.dxy.index",
    ]
    assert rows[1]["value"] == "99.1250"
    assert rows[1]["vintage_time"] is None


def test_observation_serialization_has_frozen_key_order() -> None:
    encoded = serialize_observations((_observation(),)).decode("utf-8")

    assert encoded.startswith(
        '{"schema_version":"economic-observation-v1",'
        '"series_id":"macro.us.cpi.all_items.index",'
        '"observation_time":"2026-07-01T00:00:00.000Z",'
        '"available_time":"2026-08-12T12:30:00.000Z",'
        '"vintage_time":"2026-08-12T12:30:00.000Z",'
        '"retrieved_time":"2026-08-12T12:31:00.000Z",'
        '"source_id":"fixture.macro.v1",'
        '"value":"324.100",'
        '"unit":"index",'
        '"scale":"1",'
        '"frequency":"monthly",'
        '"release_id":"cpi-2026-08",'
        '"raw_sha256":"'
    )
    assert encoded.endswith(f'{"a" * 64}"}}\n')


def test_serialization_normalizes_offset_datetimes_to_utc_milliseconds() -> None:
    dubai = timezone(timedelta(hours=4))
    encoded = serialize_observations(
        (
            _observation(
                observation_time=datetime(2026, 7, 1, 4, tzinfo=dubai),
                available_time=datetime(2026, 8, 12, 16, 30, tzinfo=dubai),
                vintage_time=datetime(2026, 8, 12, 16, 30, tzinfo=dubai),
                retrieved_time=datetime(2026, 8, 12, 16, 31, tzinfo=dubai),
                value=Decimal("1.2300"),
            ),
        )
    ).decode("utf-8")

    row = json.loads(encoded)
    assert row["observation_time"] == "2026-07-01T00:00:00.000Z"
    assert row["available_time"] == "2026-08-12T12:30:00.000Z"
    assert row["value"] == "1.2300"


def test_duplicate_logical_observation_identity_fails_closed() -> None:
    first = _observation(value=Decimal("324.100"), raw_sha256="a" * 64)
    conflicting = _observation(value=Decimal("325.000"), raw_sha256="b" * 64)

    with pytest.raises(EconomicDataError, match="duplicate economic observation identity"):
        serialize_observations((first, conflicting))


def test_series_registry_serialization_is_sorted_and_deterministic() -> None:
    registry = _registry()

    first = serialize_series_registry(registry)
    second = serialize_series_registry(EconomicSeriesRegistry(tuple(reversed(registry.definitions))))

    assert first == second
    rows = [json.loads(line) for line in first.decode("utf-8").splitlines()]
    assert [row["series_id"] for row in rows] == [
        "macro.us.cpi.all_items.index",
        "market.usd.dxy.index",
    ]
    assert rows[0]["domain"] == "MACRO"
    assert rows[0]["revision_policy"] == "REVISIONED"
    assert rows[0]["scale"] == "1"
