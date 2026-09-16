"""Runtime ancestor availability lineage for derived economic inputs."""

from dataclasses import dataclass
from datetime import UTC, datetime

from gemini_trading.economics.data.observation import EconomicChronologyError


@dataclass(frozen=True, slots=True)
class AvailabilityLineage:
    is_resolved: bool
    max_ancestor_available_time: datetime | None
    unresolved_reasons: tuple[str, ...] = ()

    @classmethod
    def resolved(cls, available_time: datetime) -> "AvailabilityLineage":
        if available_time.tzinfo is None or available_time.utcoffset() is None:
            raise EconomicChronologyError("ancestor available_time must be timezone-aware")
        return cls(True, available_time.astimezone(UTC), ())

    @classmethod
    def unresolved(cls, reason: str) -> "AvailabilityLineage":
        if not reason.strip():
            raise ValueError("unresolved lineage reason must not be blank")
        return cls(False, None, (reason,))


def merge_availability_lineages(*items: AvailabilityLineage) -> AvailabilityLineage:
    if not items:
        raise ValueError("at least one availability lineage is required")
    unresolved = tuple(
        reason for item in items if not item.is_resolved for reason in item.unresolved_reasons
    )
    if unresolved:
        return AvailabilityLineage(False, None, tuple(sorted(set(unresolved))))
    times = tuple(item.max_ancestor_available_time for item in items)
    if any(value is None for value in times):
        return AvailabilityLineage.unresolved("MISSING_EXACT_ANCESTOR_TIME")
    exact = tuple(value for value in times if value is not None)
    return AvailabilityLineage.resolved(max(exact))


def exact_cutoff_admits_lineage(lineage: AvailabilityLineage, cutoff: datetime) -> bool:
    if cutoff.tzinfo is None or cutoff.utcoffset() is None:
        raise EconomicChronologyError("forecast cutoff must be timezone-aware")
    if not lineage.is_resolved or lineage.max_ancestor_available_time is None:
        return False
    return lineage.max_ancestor_available_time <= cutoff.astimezone(UTC)


__all__ = [
    "AvailabilityLineage",
    "exact_cutoff_admits_lineage",
    "merge_availability_lineages",
]
