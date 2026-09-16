"""Point-in-time visibility for Economic Data Fabric v2."""

from collections.abc import Iterable
from datetime import UTC, date, datetime
from typing import Protocol

from gemini_trading.economics.data.availability import AvailabilityPrecision
from gemini_trading.economics.data.observation import EconomicChronologyError, EconomicDataError
from gemini_trading.economics.data.observation_v2 import EconomicObservationV2

_EXACT = {
    AvailabilityPrecision.EXACT_SECOND,
    AvailabilityPrecision.EXACT_MINUTE,
    AvailabilityPrecision.EXACT_HOUR,
}


class _ObservationDataset(Protocol):
    observations: tuple[EconomicObservationV2, ...]


def _aware_utc(cutoff: datetime) -> datetime:
    if cutoff.tzinfo is None or cutoff.utcoffset() is None:
        raise EconomicChronologyError("as-of cutoff must be timezone-aware")
    return cutoff.astimezone(UTC)


def _ordered(rows: Iterable[EconomicObservationV2]) -> tuple[EconomicObservationV2, ...]:
    return tuple(
        sorted(
            rows,
            key=lambda row: (
                row.series_id,
                row.reference_period_start,
                row.reference_period_end,
                row.version_id,
            ),
        )
    )


def observations_as_of_v2(
    dataset: _ObservationDataset,
    cutoff: datetime,
    *,
    series_id: str | None = None,
) -> tuple[EconomicObservationV2, ...]:
    """Return rows supported by exact availability at or before ``cutoff``."""

    cutoff_utc = _aware_utc(cutoff)
    visible = (
        row
        for row in dataset.observations
        if row.availability_precision in _EXACT
        and row.available_time is not None
        and row.available_time.astimezone(UTC) <= cutoff_utc
        and (series_id is None or row.series_id == series_id)
    )
    return _ordered(visible)


def observations_as_of_date_v2(
    dataset: _ObservationDataset,
    cutoff_date: date,
    *,
    series_id: str | None = None,
) -> tuple[EconomicObservationV2, ...]:
    """Return rows definitely available before the start of ``cutoff_date``."""

    visible: list[EconomicObservationV2] = []
    for row in dataset.observations:
        if series_id is not None and row.series_id != series_id:
            continue
        if row.availability_precision is AvailabilityPrecision.DATE_ONLY:
            if row.available_date is not None and row.available_date < cutoff_date:
                visible.append(row)
            continue
        if (
            row.availability_precision in _EXACT
            and row.available_time is not None
            and row.available_time.astimezone(UTC).date() < cutoff_date
        ):
            visible.append(row)
    return _ordered(visible)


def latest_visible_vintages_v2(
    dataset: _ObservationDataset,
    cutoff: datetime,
    *,
    series_id: str | None = None,
) -> tuple[EconomicObservationV2, ...]:
    """Return latest unambiguous exact vintage per series/reference interval."""

    visible = observations_as_of_v2(dataset, cutoff, series_id=series_id)
    grouped: dict[tuple[str, date, date], list[EconomicObservationV2]] = {}
    for row in visible:
        key = (row.series_id, row.reference_period_start, row.reference_period_end)
        grouped.setdefault(key, []).append(row)

    selected: list[EconomicObservationV2] = []
    for key in sorted(grouped):
        rows = grouped[key]
        latest_time = max(row.available_time.astimezone(UTC) for row in rows if row.available_time)
        latest = tuple(
            row
            for row in rows
            if row.available_time is not None and row.available_time.astimezone(UTC) == latest_time
        )
        if len(latest) != 1:
            raise EconomicDataError(
                "tied visible vintages for economic series/reference period: "
                f"{key[0]} @ {key[1].isoformat()}..{key[2].isoformat()}"
            )
        selected.append(latest[0])
    return _ordered(selected)


__all__ = [
    "latest_visible_vintages_v2",
    "observations_as_of_date_v2",
    "observations_as_of_v2",
]
