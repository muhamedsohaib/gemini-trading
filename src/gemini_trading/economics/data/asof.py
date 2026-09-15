"""Point-in-time visibility rules for Economic Data Fabric v1."""

from datetime import UTC, datetime

from gemini_trading.economics.data.dataset import EconomicDataset
from gemini_trading.economics.data.observation import (
    EconomicChronologyError,
    EconomicDataError,
    EconomicObservation,
)
from gemini_trading.economics.data.serialization import observation_identity_key


def _require_aware_cutoff(cutoff: datetime) -> datetime:
    if cutoff.tzinfo is None or cutoff.utcoffset() is None:
        raise EconomicChronologyError("as-of cutoff must be timezone-aware")
    return cutoff.astimezone(UTC)


def _canonical_order(rows: tuple[EconomicObservation, ...]) -> tuple[EconomicObservation, ...]:
    return tuple(
        sorted(
            rows,
            key=lambda row: (*observation_identity_key(row), row.raw_sha256),
        )
    )


def observations_as_of(
    dataset: EconomicDataset,
    cutoff: datetime,
    *,
    series_id: str | None = None,
) -> tuple[EconomicObservation, ...]:
    """Return only observations whose public availability is at or before ``cutoff``."""

    cutoff_utc = _require_aware_cutoff(cutoff)
    visible = tuple(
        row
        for row in dataset.observations
        if row.available_time.astimezone(UTC) <= cutoff_utc
        and (series_id is None or row.series_id == series_id)
    )
    return _canonical_order(visible)


def latest_visible_vintages(
    dataset: EconomicDataset,
    cutoff: datetime,
    *,
    series_id: str | None = None,
) -> tuple[EconomicObservation, ...]:
    """Return the latest unambiguous visible vintage for each series/reference period."""

    visible = observations_as_of(dataset, cutoff, series_id=series_id)
    grouped: dict[tuple[str, datetime], list[EconomicObservation]] = {}
    for row in visible:
        key = (row.series_id, row.observation_time.astimezone(UTC))
        grouped.setdefault(key, []).append(row)

    selected: list[EconomicObservation] = []
    for key in sorted(grouped):
        rows = grouped[key]
        latest_available = max(row.available_time.astimezone(UTC) for row in rows)
        latest = tuple(
            row for row in rows if row.available_time.astimezone(UTC) == latest_available
        )
        if len(latest) != 1:
            raise EconomicDataError(
                "tied visible vintages for economic series/reference period: "
                f"{key[0]} @ {key[1].isoformat()}"
            )
        selected.append(latest[0])

    return _canonical_order(tuple(selected))


__all__ = ["latest_visible_vintages", "observations_as_of"]
