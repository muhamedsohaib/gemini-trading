"""Canonical series semantics for Economic Data Fabric v1."""

from decimal import Decimal

import pytest

from gemini_trading.economics.data.series import (
    ECONOMIC_SERIES_SCHEMA_V1,
    EconomicDomain,
    EconomicSeriesDefinition,
    EconomicSeriesRegistry,
    RevisionPolicy,
)


def _definition(
    *,
    series_id: str = "macro.us.cpi.all_items.index",
    title: str = "US CPI All Items",
) -> EconomicSeriesDefinition:
    return EconomicSeriesDefinition(
        schema_version="economic-series-v1",
        series_id=series_id,
        title=title,
        domain=EconomicDomain.MACRO,
        unit="index",
        scale=Decimal("1"),
        frequency="monthly",
        observation_semantics="reference-month start",
        availability_semantics="public release timestamp",
        revision_policy=RevisionPolicy.REVISIONED,
    )


def test_series_schema_and_enum_values_are_frozen() -> None:
    assert ECONOMIC_SERIES_SCHEMA_V1 == "economic-series-v1"
    assert tuple(item.value for item in EconomicDomain) == (
        "MARKET",
        "MACRO",
        "EVENT",
        "ALTERNATIVE",
    )
    assert tuple(item.value for item in RevisionPolicy) == (
        "NONE",
        "REVISIONED",
        "SOURCE_DEPENDENT",
    )


def test_registry_sorts_definitions_by_series_id() -> None:
    macro = _definition(series_id="macro.us.cpi.all_items.index")
    market = EconomicSeriesDefinition(
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
    )

    registry = EconomicSeriesRegistry((macro, market))

    assert tuple(item.series_id for item in registry.definitions) == (
        "macro.us.cpi.all_items.index",
        "market.usd.dxy.index",
    )
    assert registry.by_id(market.series_id) is market


def test_registry_rejects_two_definitions_for_one_series_id() -> None:
    first = _definition()
    second = _definition(title="Conflicting semantic definition")

    with pytest.raises(ValueError, match="duplicate series_id"):
        EconomicSeriesRegistry((first, second))


def test_registry_rejects_empty_registry() -> None:
    with pytest.raises(ValueError, match="at least one"):
        EconomicSeriesRegistry(())


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("series_id", ""),
        ("title", "   "),
        ("unit", ""),
        ("frequency", ""),
        ("observation_semantics", ""),
        ("availability_semantics", ""),
    ],
)
def test_series_definition_rejects_blank_semantics(field: str, value: str) -> None:
    values = {
        "schema_version": "economic-series-v1",
        "series_id": "macro.us.cpi.all_items.index",
        "title": "US CPI All Items",
        "domain": EconomicDomain.MACRO,
        "unit": "index",
        "scale": Decimal("1"),
        "frequency": "monthly",
        "observation_semantics": "reference-month start",
        "availability_semantics": "public release timestamp",
        "revision_policy": RevisionPolicy.REVISIONED,
    }
    values[field] = value

    with pytest.raises(ValueError, match=field):
        EconomicSeriesDefinition(**values)  # type: ignore[arg-type]


def test_series_definition_rejects_unknown_schema() -> None:
    with pytest.raises(ValueError, match="unsupported economic series schema"):
        EconomicSeriesDefinition(
            schema_version="economic-series-v2",
            series_id="macro.us.cpi.all_items.index",
            title="US CPI All Items",
            domain=EconomicDomain.MACRO,
            unit="index",
            scale=Decimal("1"),
            frequency="monthly",
            observation_semantics="reference-month start",
            availability_semantics="public release timestamp",
            revision_policy=RevisionPolicy.REVISIONED,
        )


@pytest.mark.parametrize("scale", [Decimal("0"), Decimal("NaN"), Decimal("Infinity")])
def test_series_definition_rejects_invalid_scale(scale: Decimal) -> None:
    with pytest.raises(ValueError, match="scale must be finite and nonzero"):
        EconomicSeriesDefinition(
            schema_version="economic-series-v1",
            series_id="macro.us.cpi.all_items.index",
            title="US CPI All Items",
            domain=EconomicDomain.MACRO,
            unit="index",
            scale=scale,
            frequency="monthly",
            observation_semantics="reference-month start",
            availability_semantics="public release timestamp",
            revision_policy=RevisionPolicy.REVISIONED,
        )


def test_registry_raises_for_unknown_series() -> None:
    registry = EconomicSeriesRegistry((_definition(),))

    with pytest.raises(KeyError, match="unknown economic series"):
        registry.by_id("macro.unknown")
