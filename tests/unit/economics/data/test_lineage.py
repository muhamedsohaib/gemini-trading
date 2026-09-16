from datetime import UTC, datetime, timedelta

from gemini_trading.economics.data.lineage import (
    AvailabilityLineage,
    exact_cutoff_admits_lineage,
    merge_availability_lineages,
)

BASE = datetime(2026, 8, 12, 12, 30, tzinfo=UTC)


def test_merge_propagates_maximum_exact_ancestor_time() -> None:
    left = AvailabilityLineage.resolved(BASE)
    right = AvailabilityLineage.resolved(BASE + timedelta(minutes=5))
    merged = merge_availability_lineages(left, right)
    assert merged.is_resolved is True
    assert merged.max_ancestor_available_time == BASE + timedelta(minutes=5)


def test_unresolved_ancestor_poisoning_is_fail_closed() -> None:
    merged = merge_availability_lineages(
        AvailabilityLineage.resolved(BASE),
        AvailabilityLineage.unresolved("DATE_ONLY"),
    )
    assert merged.is_resolved is False
    assert merged.max_ancestor_available_time is None
    assert exact_cutoff_admits_lineage(merged, BASE + timedelta(days=1)) is False


def test_exact_cutoff_uses_closed_boundary() -> None:
    lineage = AvailabilityLineage.resolved(BASE)
    assert exact_cutoff_admits_lineage(lineage, BASE - timedelta(microseconds=1)) is False
    assert exact_cutoff_admits_lineage(lineage, BASE) is True
