"""Point-in-time observation contract tests for Economic Data Fabric v1."""

from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from gemini_trading.economics.data.observation import (
    ECONOMIC_OBSERVATION_SCHEMA_V1,
    EconomicChronologyError,
    EconomicDataError,
    EconomicObservation,
)


def _valid_observation(**overrides: object) -> EconomicObservation:
    values: dict[str, object] = {
        "schema_version": "economic-observation-v1",
        "series_id": "macro.us.cpi.all_items.index",
        "observation_time": datetime(2026, 7, 1, tzinfo=UTC),
        "available_time": datetime(2026, 8, 12, 12, 30, tzinfo=UTC),
        "vintage_time": datetime(2026, 8, 12, 12, 30, tzinfo=UTC),
        "retrieved_time": datetime(2026, 8, 12, 12, 31, tzinfo=UTC),
        "source_id": "fixture.macro.v1",
        "value": Decimal("324.100"),
        "unit": "index",
        "scale": Decimal("1"),
        "frequency": "monthly",
        "release_id": "cpi-2026-08",
        "raw_sha256": "a" * 64,
    }
    values.update(overrides)
    return EconomicObservation(**values)  # type: ignore[arg-type]


def test_schema_constant_is_frozen() -> None:
    assert ECONOMIC_OBSERVATION_SCHEMA_V1 == "economic-observation-v1"


def test_observation_accepts_point_in_time_revision_row() -> None:
    row = _valid_observation()

    assert row.available_time > row.observation_time
    assert row.retrieved_time > row.available_time
    assert row.value == Decimal("324.100")


def test_observation_preserves_timezone_aware_input_without_mutating_it() -> None:
    dubai = timezone(timedelta(hours=4))
    available = datetime(2026, 8, 12, 16, 30, tzinfo=dubai)

    row = _valid_observation(
        available_time=available,
        vintage_time=available,
        retrieved_time=datetime(2026, 8, 12, 16, 31, tzinfo=dubai),
    )

    assert row.available_time is available
    assert row.available_time.utcoffset() == timedelta(hours=4)


def test_observation_rejects_unknown_schema() -> None:
    with pytest.raises(EconomicDataError, match="unsupported economic observation schema"):
        _valid_observation(schema_version="economic-observation-v2")


@pytest.mark.parametrize(
    "field",
    ["series_id", "source_id", "unit", "frequency"],
)
def test_observation_rejects_blank_required_identifiers(field: str) -> None:
    with pytest.raises(EconomicDataError, match=field):
        _valid_observation(**{field: "   "})


@pytest.mark.parametrize(
    "field",
    ["observation_time", "available_time", "retrieved_time"],
)
def test_observation_rejects_naive_required_datetime(field: str) -> None:
    with pytest.raises(EconomicChronologyError, match=f"{field} must be timezone-aware"):
        _valid_observation(**{field: datetime(2026, 8, 12, 12, 30)})


def test_observation_rejects_naive_vintage_time() -> None:
    with pytest.raises(EconomicChronologyError, match="vintage_time must be timezone-aware"):
        _valid_observation(vintage_time=datetime(2026, 8, 12, 12, 30))


def test_observation_rejects_value_visible_before_reference_time() -> None:
    with pytest.raises(EconomicChronologyError, match="available_time precedes observation_time"):
        _valid_observation(
            observation_time=datetime(2026, 8, 1, tzinfo=UTC),
            available_time=datetime(2026, 7, 31, 23, 59, tzinfo=UTC),
            vintage_time=None,
            retrieved_time=datetime(2026, 8, 1, tzinfo=UTC),
        )


def test_observation_rejects_retrieval_before_availability() -> None:
    with pytest.raises(EconomicChronologyError, match="retrieved_time precedes available_time"):
        _valid_observation(
            retrieved_time=datetime(2026, 8, 12, 12, 29, tzinfo=UTC),
        )


def test_observation_rejects_vintage_after_retrieval() -> None:
    with pytest.raises(EconomicChronologyError, match="vintage_time exceeds retrieved_time"):
        _valid_observation(
            vintage_time=datetime(2026, 8, 12, 12, 32, tzinfo=UTC),
        )


@pytest.mark.parametrize("value", [Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity")])
def test_observation_rejects_non_finite_value(value: Decimal) -> None:
    with pytest.raises(EconomicDataError, match="value must be finite"):
        _valid_observation(value=value)


@pytest.mark.parametrize("scale", [Decimal("0"), Decimal("NaN"), Decimal("Infinity")])
def test_observation_rejects_invalid_scale(scale: Decimal) -> None:
    with pytest.raises(EconomicDataError, match="scale must be finite and nonzero"):
        _valid_observation(scale=scale)


@pytest.mark.parametrize(
    "digest",
    [
        "",
        "a" * 63,
        "a" * 65,
        "A" * 64,
        "g" * 64,
    ],
)
def test_observation_rejects_malformed_raw_sha256(digest: str) -> None:
    with pytest.raises(EconomicDataError, match="raw_sha256 must be lowercase SHA-256 hex"):
        _valid_observation(raw_sha256=digest)


def test_observation_allows_missing_optional_vintage_and_release_id() -> None:
    row = _valid_observation(vintage_time=None, release_id=None)

    assert row.vintage_time is None
    assert row.release_id is None
