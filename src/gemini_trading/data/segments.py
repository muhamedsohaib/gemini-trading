"""Exact exchange-gap matching and deterministic candle segmentation."""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Never, cast

from gemini_trading.data.errors import CandleGapError, CandleValidationError
from gemini_trading.data.exchange_closures import ExchangeClosureManifest
from gemini_trading.data.validation.candles import validate_candle_sequence_structure
from gemini_trading.domain.candle import Candle
from gemini_trading.domain.dataset import RetrievalRequest
from gemini_trading.domain.timeframe import Timeframe

_SCHEMA_VERSION = "candle-segment-manifest-v1"
_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
_MANIFEST_FIELDS = {"schema_version", "segments"}
_SEGMENT_FIELDS = {
    "segment_number",
    "start_index",
    "end_exclusive",
    "first_open_time",
    "last_open_time",
    "candle_count",
    "preceding_closure_id",
}


def _fail(message: str) -> Never:
    raise CandleValidationError(message)


def _mapping(value: object, description: str) -> dict[str, object]:
    if not isinstance(value, dict):
        _fail(f"candle segment {description} must be an object")
    raw = cast(dict[object, object], value)
    if not all(isinstance(key, str) for key in raw):
        _fail(f"candle segment {description} fields are invalid")
    return cast(dict[str, object], raw)


def _exact_fields(mapping: dict[str, object], expected: set[str], description: str) -> None:
    if set(mapping) != expected:
        _fail(f"candle segment {description} fields are invalid")


def _string(mapping: dict[str, object], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value:
        _fail(f"candle segment field is invalid: {key}")
    return value


def _integer(mapping: dict[str, object], key: str) -> int:
    value = mapping.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        _fail(f"candle segment field is invalid: {key}")
    return value


def _utc(value: str, field_name: str) -> datetime:
    if not value.endswith("Z"):
        _fail(f"candle segment {field_name} must be UTC")
    try:
        parsed = datetime.fromisoformat(f"{value[:-1]}+00:00")
    except ValueError:
        _fail(f"candle segment {field_name} must be valid UTC")
    if parsed.utcoffset() != UTC.utcoffset(parsed):
        _fail(f"candle segment {field_name} must be UTC")
    return parsed.astimezone(UTC)


def _format_datetime(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


@dataclass(frozen=True, slots=True)
class CandleSegment:
    """One maximal continuous interval inside a canonical candle sequence."""

    segment_number: int
    start_index: int
    end_exclusive: int
    first_open_time: datetime
    last_open_time: datetime
    candle_count: int
    preceding_closure_id: str | None

    def __post_init__(self) -> None:
        if isinstance(self.segment_number, bool) or self.segment_number < 1:
            _fail("candle segment number must be positive")
        if isinstance(self.start_index, bool) or self.start_index < 0:
            _fail("candle segment start index must be non-negative")
        if isinstance(self.end_exclusive, bool) or self.end_exclusive <= self.start_index:
            _fail("candle segment index window must be non-empty")
        if isinstance(self.candle_count, bool) or self.candle_count < 1:
            _fail("candle segment count must be positive")
        if self.candle_count != self.end_exclusive - self.start_index:
            _fail("candle segment count does not match its index window")
        if self.first_open_time.tzinfo is None or self.first_open_time.utcoffset() is None:
            _fail("candle segment first_open_time must be UTC")
        if self.last_open_time.tzinfo is None or self.last_open_time.utcoffset() is None:
            _fail("candle segment last_open_time must be UTC")
        if self.last_open_time < self.first_open_time:
            _fail("candle segment timestamps are reversed")
        if (
            self.preceding_closure_id is not None
            and _ID_PATTERN.fullmatch(self.preceding_closure_id) is None
        ):
            _fail("invalid preceding exchange closure ID")


@dataclass(frozen=True, slots=True)
class CandleSegmentManifest:
    """Canonical ordered coverage of all continuous candle segments."""

    schema_version: str
    segments: tuple[CandleSegment, ...]

    def __post_init__(self) -> None:
        if self.schema_version != _SCHEMA_VERSION:
            _fail("unsupported candle segment manifest schema")
        if not self.segments:
            _fail("candle segment manifest must not be empty")
        expected_numbers = tuple(range(1, len(self.segments) + 1))
        actual_numbers = tuple(segment.segment_number for segment in self.segments)
        if actual_numbers != expected_numbers:
            _fail("candle segment numbers must be consecutive")
        if self.segments[0].start_index != 0:
            _fail("first candle segment must start at index zero")
        if self.segments[0].preceding_closure_id is not None:
            _fail("first candle segment cannot follow a closure")

        preceding_ids: list[str] = []
        previous: CandleSegment | None = None
        for segment in self.segments:
            if previous is not None:
                if segment.start_index != previous.end_exclusive:
                    _fail("candle segment index coverage is not contiguous")
                if segment.first_open_time <= previous.last_open_time:
                    _fail("candle segment timestamps are not ordered")
                if segment.preceding_closure_id is None:
                    _fail("resumed candle segment lacks closure identity")
                preceding_ids.append(segment.preceding_closure_id)
            previous = segment
        if len(preceding_ids) != len(set(preceding_ids)):
            _fail("duplicate preceding exchange closure ID")

    @property
    def boundary_indices(self) -> tuple[int, ...]:
        """Return every segment start after the first segment."""

        return tuple(segment.start_index for segment in self.segments[1:])


def _segment_payload(segment: CandleSegment) -> dict[str, object]:
    return {
        "segment_number": segment.segment_number,
        "start_index": segment.start_index,
        "end_exclusive": segment.end_exclusive,
        "first_open_time": _format_datetime(segment.first_open_time),
        "last_open_time": _format_datetime(segment.last_open_time),
        "candle_count": segment.candle_count,
        "preceding_closure_id": segment.preceding_closure_id,
    }


def serialize_candle_segment_manifest(manifest: CandleSegmentManifest) -> bytes:
    """Serialize deterministic candle segment evidence."""

    payload: dict[str, object] = {
        "schema_version": manifest.schema_version,
        "segments": [_segment_payload(segment) for segment in manifest.segments],
    }
    serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return f"{serialized}\n".encode()


def load_candle_segment_manifest(raw: bytes) -> CandleSegmentManifest:
    """Parse exact canonical segment bytes and reject alternate encodings."""

    try:
        loaded: object = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        _fail("candle segment manifest is not valid JSON")
    mapping = _mapping(loaded, "manifest")
    _exact_fields(mapping, _MANIFEST_FIELDS, "manifest")
    raw_segments = mapping.get("segments")
    if not isinstance(raw_segments, list):
        _fail("candle segment manifest segments field is invalid")

    segments: list[CandleSegment] = []
    for raw_segment in cast(list[object], raw_segments):
        segment_mapping = _mapping(raw_segment, "entry")
        _exact_fields(segment_mapping, _SEGMENT_FIELDS, "entry")
        preceding_closure_id = segment_mapping.get("preceding_closure_id")
        if preceding_closure_id is not None and not isinstance(preceding_closure_id, str):
            _fail("candle segment preceding_closure_id field is invalid")
        segments.append(
            CandleSegment(
                segment_number=_integer(segment_mapping, "segment_number"),
                start_index=_integer(segment_mapping, "start_index"),
                end_exclusive=_integer(segment_mapping, "end_exclusive"),
                first_open_time=_utc(
                    _string(segment_mapping, "first_open_time"), "first_open_time"
                ),
                last_open_time=_utc(
                    _string(segment_mapping, "last_open_time"), "last_open_time"
                ),
                candle_count=_integer(segment_mapping, "candle_count"),
                preceding_closure_id=preceding_closure_id,
            )
        )

    manifest = CandleSegmentManifest(
        schema_version=_string(mapping, "schema_version"),
        segments=tuple(segments),
    )
    if serialize_candle_segment_manifest(manifest) != raw:
        _fail("candle segment manifest encoding is not canonical")
    return manifest


def _build_segment(
    candles: tuple[Candle, ...],
    *,
    segment_number: int,
    start_index: int,
    end_exclusive: int,
    preceding_closure_id: str | None,
) -> CandleSegment:
    return CandleSegment(
        segment_number=segment_number,
        start_index=start_index,
        end_exclusive=end_exclusive,
        first_open_time=candles[start_index].open_time,
        last_open_time=candles[end_exclusive - 1].open_time,
        candle_count=end_exclusive - start_index,
        preceding_closure_id=preceding_closure_id,
    )


def _validate_manifest_scope(
    manifest: ExchangeClosureManifest,
    request: RetrievalRequest,
) -> None:
    if (
        manifest.instrument != request.instrument
        or manifest.timeframe != request.timeframe
        or manifest.start_time != request.start_time
        or manifest.end_time != request.end_time
    ):
        _fail("exchange closure manifest does not match retrieval request")


def _validate_candle_boundaries(candles: tuple[Candle, ...], timeframe: Timeframe) -> None:
    expected_close_delta = timeframe.duration - timedelta(milliseconds=1)
    if any(
        candle.close_time - candle.open_time != expected_close_delta for candle in candles
    ):
        _fail("candle boundaries do not match timeframe")


def validate_and_segment_candle_sequence(
    candles: Sequence[Candle],
    request: RetrievalRequest,
    closure_manifest: ExchangeClosureManifest,
) -> CandleSegmentManifest:
    """Accept only exact declared discontinuities and derive maximal segments."""

    validate_candle_sequence_structure(candles, request)
    candle_values = tuple(candles)
    _validate_manifest_scope(closure_manifest, request)
    _validate_candle_boundaries(candle_values, request.timeframe)

    closures_by_bounds = {
        (closure.missing_start, closure.resumed_open): closure
        for closure in closure_manifest.closures
    }
    declared_ids = {closure.closure_id for closure in closure_manifest.closures}
    used_ids: set[str] = set()
    segments: list[CandleSegment] = []
    segment_start = 0
    preceding_closure_id: str | None = None
    previous = candle_values[0]

    for index, current in enumerate(candle_values[1:], start=1):
        expected_open = previous.open_time + request.timeframe.duration
        if current.open_time != expected_open:
            closure = closures_by_bounds.get((expected_open, current.open_time))
            if closure is None:
                raise CandleGapError(
                    "candle sequence contains an undeclared timeframe gap: "
                    f"previous_open_time={previous.open_time.isoformat()} "
                    f"expected_open_time={expected_open.isoformat()} "
                    f"actual_open_time={current.open_time.isoformat()}"
                )
            if closure.closure_id in used_ids:
                _fail("exchange closure declaration was observed more than once")
            segments.append(
                _build_segment(
                    candle_values,
                    segment_number=len(segments) + 1,
                    start_index=segment_start,
                    end_exclusive=index,
                    preceding_closure_id=preceding_closure_id,
                )
            )
            used_ids.add(closure.closure_id)
            segment_start = index
            preceding_closure_id = closure.closure_id
        previous = current

    unused_ids = tuple(sorted(declared_ids - used_ids))
    if unused_ids:
        _fail(
            "exchange closure manifest contains unused declarations: " + ",".join(unused_ids)
        )
    segments.append(
        _build_segment(
            candle_values,
            segment_number=len(segments) + 1,
            start_index=segment_start,
            end_exclusive=len(candle_values),
            preceding_closure_id=preceding_closure_id,
        )
    )
    return CandleSegmentManifest(schema_version=_SCHEMA_VERSION, segments=tuple(segments))


def segment_number_for_index(manifest: CandleSegmentManifest, index: int) -> int:
    """Return the one-based segment number containing a global candle index."""

    if isinstance(index, bool) or index < 0:
        _fail("candle index must be a non-negative integer")
    for segment in manifest.segments:
        if segment.start_index <= index < segment.end_exclusive:
            return segment.segment_number
    _fail("candle index is outside segment evidence")


__all__ = [
    "CandleSegment",
    "CandleSegmentManifest",
    "load_candle_segment_manifest",
    "segment_number_for_index",
    "serialize_candle_segment_manifest",
    "validate_and_segment_candle_sequence",
]
