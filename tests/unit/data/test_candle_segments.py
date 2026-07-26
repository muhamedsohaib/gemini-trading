"""Contracts for exact declared gaps and deterministic candle segments."""

from dataclasses import replace
from datetime import timedelta
from pathlib import Path

import pytest

from fixtures.market_data.gapped_btcusdt_4h import CANDLES, REQUEST
from gemini_trading.data.errors import CandleGapError, CandleValidationError
from gemini_trading.data.exchange_closures import (
    ExchangeClosureManifest,
    load_fixed_btcusdt_closure_manifest,
)
from gemini_trading.data.segments import (
    load_candle_segment_manifest,
    segment_number_for_index,
    serialize_candle_segment_manifest,
    validate_and_segment_candle_sequence,
)
from gemini_trading.data.validation.candles import validate_candle_sequence
from gemini_trading.domain.candle import Candle

_PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _manifest() -> ExchangeClosureManifest:
    return load_fixed_btcusdt_closure_manifest(_PROJECT_ROOT)[0]


def _shift_from(index: int, delta: timedelta) -> tuple[Candle, ...]:
    return tuple(
        replace(
            candle,
            open_time=candle.open_time + delta,
            close_time=candle.close_time + delta,
        )
        if candle_index >= index
        else candle
        for candle_index, candle in enumerate(CANDLES)
    )


def test_declared_exchange_closure_produces_two_segments() -> None:
    segments = validate_and_segment_candle_sequence(CANDLES, REQUEST, _manifest())

    assert [(item.start_index, item.end_exclusive) for item in segments.segments] == [
        (0, 3),
        (3, 6),
    ]
    assert segments.segments[0].preceding_closure_id is None
    assert (
        segments.segments[1].preceding_closure_id
        == "binance-spot-system-upgrade-2018-02-08"
    )
    assert segment_number_for_index(segments, 0) == 1
    assert segment_number_for_index(segments, 5) == 2


def test_strict_validation_still_rejects_the_gap() -> None:
    with pytest.raises(CandleGapError, match="timeframe gap"):
        validate_candle_sequence(CANDLES, REQUEST)


def test_shifted_actual_resumption_is_rejected_as_undeclared() -> None:
    shifted = _shift_from(3, timedelta(hours=4))

    with pytest.raises(CandleGapError, match="undeclared timeframe gap"):
        validate_and_segment_candle_sequence(shifted, REQUEST, _manifest())


def test_additional_provider_gap_is_rejected() -> None:
    gapped = tuple(
        replace(
            candle,
            open_time=candle.open_time + timedelta(hours=4),
            close_time=candle.close_time + timedelta(hours=4),
        )
        if index == 5
        else candle
        for index, candle in enumerate(CANDLES)
    )

    with pytest.raises(CandleGapError, match="undeclared timeframe gap"):
        validate_and_segment_candle_sequence(gapped, REQUEST, _manifest())


def test_unused_closure_declaration_is_rejected() -> None:
    continuous = _shift_from(3, -timedelta(hours=28))

    with pytest.raises(CandleValidationError, match="unused"):
        validate_and_segment_candle_sequence(continuous, REQUEST, _manifest())


def test_segment_manifest_round_trips_canonically() -> None:
    segments = validate_and_segment_candle_sequence(CANDLES, REQUEST, _manifest())
    raw = serialize_candle_segment_manifest(segments)

    assert load_candle_segment_manifest(raw) == segments
    assert serialize_candle_segment_manifest(load_candle_segment_manifest(raw)) == raw


def test_segment_manifest_rejects_tampered_segment_number() -> None:
    segments = validate_and_segment_candle_sequence(CANDLES, REQUEST, _manifest())
    raw = serialize_candle_segment_manifest(segments)
    tampered = raw.replace(b'"segment_number":1', b'"segment_number":9')

    with pytest.raises(CandleValidationError, match="segment numbers"):
        load_candle_segment_manifest(tampered)


def test_segment_lookup_rejects_an_index_outside_evidence() -> None:
    segments = validate_and_segment_candle_sequence(CANDLES, REQUEST, _manifest())

    with pytest.raises(CandleValidationError, match="outside"):
        segment_number_for_index(segments, 6)
