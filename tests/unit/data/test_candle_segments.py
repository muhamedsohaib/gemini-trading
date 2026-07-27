"""Contracts for exact declared gaps and deterministic candle segments."""

from dataclasses import replace
from datetime import timedelta

import pytest

from fixtures.market_data.multi_closure_btcusdt_4h import (
    CANDLES,
    EXPECTED_BOUNDARIES,
    EXPECTED_CANDLE_COUNT,
    MANIFEST,
    REQUEST,
    candle,
)
from gemini_trading.data.errors import CandleGapError, CandleValidationError
from gemini_trading.data.segments import (
    load_candle_segment_manifest,
    segment_number_for_index,
    serialize_candle_segment_manifest,
    validate_and_segment_candle_sequence,
)
from gemini_trading.data.validation.candles import validate_candle_sequence


def test_declared_multi_closure_sequence_produces_all_segments() -> None:
    segments = validate_and_segment_candle_sequence(CANDLES, REQUEST, MANIFEST)

    assert len(CANDLES) == EXPECTED_CANDLE_COUNT
    assert len(segments.segments) == len(MANIFEST.closures) + 1 == 21
    assert segments.boundary_indices == EXPECTED_BOUNDARIES
    assert tuple(item.preceding_closure_id for item in segments.segments[1:]) == tuple(
        item.closure_id for item in MANIFEST.closures
    )
    assert segments.segments[0].preceding_closure_id is None
    assert segments.segments[0].first_open_time == REQUEST.start_time
    assert segments.segments[-1].last_open_time == CANDLES[-1].open_time
    assert sum(item.candle_count for item in segments.segments) == EXPECTED_CANDLE_COUNT


def test_zero_missing_closure_still_creates_a_segment_boundary() -> None:
    zero_missing_index = next(
        index
        for index, closure in enumerate(MANIFEST.closures)
        if closure.fully_missing_candle_count == 0
    )
    segments = validate_and_segment_candle_sequence(CANDLES, REQUEST, MANIFEST)
    closure = MANIFEST.closures[zero_missing_index]
    boundary = segments.boundary_indices[zero_missing_index]

    assert CANDLES[boundary].open_time == closure.resumed_open
    assert segments.segments[zero_missing_index + 1].preceding_closure_id == closure.closure_id


def test_strict_validation_still_rejects_the_first_gap() -> None:
    with pytest.raises(CandleGapError, match="timeframe gap"):
        validate_candle_sequence(CANDLES, REQUEST)


def test_shifted_actual_resumption_is_rejected_as_undeclared() -> None:
    first_boundary, second_boundary = EXPECTED_BOUNDARIES[:2]
    shifted = tuple(
        replace(
            item,
            open_time=item.open_time + timedelta(hours=4),
            close_time=item.close_time + timedelta(hours=4),
        )
        if first_boundary <= index < second_boundary
        else item
        for index, item in enumerate(CANDLES)
    )

    with pytest.raises(CandleGapError, match="undeclared timeframe gap"):
        validate_and_segment_candle_sequence(shifted, REQUEST, MANIFEST)


def test_additional_provider_gap_is_rejected() -> None:
    removed_index = 100
    gapped = (*CANDLES[:removed_index], *CANDLES[removed_index + 1 :])

    with pytest.raises(CandleGapError, match="undeclared timeframe gap"):
        validate_and_segment_candle_sequence(gapped, REQUEST, MANIFEST)


def test_unused_closure_declaration_is_rejected() -> None:
    first_closure = MANIFEST.closures[0]
    restored = tuple(
        candle(
            first_closure.canonical_gap_start + offset * MANIFEST.timeframe.duration,
            seed=90 + offset,
        )
        for offset in range(first_closure.unavailable_candle_count)
    )
    continuous_first_closure = tuple(sorted((*CANDLES, *restored), key=lambda item: item.open_time))

    with pytest.raises(CandleValidationError, match="unused"):
        validate_and_segment_candle_sequence(continuous_first_closure, REQUEST, MANIFEST)


def test_segment_manifest_round_trips_canonically() -> None:
    segments = validate_and_segment_candle_sequence(CANDLES, REQUEST, MANIFEST)
    raw = serialize_candle_segment_manifest(segments)

    assert load_candle_segment_manifest(raw) == segments
    assert serialize_candle_segment_manifest(load_candle_segment_manifest(raw)) == raw


def test_segment_manifest_rejects_tampered_segment_number() -> None:
    segments = validate_and_segment_candle_sequence(CANDLES, REQUEST, MANIFEST)
    raw = serialize_candle_segment_manifest(segments)
    tampered = raw.replace(b'"segment_number":1', b'"segment_number":9', 1)

    with pytest.raises(CandleValidationError, match="segment numbers"):
        load_candle_segment_manifest(tampered)


def test_segment_lookup_resolves_each_fixed_boundary() -> None:
    segments = validate_and_segment_candle_sequence(CANDLES, REQUEST, MANIFEST)

    assert segment_number_for_index(segments, 0) == 1
    for segment_number, boundary in enumerate(EXPECTED_BOUNDARIES, start=2):
        assert segment_number_for_index(segments, boundary) == segment_number


def test_segment_lookup_rejects_an_index_outside_evidence() -> None:
    segments = validate_and_segment_candle_sequence(CANDLES, REQUEST, MANIFEST)

    with pytest.raises(CandleValidationError, match="outside"):
        segment_number_for_index(segments, len(CANDLES))
