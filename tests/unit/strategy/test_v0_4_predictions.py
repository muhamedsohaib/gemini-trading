"""Candidate v0.4 fold-local regime-owned prediction context."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from gemini_trading.domain.candle import Candle
from gemini_trading.domain.instrument import Instrument
from gemini_trading.domain.timeframe import Timeframe
from gemini_trading.strategy.contracts import (
    RegimeState,
    SpecialistKind,
)
from gemini_trading.strategy.features import (
    FeatureDefinition,
    FeatureGroup,
    FeatureMatrix,
    FeatureRegistry,
    FeatureRow,
)
from gemini_trading.strategy.labels import (
    LabelObservation,
    LabelVector,
)
from gemini_trading.strategy.policy import CandidatePolicy
from gemini_trading.strategy.v0_4_context import ContextObservation
from gemini_trading.strategy.v0_4_features import V04FeatureRegistry
from gemini_trading.strategy.v0_4_policy import V04MultiTimeframePolicy
from gemini_trading.strategy.v0_4_predictions import (
    V04PredictionContext,
    fit_v0_4_prediction_context,
)

_INSTRUMENT = Instrument("BTCUSDT", "BTC", "USDT")
_START = datetime(2020, 1, 1, tzinfo=UTC)

_TRAINING = tuple(range(1000, 3000))
_CALIBRATION = tuple(range(3000, 4800))
_PREDICTION = tuple(range(4800, 4816))

_CONTEXT_NAMES = V04MultiTimeframePolicy.locked().context_feature_names


@dataclass(frozen=True, slots=True)
class _Fixture:
    matrix: FeatureMatrix
    labels: LabelVector
    context_join: tuple[ContextObservation | None, ...]
    training_indices: tuple[int, ...]
    calibration_indices: tuple[int, ...]
    prediction_indices: tuple[int, ...]
    trend_training_indices: tuple[int, ...]
    mean_training_indices: tuple[int, ...]
    trend_calibration_indices: tuple[int, ...]
    mean_calibration_indices: tuple[int, ...]


def _decision_group_start(index: int) -> int:
    return index - index % 4


def _is_trend_context(index: int) -> bool:
    group = _decision_group_start(index)

    return 1000 <= group < 2000 or 3000 <= group < 3900 or 4800 <= group < 4808


def _stretch_active(index: int) -> bool:
    if _is_trend_context(index):
        return False

    # Keep more than 800 regime+stretch calibration observations,
    # while proving that RANGING alone is insufficient.
    return index % 20 != 0


def _context_observation(index: int) -> ContextObservation:
    context_number = index // 4 - 1
    context_open = _START + timedelta(hours=4 * context_number)

    constituent_start = context_number * 4
    constituents = (
        constituent_start,
        constituent_start + 1,
        constituent_start + 2,
        constituent_start + 3,
    )

    base = Decimal("10000") + Decimal(context_number)

    candle = Candle(
        instrument=_INSTRUMENT,
        timeframe=Timeframe.H4,
        open_time=context_open,
        close_time=(context_open + timedelta(hours=4) - timedelta(milliseconds=1)),
        open=base,
        high=base + Decimal("10"),
        low=base - Decimal("10"),
        close=base + Decimal("2"),
        volume=Decimal("4000") + Decimal(context_number % 31),
        completed=True,
        source_provider="binance_spot",
    )

    return ContextObservation(
        candle=candle,
        constituent_indices=constituents,
        constituent_sha256=f"{context_number:064x}",
    )


def _context_values(
    index: int,
) -> dict[str, Decimal]:
    context_number = index // 4 - 1

    if _is_trend_context(index):
        signed_spread = Decimal("1.10") + Decimal(context_number % 11) / Decimal("100")
    else:
        signed_spread = Decimal("0.20") + Decimal(context_number % 11) / Decimal("100")

    return {
        _CONTEXT_NAMES[0]: signed_spread,
        _CONTEXT_NAMES[1]: (Decimal("0.90") + Decimal(context_number % 13) / Decimal("100")),
        _CONTEXT_NAMES[2]: (Decimal("1.00") + Decimal(context_number % 7) / Decimal("100")),
        _CONTEXT_NAMES[3]: (Decimal("0.40") + Decimal(context_number % 17) / Decimal("100")),
        _CONTEXT_NAMES[4]: (Decimal("0.10") + Decimal(context_number % 19) / Decimal("100")),
        _CONTEXT_NAMES[5]: (Decimal("0.20") + Decimal(context_number % 23) / Decimal("100")),
    }


def _legacy_value(
    *,
    index: int,
    offset: int,
    column: int,
    name: str,
) -> Decimal:
    value = Decimal(((offset + 1) * (column + 3)) % 997) / Decimal("1000") + Decimal(
        (offset + column) % 19
    ) / Decimal("100")

    # Deliberately make the legacy tactical regime appear UNSTABLE.
    # v0.4 ownership must come from completed 4h context instead.
    if name == "volatility_ratio_6_42":
        return Decimal("1.80") + Decimal(offset % 11) / Decimal("100")

    if name == "true_range_ratio_24":
        return Decimal("1.00") + Decimal(offset % 13) / Decimal("100")

    if name == "trend_strength_12_42_atr24":
        return Decimal("0.20") + Decimal(offset % 17) / Decimal("100")

    if name == "ema_12_42_sign_streak":
        return Decimal(1 + offset % 2)

    if name == "close_zscore_24":
        if not _is_trend_context(index):
            if _stretch_active(index):
                return Decimal("-0.80") - Decimal(offset % 7) / Decimal("100")
            return Decimal("0.10")

        return Decimal("-0.10") + Decimal(offset % 7) / Decimal("100")

    if name == "drawdown_from_high_24":
        if not _is_trend_context(index):
            if _stretch_active(index):
                return Decimal("0.025") + Decimal(offset % 7) / Decimal("1000")
            return Decimal("0.005")

        return Decimal("0.005") + Decimal(offset % 11) / Decimal("1000")

    return value


def _context_definitions() -> tuple[FeatureDefinition, ...]:
    return tuple(
        FeatureDefinition(
            name=name,
            version="v1",
            group=FeatureGroup.TREND,
            lookback_candles=42,
            parameters=(("timeframe", "4h"),),
        )
        for name in _CONTEXT_NAMES
    )


def _fixture() -> _Fixture:
    tactical = FeatureRegistry.locked_v0_1()
    registry = V04FeatureRegistry.locked()

    definitions = (
        *tactical.definitions,
        *_context_definitions(),
    )

    rows: list[FeatureRow] = []
    observations: list[LabelObservation] = []

    first_index = _TRAINING[0]
    final_index = _PREDICTION[-1]

    context_join: list[ContextObservation | None] = [None] * (final_index + 1)

    for index in range(first_index, final_index + 1):
        offset = index - first_index

        tactical_values = tuple(
            _legacy_value(
                index=index,
                offset=offset,
                column=column,
                name=definition.name,
            )
            for column, definition in enumerate(tactical.definitions)
        )

        context_values = _context_values(index)

        rows.append(
            FeatureRow(
                candle_index=index,
                candle_open_time=(_START + timedelta(hours=index)),
                values=(
                    *tactical_values,
                    *(context_values[name] for name in registry.context_feature_names),
                ),
            )
        )

        positive = offset % 2 == 0

        gross_return = (
            Decimal("0.015") + Decimal(offset % 13) / Decimal("10000")
            if positive
            else (Decimal("-0.010") - Decimal(offset % 11) / Decimal("10000"))
        )

        observations.append(
            LabelObservation(
                decision_candle_index=index,
                entry_candle_index=index + 1,
                exit_candle_index=index + 13,
                entry_reference_price=Decimal("100"),
                exit_reference_price=(Decimal("102") if positive else Decimal("98")),
                entry_fill_price=Decimal("100.20"),
                exit_fill_price=(Decimal("101.80") if positive else Decimal("97.80")),
                gross_return=gross_return,
                net_return=(gross_return - Decimal("0.006")),
                hurdle_bps=Decimal("60"),
                positive=positive,
            )
        )

        context_join[index] = _context_observation(index)

    matrix = FeatureMatrix(
        schema_version="candidate-v0.4-feature-matrix-v1",
        definitions=definitions,
        rows=tuple(rows),
    )

    labels = LabelVector(
        schema_version="candidate-label-vector-v1",
        horizon_candles=12,
        hurdle_bps=Decimal("60"),
        observations=tuple(observations),
    )

    # The fixture starts at the first positive-sign 4h
    # context. The inherited regime contract requires three
    # distinct same-sign completed 4h contexts before TRENDING,
    # so the first two contexts (8 tactical rows) remain
    # INDETERMINATE.
    first_trend_group = _decision_group_start(_TRAINING[0])

    trend_training = tuple(
        index
        for index in _TRAINING
        if (_is_trend_context(index) and _decision_group_start(index) >= first_trend_group + 8)
    )

    mean_training = tuple(
        index for index in _TRAINING if (not _is_trend_context(index) and _stretch_active(index))
    )

    trend_calibration = tuple(index for index in _CALIBRATION if _is_trend_context(index))

    mean_calibration = tuple(
        index for index in _CALIBRATION if (not _is_trend_context(index) and _stretch_active(index))
    )

    return _Fixture(
        matrix=matrix,
        labels=labels,
        context_join=tuple(context_join),
        training_indices=_TRAINING,
        calibration_indices=_CALIBRATION,
        prediction_indices=_PREDICTION,
        trend_training_indices=trend_training,
        mean_training_indices=mean_training,
        trend_calibration_indices=trend_calibration,
        mean_calibration_indices=mean_calibration,
    )


@pytest.fixture(scope="module")
def fold_fixture() -> _Fixture:
    return _fixture()


@pytest.fixture(scope="module")
def prediction_context(
    fold_fixture: _Fixture,
) -> V04PredictionContext:
    return fit_v0_4_prediction_context(
        fold_number=4,
        matrix=fold_fixture.matrix,
        labels=fold_fixture.labels,
        context_join=fold_fixture.context_join,
        policy=CandidatePolicy.locked_v0_4(),
        training_indices=fold_fixture.training_indices,
        calibration_indices=fold_fixture.calibration_indices,
        prediction_indices=fold_fixture.prediction_indices,
    )


def test_trend_v0_4_fit_consumes_only_4h_trending_training_rows(
    prediction_context: V04PredictionContext,
    fold_fixture: _Fixture,
) -> None:
    assert prediction_context.trend_training_indices == fold_fixture.trend_training_indices

    # If the implementation accidentally uses the old 1h regime
    # columns, every one of these rows would be UNSTABLE.
    assert all(
        fold_fixture.matrix.value_for(
            index,
            "volatility_ratio_6_42",
        )
        >= Decimal("1.75")
        for index in prediction_context.trend_training_indices
    )


def test_mean_reversion_v0_4_fit_consumes_only_4h_ranging_stretch_rows(
    prediction_context: V04PredictionContext,
    fold_fixture: _Fixture,
) -> None:
    assert prediction_context.mean_reversion_training_indices == fold_fixture.mean_training_indices

    assert all(
        _stretch_active(index) for index in prediction_context.mean_reversion_training_indices
    )


def test_v0_4_calibration_and_return_maps_use_same_regime_domains(
    prediction_context: V04PredictionContext,
    fold_fixture: _Fixture,
) -> None:
    assert prediction_context.trend_calibration_indices == fold_fixture.trend_calibration_indices
    assert (
        prediction_context.mean_reversion_calibration_indices
        == fold_fixture.mean_calibration_indices
    )

    assert prediction_context.trend_platt.observation_count == len(
        fold_fixture.trend_calibration_indices
    )
    assert prediction_context.mean_reversion_platt.observation_count == len(
        fold_fixture.mean_calibration_indices
    )

    assert prediction_context.trend_return_map.observation_count == len(
        fold_fixture.trend_calibration_indices
    )
    assert prediction_context.mean_reversion_return_map.observation_count == len(
        fold_fixture.mean_calibration_indices
    )

    assert (
        prediction_context.trend_platt.observation_count
        >= CandidatePolicy.locked_v0_4().calibration_minimum_observations
    )
    assert (
        prediction_context.mean_reversion_platt.observation_count
        >= CandidatePolicy.locked_v0_4().calibration_minimum_observations
    )


def test_v0_4_primary_and_sensitivity_thresholds_bind_exact_domains(
    prediction_context: V04PredictionContext,
    fold_fixture: _Fixture,
) -> None:
    assert set(prediction_context.primary_thresholds) == {
        SpecialistKind.TREND,
        SpecialistKind.MEAN_REVERSION,
    }

    trend_primary = prediction_context.primary_thresholds[SpecialistKind.TREND]
    mean_primary = prediction_context.primary_thresholds[SpecialistKind.MEAN_REVERSION]

    assert trend_primary.percentile == Decimal("0.75")
    assert mean_primary.percentile == Decimal("0.75")

    assert trend_primary.eligible_indices == fold_fixture.trend_calibration_indices
    assert mean_primary.eligible_indices == fold_fixture.mean_calibration_indices

    assert set(prediction_context.sensitivity_thresholds) == {
        (SpecialistKind.TREND, Decimal("0.70")),
        (SpecialistKind.TREND, Decimal("0.80")),
        (
            SpecialistKind.MEAN_REVERSION,
            Decimal("0.70"),
        ),
        (
            SpecialistKind.MEAN_REVERSION,
            Decimal("0.80"),
        ),
    }


def test_v0_4_prediction_rows_persist_tactical_and_context_identity(
    prediction_context: V04PredictionContext,
    fold_fixture: _Fixture,
) -> None:
    assert (
        tuple(item.candle_index for item in prediction_context.predictions)
        == fold_fixture.prediction_indices
    )

    for item in prediction_context.predictions:
        row = fold_fixture.matrix.row_for(item.candle_index)
        observation = fold_fixture.context_join[item.candle_index]

        assert observation is not None

        assert item.tactical_open_time == row.candle_open_time
        assert item.context_sha256 == observation.constituent_sha256
        assert item.context_close_time == observation.candle.close_time

        expected_regime = (
            RegimeState.TRENDING if _is_trend_context(item.candle_index) else RegimeState.RANGING
        )
        assert item.regime.state is expected_regime

        expected_owner = (
            SpecialistKind.TREND
            if expected_regime is RegimeState.TRENDING
            else SpecialistKind.MEAN_REVERSION
        )
        assert item.eligible_specialist is expected_owner

        assert math.isfinite(item.trend_raw)
        assert math.isfinite(item.mean_reversion_raw)

        for probability in (
            item.trend_probability,
            item.mean_reversion_probability,
        ):
            assert probability.is_finite()
            assert Decimal("0") <= probability <= Decimal("1")

        assert item.trend_expected_return.is_finite()
        assert item.mean_reversion_expected_return.is_finite()


def test_v0_4_prediction_context_is_deterministic(
    prediction_context: V04PredictionContext,
    fold_fixture: _Fixture,
) -> None:
    replayed = fit_v0_4_prediction_context(
        fold_number=4,
        matrix=fold_fixture.matrix,
        labels=fold_fixture.labels,
        context_join=fold_fixture.context_join,
        policy=CandidatePolicy.locked_v0_4(),
        training_indices=fold_fixture.training_indices,
        calibration_indices=fold_fixture.calibration_indices,
        prediction_indices=fold_fixture.prediction_indices,
    )

    assert replayed == prediction_context


def test_v0_4_trending_requires_three_distinct_completed_context_signs(
    fold_fixture: _Fixture,
) -> None:
    from dataclasses import replace

    context_column = fold_fixture.matrix.feature_names.index(_CONTEXT_NAMES[0])

    mutated_rows: list[FeatureRow] = []

    for row in fold_fixture.matrix.rows:
        values = list(row.values)

        # The immediately preceding completed 4h context has the
        # opposite EMA12/42 spread sign. This must reset the
        # context sign streak.
        if 4796 <= row.candle_index < 4800:
            values[context_column] = Decimal("-0.20")

        # Then supply three consecutive distinct completed 4h
        # contexts with qualifying positive trend strength.
        elif 4800 <= row.candle_index < 4812:
            values[context_column] = Decimal("1.10")

        mutated_rows.append(
            replace(
                row,
                values=tuple(values),
            )
        )

    mutated_matrix = replace(
        fold_fixture.matrix,
        rows=tuple(mutated_rows),
    )

    context = fit_v0_4_prediction_context(
        fold_number=4,
        matrix=mutated_matrix,
        labels=fold_fixture.labels,
        context_join=fold_fixture.context_join,
        policy=CandidatePolicy.locked_v0_4(),
        training_indices=fold_fixture.training_indices,
        calibration_indices=fold_fixture.calibration_indices,
        prediction_indices=fold_fixture.prediction_indices,
    )

    by_index = {item.candle_index: item for item in context.predictions}

    first = by_index[4800]
    repeated_first = by_index[4803]
    second = by_index[4804]
    third = by_index[4808]

    # Repeated tactical 1h rows joined to the same 4h context
    # must not increment a 4h regime streak.
    assert first.regime.sign_streak == 1
    assert repeated_first.regime.sign_streak == 1
    assert second.regime.sign_streak == 2
    assert third.regime.sign_streak == 3

    assert first.regime.state is RegimeState.INDETERMINATE
    assert repeated_first.regime.state is RegimeState.INDETERMINATE
    assert second.regime.state is RegimeState.INDETERMINATE
    assert third.regime.state is RegimeState.TRENDING
