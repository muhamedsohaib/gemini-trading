"""Provider-neutral semantic definitions for economic series."""

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Final

ECONOMIC_SERIES_SCHEMA_V1: Final[str] = "economic-series-v1"


class EconomicDomain(StrEnum):
    """Closed v1 evidence domains."""

    MARKET = "MARKET"
    MACRO = "MACRO"
    EVENT = "EVENT"
    ALTERNATIVE = "ALTERNATIVE"


class RevisionPolicy(StrEnum):
    """Whether observations for a series can be revised."""

    NONE = "NONE"
    REVISIONED = "REVISIONED"
    SOURCE_DEPENDENT = "SOURCE_DEPENDENT"


@dataclass(frozen=True, slots=True)
class EconomicSeriesDefinition:
    """Stable semantic meaning for one canonical economic series identifier."""

    schema_version: str
    series_id: str
    title: str
    domain: EconomicDomain
    unit: str
    scale: Decimal
    frequency: str
    observation_semantics: str
    availability_semantics: str
    revision_policy: RevisionPolicy

    def __post_init__(self) -> None:
        if self.schema_version != ECONOMIC_SERIES_SCHEMA_V1:
            raise ValueError("unsupported economic series schema")
        for name, value in (
            ("series_id", self.series_id),
            ("title", self.title),
            ("unit", self.unit),
            ("frequency", self.frequency),
            ("observation_semantics", self.observation_semantics),
            ("availability_semantics", self.availability_semantics),
        ):
            if not value.strip():
                raise ValueError(f"{name} must not be empty")
        if not self.scale.is_finite() or self.scale == 0:
            raise ValueError("scale must be finite and nonzero")


@dataclass(frozen=True, slots=True, init=False)
class EconomicSeriesRegistry:
    """Canonical sorted registry of unique economic series definitions."""

    definitions: tuple[EconomicSeriesDefinition, ...]

    def __init__(self, definitions: tuple[EconomicSeriesDefinition, ...]) -> None:
        if not definitions:
            raise ValueError("economic series registry requires at least one definition")
        ordered = tuple(sorted(definitions, key=lambda item: item.series_id))
        identifiers = tuple(item.series_id for item in ordered)
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("duplicate series_id in economic series registry")
        object.__setattr__(self, "definitions", ordered)

    def by_id(self, series_id: str) -> EconomicSeriesDefinition:
        """Return the exact registered definition for ``series_id``."""

        for definition in self.definitions:
            if definition.series_id == series_id:
                return definition
        raise KeyError(f"unknown economic series: {series_id}")
