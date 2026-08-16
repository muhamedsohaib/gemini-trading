"""Hierarchical tactical + completed-context features for Candidate v0.4."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Context, Decimal, localcontext

from gemini_trading.data.segments import CandleSegmentManifest
from gemini_trading.domain.candle import Candle
from gemini_trading.domain.timeframe import Timeframe
from gemini_trading.strategy.features import (
    FeatureDefinition,
    FeatureGroup,
    FeatureMatrix,
    FeatureRegistry,
    FeatureRow,
    compute_price_feature_basis,
)
from gemini_trading.strategy.v0_4_context import ContextObservation
from gemini_trading.strategy.v0_4_policy import V04MultiTimeframePolicy

_DECIMAL_CONTEXT = Context(prec=34, rounding=ROUND_HALF_EVEN)
_ZERO = Decimal("0")


@dataclass(frozen=True, slots=True)
class V04FeatureRegistry:
    """Locked Candidate v0.4 specialist input names."""

    trend_feature_names: tuple[str, ...]
    mean_reversion_feature_names: tuple[str, ...]
    context_feature_names: tuple[str, ...]

    def __post_init__(self) -> None:
        expected_context = V04MultiTimeframePolicy.locked().context_feature_names

        if self.context_feature_names != expected_context:
            raise ValueError("Candidate v0.4 context feature names are not exact")

        if len(self.context_feature_names) != 6:
            raise ValueError("Candidate v0.4 requires exactly six context features")

        if self.trend_feature_names[-6:] != self.context_feature_names:
            raise ValueError("trend specialist must append the exact context features")

        if self.mean_reversion_feature_names[-6:] != self.context_feature_names:
            raise ValueError("mean-reversion specialist must append the exact context features")

        for names in (
            self.trend_feature_names,
            self.mean_reversion_feature_names,
            self.context_feature_names,
        ):
            if len(names) != len(set(names)):
                raise ValueError("Candidate v0.4 feature names must be unique")

    @classmethod
    def locked(cls) -> V04FeatureRegistry:
        """Return the exact preregistered Candidate v0.4 feature surface."""

        tactical = FeatureRegistry.locked_v0_1()
        context = V04MultiTimeframePolicy.locked().context_feature_names

        return cls(
            trend_feature_names=(
                *tactical.trend_feature_names,
                *context,
            ),
            mean_reversion_feature_names=(
                *tactical.mean_reversion_feature_names,
                *context,
            ),
            context_feature_names=context,
        )


def _context_definitions() -> tuple[FeatureDefinition, ...]:
    names = V04MultiTimeframePolicy.locked().context_feature_names
    groups = (
        FeatureGroup.TREND,
        FeatureGroup.VOLATILITY,
        FeatureGroup.VOLATILITY,
        FeatureGroup.CANDLE_STRUCTURE,
        FeatureGroup.MEAN_REVERSION,
        FeatureGroup.TREND,
    )

    return tuple(
        FeatureDefinition(
            name=name,
            version="v1",
            group=group,
            lookback_candles=42,
            parameters=(("timeframe", "4h"),),
        )
        for name, group in zip(names, groups, strict=True)
    )


def _validate_inputs(
    candles: tuple[Candle, ...],
    context_join: tuple[ContextObservation | None, ...],
) -> None:
    if len(context_join) != len(candles):
        raise ValueError("Candidate v0.4 context join length must match candles")

    for index, candle in enumerate(candles):
        if candle.timeframe is not Timeframe.H1:
            raise ValueError("Candidate v0.4 tactical features require 1h candles")

        observation = context_join[index]
        if observation is None:
            continue

        if observation.candle.timeframe is not Timeframe.H4:
            raise ValueError("Candidate v0.4 context observations must be 4h")
        if not observation.candle.completed:
            raise ValueError("Candidate v0.4 context observations must be completed")
        if observation.candle.instrument != candle.instrument:
            raise ValueError("Candidate v0.4 tactical/context instrument mismatch")
        if observation.candle.close_time > candle.open_time:
            raise ValueError("Candidate v0.4 context observation is from the future")

        indices = observation.constituent_indices
        if tuple(sorted(indices)) != indices or len(set(indices)) != 4:
            raise ValueError("Candidate v0.4 context constituent indices are invalid")
        if any(item < 0 or item >= len(candles) for item in indices):
            raise ValueError("Candidate v0.4 context constituent index is outside candles")
        if indices[-1] >= index:
            raise ValueError("Candidate v0.4 context contains future hourly evidence")


def _source_segment_position(
    observation: ContextObservation,
    segments: CandleSegmentManifest,
) -> int:
    first_index = observation.constituent_indices[0]
    last_index = observation.constituent_indices[-1]

    matches = tuple(
        position
        for position, segment in enumerate(segments.segments)
        if segment.start_index <= first_index and last_index < segment.end_exclusive
    )

    if len(matches) != 1:
        raise ValueError(
            "Candidate v0.4 context constituents do not belong to one verified segment"
        )

    return matches[0]


def _context_groups(
    context_join: tuple[ContextObservation | None, ...],
    segments: CandleSegmentManifest,
) -> tuple[tuple[ContextObservation, ...], ...]:
    """Return unique context bars grouped by their verified hourly segment."""

    groups: list[list[ContextObservation]] = []
    seen: dict[str, ContextObservation] = {}
    current_segment_position: int | None = None

    for observation in context_join:
        if observation is None:
            continue

        previous = seen.get(observation.constituent_sha256)
        if previous is not None:
            if previous != observation:
                raise ValueError("Candidate v0.4 context digest identity is inconsistent")
            continue

        source_position = _source_segment_position(observation, segments)

        if current_segment_position is not None and source_position < current_segment_position:
            raise ValueError("Candidate v0.4 context segments are out of order")

        if source_position != current_segment_position:
            groups.append([])
            current_segment_position = source_position
        elif groups[-1]:
            expected_open = groups[-1][-1].candle.open_time + Timeframe.H4.duration
            if observation.candle.open_time != expected_open:
                raise ValueError(
                    "Candidate v0.4 context is discontinuous inside a verified segment"
                )

        groups[-1].append(observation)
        seen[observation.constituent_sha256] = observation

    return tuple(tuple(group) for group in groups)


def _signed_spread(
    ema_spread_close: Decimal,
    trend_strength: Decimal,
) -> Decimal:
    if ema_spread_close > _ZERO:
        return trend_strength
    if ema_spread_close < _ZERO:
        return -trend_strength
    return _ZERO


def _context_values(
    basis: dict[str, Decimal],
    candle: Candle,
) -> tuple[Decimal, Decimal, Decimal, Decimal, Decimal, Decimal]:
    """Build the six exact v0.4 context values from established price math."""

    atr24 = basis["atr_24"]
    ema_spread_close = basis["ema_spread_12_42"]
    trend_strength = basis["trend_strength_12_42_atr24"]

    with localcontext(_DECIMAL_CONTEXT):
        ema12_slope = basis["ema_slope_12_3"] * candle.close / atr24

    return (
        _signed_spread(
            ema_spread_close,
            trend_strength,
        ),
        basis["volatility_ratio_6_42"],
        basis["true_range_ratio_24"],
        basis["rolling_close_location_24"],
        basis["median_atr_distance_24"],
        ema12_slope,
    )


def _context_values_by_digest(
    context_join: tuple[ContextObservation | None, ...],
    segments: CandleSegmentManifest,
) -> dict[str, tuple[Decimal, Decimal, Decimal, Decimal, Decimal, Decimal]]:
    """Compute context independently inside every verified continuous segment."""

    result: dict[
        str,
        tuple[Decimal, Decimal, Decimal, Decimal, Decimal, Decimal],
    ] = {}

    for group in _context_groups(
        context_join,
        segments,
    ):
        context_candles = tuple(observation.candle for observation in group)

        for local_index, observation in enumerate(group):
            if local_index < 42:
                continue

            basis = compute_price_feature_basis(
                context_candles,
                local_index,
            )
            if basis is None:
                # One of the six required price-context calculations
                # has insufficient history or a zero denominator.
                continue

            result[observation.constituent_sha256] = _context_values(
                basis,
                observation.candle,
            )

    return result


def build_v0_4_feature_matrix(
    candles: tuple[Candle, ...],
    segment_manifest: CandleSegmentManifest,
    context_join: tuple[ContextObservation | None, ...],
) -> FeatureMatrix:
    """Build exact 1h tactical features plus six completed-4h context columns."""

    _validate_inputs(candles, context_join)

    tactical_registry = FeatureRegistry.locked_v0_1()
    tactical_matrix = tactical_registry.compute(
        candles,
        segments=segment_manifest,
    )

    context_values = _context_values_by_digest(
        context_join,
        segment_manifest,
    )

    rows: list[FeatureRow] = []
    for tactical_row in tactical_matrix.rows:
        observation = context_join[tactical_row.candle_index]
        if observation is None:
            continue

        appended = context_values.get(observation.constituent_sha256)
        if appended is None:
            # Insufficient completed 4h history or a zero denominator:
            # this tactical observation is ineligible. Never impute.
            continue

        rows.append(
            FeatureRow(
                candle_index=tactical_row.candle_index,
                candle_open_time=tactical_row.candle_open_time,
                values=(
                    *tactical_row.values,
                    *appended,
                ),
            )
        )

    return FeatureMatrix(
        schema_version="candidate-v0.4-feature-matrix-v1",
        definitions=(
            *tactical_matrix.definitions,
            *_context_definitions(),
        ),
        rows=tuple(rows),
    )


__all__ = [
    "V04FeatureRegistry",
    "build_v0_4_feature_matrix",
]
