"""Deterministic trailing-only features for candidate-strategy research."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_EVEN, Context, Decimal, localcontext
from enum import StrEnum

from gemini_trading.domain.candle import Candle

_CONTEXT = Context(prec=34, rounding=ROUND_HALF_EVEN)
_ZERO = Decimal("0")
_ONE = Decimal("1")
_TWO = Decimal("2")


class FeatureGroup(StrEnum):
    """Closed feature families used to isolate specialist inputs."""

    RETURN = "return"
    MOMENTUM = "momentum"
    TREND = "trend"
    VOLATILITY = "volatility"
    CANDLE_STRUCTURE = "candle_structure"
    MEAN_REVERSION = "mean_reversion"
    VOLUME = "volume"
    REGIME = "regime"


@dataclass(frozen=True, slots=True)
class FeatureDefinition:
    """One stable point-in-time feature declaration."""

    name: str
    version: str
    group: FeatureGroup
    lookback_candles: int
    parameters: tuple[tuple[str, str], ...] = ()
    data_type: str = "decimal"

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("feature name must not be empty")
        if not self.version.strip():
            raise ValueError("feature version must not be empty")
        if isinstance(self.lookback_candles, bool) or self.lookback_candles < 0:
            raise ValueError("feature lookback must be a non-negative integer")
        if not self.data_type.strip():
            raise ValueError("feature data_type must not be empty")
        parameter_names = tuple(name for name, _ in self.parameters)
        if len(parameter_names) != len(set(parameter_names)):
            raise ValueError("feature parameters must have unique names")
        if any(not name.strip() or not value.strip() for name, value in self.parameters):
            raise ValueError("feature parameters must not contain empty values")


@dataclass(frozen=True, slots=True)
class FeatureRow:
    """One immutable feature vector aligned to one completed candle."""

    candle_index: int
    candle_open_time: datetime
    values: tuple[Decimal, ...]

    def __post_init__(self) -> None:
        if isinstance(self.candle_index, bool) or self.candle_index < 0:
            raise ValueError("candle_index must be a non-negative integer")
        if self.candle_open_time.tzinfo is None or self.candle_open_time.utcoffset() is None:
            raise ValueError("candle_open_time must be timezone-aware")
        if any(not value.is_finite() for value in self.values):
            raise ValueError("feature values must be finite")


@dataclass(frozen=True, slots=True)
class FeatureMatrix:
    """One deterministic matrix with stable column and row alignment."""

    schema_version: str
    definitions: tuple[FeatureDefinition, ...]
    rows: tuple[FeatureRow, ...]

    def __post_init__(self) -> None:
        if not self.schema_version.strip():
            raise ValueError("feature matrix schema_version must not be empty")
        names = tuple(definition.name for definition in self.definitions)
        if len(names) != len(set(names)):
            raise ValueError("feature matrix definitions must have unique names")
        indexes = tuple(row.candle_index for row in self.rows)
        if indexes != tuple(sorted(indexes)) or len(indexes) != len(set(indexes)):
            raise ValueError("feature matrix rows must have unique ordered indexes")
        if any(len(row.values) != len(self.definitions) for row in self.rows):
            raise ValueError("feature row width must match definitions")

    @property
    def feature_names(self) -> tuple[str, ...]:
        """Return stable matrix column names."""

        return tuple(definition.name for definition in self.definitions)

    def row_for(self, candle_index: int) -> FeatureRow:
        """Return one row by exact candle index."""

        for row in self.rows:
            if row.candle_index == candle_index:
                return row
        raise KeyError(f"feature row is unavailable for candle index {candle_index}")

    def value_for(self, candle_index: int, feature_name: str) -> Decimal:
        """Return one exact value by candle index and stable feature name."""

        try:
            column_index = self.feature_names.index(feature_name)
        except ValueError:
            raise KeyError(f"unknown feature name: {feature_name}") from None
        return self.row_for(candle_index).values[column_index]


@dataclass(frozen=True, slots=True)
class FeatureRegistry:
    """Locked feature declarations and deterministic computation policy."""

    schema_version: str
    definitions: tuple[FeatureDefinition, ...]
    trend_feature_names: tuple[str, ...]
    mean_reversion_feature_names: tuple[str, ...]
    regime_feature_names: tuple[str, ...]
    maximum_lookback_candles: int

    def __post_init__(self) -> None:
        if not self.schema_version.strip():
            raise ValueError("feature registry schema_version must not be empty")
        names = self.feature_names
        if len(names) != len(set(names)):
            raise ValueError("feature registry names must be unique")
        registered = set(names)
        for field_name in (
            "trend_feature_names",
            "mean_reversion_feature_names",
            "regime_feature_names",
        ):
            selected = getattr(self, field_name)
            if not selected or not set(selected) < registered:
                raise ValueError(f"{field_name} must be a strict non-empty registry subset")
            if len(selected) != len(set(selected)):
                raise ValueError(f"{field_name} must not contain duplicates")
        if isinstance(self.maximum_lookback_candles, bool) or self.maximum_lookback_candles < 1:
            raise ValueError("maximum_lookback_candles must be positive")
        if any(
            definition.lookback_candles > self.maximum_lookback_candles
            for definition in self.definitions
        ):
            raise ValueError("feature definition exceeds maximum lookback")

    @property
    def feature_names(self) -> tuple[str, ...]:
        """Return stable registry feature names."""

        return tuple(definition.name for definition in self.definitions)

    @classmethod
    def locked_v0_1(cls) -> "FeatureRegistry":
        """Return the predeclared Candidate v0.1 feature registry."""

        definitions: list[FeatureDefinition] = []

        def add(
            name: str,
            group: FeatureGroup,
            lookback: int,
            **parameters: int | str,
        ) -> None:
            definitions.append(
                FeatureDefinition(
                    name=name,
                    version="v1",
                    group=group,
                    lookback_candles=lookback,
                    parameters=tuple(
                        (key, str(value)) for key, value in sorted(parameters.items())
                    ),
                )
            )

        for lag in (1, 2, 3, 6, 12, 24, 42):
            add(f"log_return_{lag}", FeatureGroup.RETURN, lag, lag=lag)
        for window in (6, 12, 24, 42):
            add(
                f"positive_return_fraction_{window}",
                FeatureGroup.MOMENTUM,
                window,
                window=window,
            )
        add(
            "return_acceleration_3_3",
            FeatureGroup.MOMENTUM,
            6,
            current=3,
            previous=3,
        )
        for window in (12, 42):
            add(
                f"distance_from_high_{window}",
                FeatureGroup.MOMENTUM,
                window,
                window=window,
            )
            add(
                f"distance_from_low_{window}",
                FeatureGroup.MOMENTUM,
                window,
                window=window,
            )
        for span in (6, 12, 24, 42):
            add(f"ema_distance_{span}", FeatureGroup.TREND, 42, span=span)
        for fast, slow in ((6, 24), (12, 42), (24, 42)):
            add(
                f"ema_spread_{fast}_{slow}",
                FeatureGroup.TREND,
                42,
                fast=fast,
                slow=slow,
            )
        for span in (6, 12, 24, 42):
            for slope_window in (3, 6):
                add(
                    f"ema_slope_{span}_{slope_window}",
                    FeatureGroup.TREND,
                    42,
                    span=span,
                    slope_window=slope_window,
                )
        for window in (6, 12, 24):
            add(
                f"trend_consistency_{window}",
                FeatureGroup.TREND,
                window,
                window=window,
            )
        for window in (6, 12, 24, 42):
            add(
                f"realized_volatility_{window}",
                FeatureGroup.VOLATILITY,
                window,
                window=window,
            )
        for window in (6, 12, 24):
            add(f"atr_{window}", FeatureGroup.VOLATILITY, window, window=window)
        add(
            "true_range_ratio_24",
            FeatureGroup.VOLATILITY,
            24,
            window=24,
        )
        for name in (
            "candle_body_fraction",
            "upper_wick_fraction",
            "lower_wick_fraction",
            "close_location_current",
        ):
            add(name, FeatureGroup.CANDLE_STRUCTURE, 0)
        for window in (12, 24):
            add(
                f"rolling_close_location_{window}",
                FeatureGroup.CANDLE_STRUCTURE,
                window,
                window=window,
            )
        for window in (12, 24, 42):
            add(
                f"close_zscore_{window}",
                FeatureGroup.MEAN_REVERSION,
                window,
                window=window,
            )
            add(
                f"median_atr_distance_{window}",
                FeatureGroup.MEAN_REVERSION,
                max(window, 24),
                window=window,
                atr_window=24,
            )
            add(
                f"drawdown_from_high_{window}",
                FeatureGroup.MEAN_REVERSION,
                window,
                window=window,
            )
            add(
                f"rebound_from_low_{window}",
                FeatureGroup.MEAN_REVERSION,
                window,
                window=window,
            )
        for lag in (1, 3, 6, 12):
            add(f"log_volume_change_{lag}", FeatureGroup.VOLUME, lag, lag=lag)
        for window in (12, 24, 42):
            add(
                f"median_volume_ratio_{window}",
                FeatureGroup.VOLUME,
                window,
                window=window,
            )
        for window in (24, 42):
            add(
                f"volume_zscore_{window}",
                FeatureGroup.VOLUME,
                window,
                window=window,
            )
        add("signed_volume_proxy", FeatureGroup.VOLUME, 24, volume_window=24)
        add("range_volume_proxy", FeatureGroup.VOLUME, 24, volume_window=24)
        add(
            "trend_strength_12_42_atr24",
            FeatureGroup.REGIME,
            42,
            fast=12,
            slow=42,
            atr_window=24,
        )
        add(
            "volatility_ratio_6_42",
            FeatureGroup.REGIME,
            42,
            fast_window=6,
            slow_window=42,
        )
        add(
            "ema_12_42_sign_streak",
            FeatureGroup.REGIME,
            42,
            fast=12,
            slow=42,
        )

        frozen = tuple(definitions)
        trend_groups = {
            FeatureGroup.RETURN,
            FeatureGroup.MOMENTUM,
            FeatureGroup.TREND,
            FeatureGroup.VOLATILITY,
            FeatureGroup.VOLUME,
        }
        mean_reversion_groups = {
            FeatureGroup.MEAN_REVERSION,
            FeatureGroup.CANDLE_STRUCTURE,
            FeatureGroup.VOLATILITY,
            FeatureGroup.VOLUME,
        }
        regime_names = (
            "trend_strength_12_42_atr24",
            "volatility_ratio_6_42",
            "true_range_ratio_24",
            "ema_12_42_sign_streak",
        )
        return cls(
            schema_version="candidate-feature-registry-v1",
            definitions=frozen,
            trend_feature_names=tuple(
                definition.name for definition in frozen if definition.group in trend_groups
            ),
            mean_reversion_feature_names=tuple(
                definition.name
                for definition in frozen
                if definition.group in mean_reversion_groups
            ),
            regime_feature_names=regime_names,
            maximum_lookback_candles=42,
        )

    def compute(self, candles: tuple[Candle, ...]) -> FeatureMatrix:
        """Compute eligible trailing feature rows without future information."""

        _validate_candles(candles)
        rows: list[FeatureRow] = []
        with localcontext(_CONTEXT):
            for candle_index in range(self.maximum_lookback_candles, len(candles)):
                try:
                    values_by_name = _compute_values(candles, candle_index)
                    values = tuple(values_by_name[name] for name in self.feature_names)
                except _IneligibleFeatureRow:
                    continue
                rows.append(
                    FeatureRow(
                        candle_index=candle_index,
                        candle_open_time=candles[candle_index].open_time,
                        values=values,
                    )
                )
        return FeatureMatrix(
            schema_version="candidate-feature-matrix-v1",
            definitions=self.definitions,
            rows=tuple(rows),
        )


class _IneligibleFeatureRow(Exception):
    """Internal control flow for a row that cannot satisfy the registry."""


def _validate_candles(candles: tuple[Candle, ...]) -> None:
    if not candles:
        return
    first = candles[0]
    prior_open_time: datetime | None = None
    for candle in candles:
        if not candle.completed:
            raise ValueError("feature computation requires completed candles")
        if candle.instrument != first.instrument or candle.timeframe != first.timeframe:
            raise ValueError("feature candles must share instrument and timeframe")
        if prior_open_time is not None and candle.open_time <= prior_open_time:
            raise ValueError("feature candles must be strictly chronological")
        prior_open_time = candle.open_time
        if any(
            not value.is_finite()
            for value in (candle.open, candle.high, candle.low, candle.close, candle.volume)
        ):
            raise ValueError("feature candle values must be finite")
        if candle.close <= 0 or candle.volume <= 0:
            raise ValueError("feature close and volume must be positive")
        if candle.high < max(candle.open, candle.close) or candle.low > min(
            candle.open, candle.close
        ):
            raise ValueError("feature candle OHLC values are inconsistent")


def _compute_values(candles: tuple[Candle, ...], index: int) -> dict[str, Decimal]:
    closes = tuple(candle.close for candle in candles)
    volumes = tuple(candle.volume for candle in candles)
    current = candles[index]
    close = current.close
    local_start = index - 42
    local_closes = closes[local_start : index + 1]
    ema_series = {span: _ema_series(local_closes, span) for span in (6, 12, 24, 42)}
    ema_current = {span: series[-1] for span, series in ema_series.items()}
    true_ranges = {window: _trailing_true_ranges(candles, index, window) for window in (6, 12, 24)}
    atr = {window: _mean(values) for window, values in true_ranges.items()}
    log_returns = {
        window: _trailing_log_returns(closes, index, window) for window in (6, 12, 24, 42)
    }
    realized_volatility = {
        window: _population_std(values) for window, values in log_returns.items()
    }

    values: dict[str, Decimal] = {}
    for lag in (1, 2, 3, 6, 12, 24, 42):
        values[f"log_return_{lag}"] = _log_ratio(close, closes[index - lag])
    for window in (6, 12, 24, 42):
        returns = log_returns[window]
        values[f"positive_return_fraction_{window}"] = Decimal(
            sum(value > 0 for value in returns)
        ) / Decimal(window)
    values["return_acceleration_3_3"] = _log_ratio(close, closes[index - 3]) - _log_ratio(
        closes[index - 3], closes[index - 6]
    )
    for window in (12, 42):
        trailing_closes = closes[index - window + 1 : index + 1]
        trailing_high = max(trailing_closes)
        trailing_low = min(trailing_closes)
        values[f"distance_from_high_{window}"] = _safe_divide(close - trailing_high, trailing_high)
        values[f"distance_from_low_{window}"] = _safe_divide(close - trailing_low, trailing_low)
    for span in (6, 12, 24, 42):
        values[f"ema_distance_{span}"] = _safe_divide(close - ema_current[span], close)
    for fast, slow in ((6, 24), (12, 42), (24, 42)):
        values[f"ema_spread_{fast}_{slow}"] = _safe_divide(
            ema_current[fast] - ema_current[slow], close
        )
    for span in (6, 12, 24, 42):
        for slope_window in (3, 6):
            series = ema_series[span]
            values[f"ema_slope_{span}_{slope_window}"] = _safe_divide(
                series[-1] - series[-1 - slope_window], close
            )
    for window in (6, 12, 24):
        returns = log_returns[window]
        window_direction = _sign(sum(returns, _ZERO))
        if window_direction == 0:
            values[f"trend_consistency_{window}"] = _ZERO
        else:
            matching = sum(_sign(value) == window_direction for value in returns)
            values[f"trend_consistency_{window}"] = Decimal(matching) / Decimal(window)
    for window in (6, 12, 24, 42):
        values[f"realized_volatility_{window}"] = realized_volatility[window]
    for window in (6, 12, 24):
        values[f"atr_{window}"] = atr[window]
    current_true_range = true_ranges[24][-1]
    values["true_range_ratio_24"] = _safe_divide(current_true_range, atr[24])

    candle_range = current.high - current.low
    values["candle_body_fraction"] = _safe_divide(abs(current.close - current.open), candle_range)
    values["upper_wick_fraction"] = _safe_divide(
        current.high - max(current.open, current.close), candle_range
    )
    values["lower_wick_fraction"] = _safe_divide(
        min(current.open, current.close) - current.low, candle_range
    )
    values["close_location_current"] = _safe_divide(current.close - current.low, candle_range)
    for window in (12, 24):
        trailing = candles[index - window + 1 : index + 1]
        high = max(candle.high for candle in trailing)
        low = min(candle.low for candle in trailing)
        values[f"rolling_close_location_{window}"] = _safe_divide(close - low, high - low)

    for window in (12, 24, 42):
        trailing_closes = closes[index - window + 1 : index + 1]
        mean = _mean(trailing_closes)
        standard_deviation = _population_std(trailing_closes)
        median = _median(trailing_closes)
        trailing_high = max(trailing_closes)
        trailing_low = min(trailing_closes)
        values[f"close_zscore_{window}"] = _safe_divide(close - mean, standard_deviation)
        values[f"median_atr_distance_{window}"] = _safe_divide(close - median, atr[24])
        values[f"drawdown_from_high_{window}"] = _safe_divide(trailing_high - close, trailing_high)
        values[f"rebound_from_low_{window}"] = _safe_divide(close - trailing_low, trailing_low)

    for lag in (1, 3, 6, 12):
        values[f"log_volume_change_{lag}"] = _log_ratio(current.volume, volumes[index - lag])
    for window in (12, 24, 42):
        trailing_volumes = volumes[index - window + 1 : index + 1]
        values[f"median_volume_ratio_{window}"] = _safe_divide(
            current.volume, _median(trailing_volumes)
        )
    for window in (24, 42):
        trailing_volumes = volumes[index - window + 1 : index + 1]
        values[f"volume_zscore_{window}"] = _safe_divide(
            current.volume - _mean(trailing_volumes),
            _population_std(trailing_volumes),
        )
    normalized_volume = values["median_volume_ratio_24"]
    one_candle_return = values["log_return_1"]
    values["signed_volume_proxy"] = Decimal(_sign(one_candle_return)) * normalized_volume
    values["range_volume_proxy"] = _safe_divide(current_true_range, close) * normalized_volume
    values["trend_strength_12_42_atr24"] = _safe_divide(
        abs(ema_current[12] - ema_current[42]), atr[24]
    )
    values["volatility_ratio_6_42"] = _safe_divide(realized_volatility[6], realized_volatility[42])
    spread_signs = tuple(
        _sign(fast - slow) for fast, slow in zip(ema_series[12], ema_series[42], strict=True)
    )
    values["ema_12_42_sign_streak"] = Decimal(_trailing_sign_streak(spread_signs))

    if any(not value.is_finite() for value in values.values()):
        raise _IneligibleFeatureRow
    return values


def _ema_series(values: Sequence[Decimal], span: int) -> tuple[Decimal, ...]:
    if not values:
        raise _IneligibleFeatureRow
    alpha = _TWO / Decimal(span + 1)
    complement = _ONE - alpha
    current = values[0]
    result = [current]
    for value in values[1:]:
        current = alpha * value + complement * current
        result.append(current)
    return tuple(result)


def _trailing_log_returns(
    closes: tuple[Decimal, ...], index: int, window: int
) -> tuple[Decimal, ...]:
    return tuple(
        _log_ratio(closes[position], closes[position - 1])
        for position in range(index - window + 1, index + 1)
    )


def _trailing_true_ranges(
    candles: tuple[Candle, ...], index: int, window: int
) -> tuple[Decimal, ...]:
    result: list[Decimal] = []
    for position in range(index - window + 1, index + 1):
        candle = candles[position]
        previous_close = candles[position - 1].close
        result.append(
            max(
                candle.high - candle.low,
                abs(candle.high - previous_close),
                abs(candle.low - previous_close),
            )
        )
    return tuple(result)


def _mean(values: Sequence[Decimal]) -> Decimal:
    if not values:
        raise _IneligibleFeatureRow
    return sum(values, _ZERO) / Decimal(len(values))


def _population_std(values: Sequence[Decimal]) -> Decimal:
    mean = _mean(values)
    variance = sum(((value - mean) ** 2 for value in values), _ZERO) / Decimal(len(values))
    return variance.sqrt()


def _median(values: Sequence[Decimal]) -> Decimal:
    if not values:
        raise _IneligibleFeatureRow
    ordered = sorted(values)
    midpoint = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[midpoint]
    return (ordered[midpoint - 1] + ordered[midpoint]) / _TWO


def _log_ratio(numerator: Decimal, denominator: Decimal) -> Decimal:
    if numerator <= 0 or denominator <= 0:
        raise _IneligibleFeatureRow
    return (numerator / denominator).ln()


def _safe_divide(numerator: Decimal, denominator: Decimal) -> Decimal:
    if denominator == 0:
        raise _IneligibleFeatureRow
    result = numerator / denominator
    if not result.is_finite():
        raise _IneligibleFeatureRow
    return result


def _sign(value: Decimal) -> int:
    if value > 0:
        return 1
    if value < 0:
        return -1
    return 0


def _trailing_sign_streak(signs: Sequence[int]) -> int:
    if not signs or signs[-1] == 0:
        return 0
    current = signs[-1]
    streak = 0
    for sign in reversed(signs):
        if sign != current:
            break
        streak += 1
    return streak
