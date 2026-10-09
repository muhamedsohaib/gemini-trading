"""Deterministic completed four-hour context for Candidate v0.4."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import timedelta

from gemini_trading.domain.candle import Candle
from gemini_trading.domain.instrument import Instrument
from gemini_trading.domain.timeframe import Timeframe
from gemini_trading.research.serialization import canonical_json_bytes


@dataclass(frozen=True, slots=True)
class DerivedContextBar:
    """One completed 4h bar derived from exactly four canonical 1h candles."""

    candle: Candle
    constituent_indices: tuple[int, int, int, int]
    constituent_sha256: str


@dataclass(frozen=True, slots=True)
class ContextObservation:
    """Point-in-time context evidence visible to one tactical decision row."""

    candle: Candle
    constituent_indices: tuple[int, int, int, int]
    constituent_sha256: str

    @classmethod
    def from_bar(cls, bar: DerivedContextBar) -> ContextObservation:
        return cls(
            candle=bar.candle,
            constituent_indices=bar.constituent_indices,
            constituent_sha256=bar.constituent_sha256,
        )


def _validate_hourly_candles(candles: tuple[Candle, ...]) -> None:
    if not candles:
        return

    expected_instrument = candles[0].instrument
    expected_provider = candles[0].source_provider

    previous_open = candles[0].open_time
    for index, candle in enumerate(candles):
        if candle.instrument != expected_instrument:
            raise ValueError("Candidate v0.4 context candles must use one instrument")
        if candle.timeframe is not Timeframe.H1:
            raise ValueError("Candidate v0.4 context requires 1h candles")
        if candle.source_provider != expected_provider:
            raise ValueError("Candidate v0.4 context candles must use one source provider")

        if index > 0 and candle.open_time <= previous_open:
            raise ValueError("Candidate v0.4 context candle opens must be strictly increasing")
        previous_open = candle.open_time


def _validate_segment_boundaries(
    segment_boundaries: tuple[int, ...],
    candle_count: int,
) -> frozenset[int]:
    if segment_boundaries != tuple(sorted(set(segment_boundaries))):
        raise ValueError("Candidate v0.4 segment boundaries must be sorted and unique")

    for boundary in segment_boundaries:
        if isinstance(boundary, bool) or boundary < 1 or boundary >= candle_count:
            raise ValueError("Candidate v0.4 segment boundary is outside the candle sequence")

    return frozenset(segment_boundaries)


def _utc_four_hour_aligned(candle: Candle) -> bool:
    open_time = candle.open_time
    return (
        open_time.hour % 4 == 0
        and open_time.minute == 0
        and open_time.second == 0
        and open_time.microsecond == 0
    )


def _crosses_segment_boundary(
    indices: tuple[int, int, int, int],
    segment_boundaries: frozenset[int],
) -> bool:
    return any(boundary in indices[1:] for boundary in segment_boundaries)


def _valid_group(
    indices: tuple[int, int, int, int],
    candles: tuple[Candle, ...],
    segment_boundaries: frozenset[int],
) -> bool:
    first = candles[indices[0]]

    if not _utc_four_hour_aligned(first):
        return False

    if _crosses_segment_boundary(indices, segment_boundaries):
        return False

    if not all(candles[index].completed for index in indices):
        return False

    for offset in range(3):
        current = candles[indices[offset]]
        following = candles[indices[offset + 1]]
        if current.open_time + timedelta(hours=1) != following.open_time:
            return False

    return True


def _constituent_sha256(
    candles: tuple[Candle, ...],
    indices: tuple[int, int, int, int],
) -> str:
    payload: dict[str, object] = {
        "constituents": [
            {
                "index": index,
                "open_time": candles[index].open_time,
                "open": candles[index].open,
                "high": candles[index].high,
                "low": candles[index].low,
                "close": candles[index].close,
                "volume": candles[index].volume,
            }
            for index in indices
        ]
    }
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def _aggregate_group(
    candles: tuple[Candle, ...],
    indices: tuple[int, int, int, int],
) -> DerivedContextBar:
    constituents = tuple(candles[index] for index in indices)
    first = constituents[0]
    last = constituents[-1]

    candle = Candle(
        instrument=first.instrument,
        timeframe=Timeframe.H4,
        open_time=first.open_time,
        close_time=last.close_time,
        open=first.open,
        high=max(item.high for item in constituents),
        low=min(item.low for item in constituents),
        close=last.close,
        volume=sum((item.volume for item in constituents), start=first.volume * 0),
        completed=True,
        source_provider=first.source_provider,
    )

    return DerivedContextBar(
        candle=candle,
        constituent_indices=indices,
        constituent_sha256=_constituent_sha256(candles, indices),
    )


def derive_v0_4_context_bars(
    candles: tuple[Candle, ...],
    segment_boundaries: tuple[int, ...],
) -> tuple[DerivedContextBar, ...]:
    """Derive valid completed UTC-aligned 4h bars without crossing segments."""

    _validate_hourly_candles(candles)
    boundaries = _validate_segment_boundaries(segment_boundaries, len(candles))

    result: list[DerivedContextBar] = []
    for start in range(len(candles)):
        if start + 3 >= len(candles):
            break

        indices = (start, start + 1, start + 2, start + 3)
        if not _valid_group(indices, candles, boundaries):
            continue

        result.append(_aggregate_group(candles, indices))

    return tuple(result)


def _validate_context_bars(
    context_bars: tuple[DerivedContextBar, ...],
    *,
    expected_instrument: Instrument | None,
) -> None:
    previous_close = None

    for bar in context_bars:
        if bar.candle.timeframe is not Timeframe.H4:
            raise ValueError("Candidate v0.4 context join requires 4h context bars")
        if not bar.candle.completed:
            raise ValueError("Candidate v0.4 context join requires completed context bars")
        if expected_instrument is not None and bar.candle.instrument != expected_instrument:
            raise ValueError("Candidate v0.4 context instrument mismatch")
        if previous_close is not None and bar.candle.close_time <= previous_close:
            raise ValueError("Candidate v0.4 context bars must be strictly increasing")
        previous_close = bar.candle.close_time


def join_v0_4_context(
    candles: tuple[Candle, ...],
    context_bars: tuple[DerivedContextBar, ...],
) -> tuple[ContextObservation | None, ...]:
    """Join only context already completed at each tactical candle open."""

    _validate_hourly_candles(candles)
    expected_instrument = candles[0].instrument if candles else None
    _validate_context_bars(
        context_bars,
        expected_instrument=expected_instrument,
    )

    result: list[ContextObservation | None] = []
    cursor = -1

    for candle in candles:
        decision_time = candle.open_time

        while (
            cursor + 1 < len(context_bars)
            and context_bars[cursor + 1].candle.close_time <= decision_time
        ):
            cursor += 1

        if cursor < 0:
            result.append(None)
        else:
            result.append(ContextObservation.from_bar(context_bars[cursor]))

    return tuple(result)


__all__ = [
    "ContextObservation",
    "DerivedContextBar",
    "derive_v0_4_context_bars",
    "join_v0_4_context",
]
