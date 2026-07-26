"""Exact exchange-gap matching and deterministic candle segmentation."""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import cast

from gemini_trading.data.errors import CandleGapError, CandleValidationError
from gemini_trading.data.exchange_closures import ExchangeClosureManifest
from gemini_trading.data.validation.candles import validate_candle_sequence_structure
from gemini_trading.domain.candle import Candle
from gemini_trading.domain.dataset import RetrievalRequest
from gemini_trading.domain.time import require_utc
from gemini_trading.research.serialization import canonical_json_bytes

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


def _format_utc(value: datetime) -> str:
    require_utc(value, "timestamp")
    return value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _mapping(value: object, description: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise CandleValidationError(f"{description} must be a JSON object")
    raw = cast(dict[object, object], value)
    if not all(isinstance(key, str) for key in raw):
        raise CandleValidationError(f"{description} keys must be strings")
    return cast(dict[str, object], raw)


def _exact_fields(
    mapping: dict[str, object],
    expected: set[str],
    description: str,
) -> None:
    if set(mapping) != expected:
        raise CandleValidationError(f"invalid {description} fields")


def _string(mapping: dict[str, object], key: str, description: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value:
        raise CandleValidationError(f"invalid {description} field: {key}")
    return value


def _integer(mapping: dict[str, object], key: str, description: str) -> int:
    value = mapping.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise CandleValidationError(f"invalid {description} field: {key}")
    return value


def _utc(value: str, field_name: str) -> datetime:
    if not value.endswith("Z"):
        raise CandleValidationError(f"candle segment {field_name} must be UTC")
    try:
        parsed = datetime.fromisoformat(f"{value[:-1]}+00:00")
        require_utc(parsed, field_name)
    except ValueError:
        raise CandleValidationError(
            f"candle segment {field_name} must be valid UTC"
        ) from None
    return parsed.astimezone(UTC)


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
            raise CandleValidationError("candle segment number must be positive")
        if isinstance(self.start_index, bool) or self.start_index < 0:
            raise CandleValidationError("candle segment start index must be non-negative")
        if isinstance(self.end_exclusive, bool) or self.end_exclusive <= self.start_index:
            raise CandleValidationError("candle segment index window is empty")
        if isinstance(self.candle_count, bool) or self.candle_count < 1:
            raise CandleValidationError("candle segment count must be positive")
        if self.candle_count != self.end_exclusive - self.start_index:
            raise CandleValidationError("candle segment count does not match index window")
        require_utc(self.first_open_time, "first_open_time")
        require_utc(self.last_open_time, "last_open_time")
        if self.last_open_time < self.first_open_time:
            raise CandleValidationError("candle segment timestamps are reversed")
        if self.preceding_closure_id is not None:
            if _ID_PATTERN.fullmatch(self.preceding_closure_id) is None:
                raise CandleValidationError("invalid preceding exchange closure ID")


@dataclass(frozen=True, slots=True)
class CandleSegmentManifest:
    """Canonical ordered coverage of all continuous candle segments."""

    schema_version: str
    segments: tuple[CandleSegment, ...]

    def __post_init__(self) -> None:
        if self.schema_version != _SCHEMA_VERSION:
            raise CandleValidationError("unsupported candle segment manifest schema")
        if not self.segments:
            raise CandleValidationError("candle segment manifest must not be empty")
        expected_numbers = tuple(range(1, len(self.segments) + 1))
        actual_numbers = tuple(segment.segment_number for segment in self.segments)
        if actual_numbers != expected_numbers:
            raise CandleValidationError("candle segment numbers must be consecutive")
        if self.segments[0].start_index != 0:
            raise CandleValidationError("first candle segment must start at index zero")
        if self.segments[0].preceding_closure_id is not None:
            raise CandleValidationError("first candle segment cannot follow a closure")

        preceding_ids: list[str] = []
        previous: CandleSegment | None = None
        for segment in self.segments:
            if previous is not None:
                if segment.start_index != previous.end_exclusive:
                    raise CandleValidationError("candle segment index coverage is not contiguous")
                if segment.first_open_time <= previous.last_open_time:
                    raise CandleValidationError("candle segment timestamps are not ordered")
                if segment.preceding_closure_id is None:
                    raise CandleValidationError("resumed candle segment lacks closure identity")
                preceding_ids.append(segment.preceding_closure_id)
            previous = segment
        if len(preceding_ids) != len(set(preceding_ids)):
            raise CandleValidationError("duplicate preceding exchange closure ID")

    @property
    def boundary_indices(self) -> tuple[int, ...]:
        """Return every segment start after the first segment."""

        return tuple(segment.start_index for segment in self.segments[1:])


def _segment_payload(segment: CandleSegment) -> dict[str, object]:
    return {
        "segment_number": segment.segment_number,
        "start_index": segment.start_index,
        "end_exclusive": segment.end_exclusive,
        "first_open_time": _format_utc(segment.first_open_time),
        "last_open_time": _format_utc(segment.last_open_time),
        "candle_count": segment.candle_count,
        "preceding_closure_id": segment.preceding_closure_id,
    }


def serialize_candle_segment_manifest(manifest: CandleSegmentManifest) -> bytes:
    """Serialize deterministic candle segment evidence."""

    return canonical_json_bytes(
        {
            "schema_version": manifest.schema_version,
            "segments": [_segment_payload(segment) for segment in manifest.segments],
        }
    )


def load_candle_segment_manifest(raw: bytes) -> CandleSegmentManifest:
    """Parse exact canonical segment bytes and reject alternate encodings."""

    try:
        loaded: object = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise CandleValidationError("invalid candle segment manifest JSON") from None
    mapping = _mapping(loaded, "candle segment manifest")
    _exact_fields(mapping, _MANIFEST_FIELDS, "candle segment manifest")
    raw_segments = mapping.get("segments")
    if not isinstance(raw_segments, list):
        raise CandleValidationError("invalid candle segment manifest field: segments")

    segments: list[CandleSegment] = []
    for raw_segment in cast(list[object], raw_segments):
        segment_mapping = _mapping(raw_segment, "candle segment")
        _exact_fields(segment_mapping, _SEGMENT_FIELDS, "candle segment")
        preceding_raw = segment_mapping.get("preceding_closure_id")
        if preceding_raw is not None and not isinstance(preceding_raw, str):
            raise CandleValidationError(
                "invalid candle segment field: preceding_closure_id"
            )
        segments.append(
            CandleSegment(
                segment_number=_integer(
                    segment_mapping,
                    "segment_number",
                    "segment",
                ),
                start_index=_integer(segment_mapping, "start_index", "segment"),
                end_exclusive=_integer(
                    segment_mapping,
                    "end_exclusive",
                    "segment",
                ),
                first_open_time=_utc(
                    _string(segment_mapping, "first_open_time", "segment"),
                    "first_open_time",
                ),
                last_open_time=_utc(
                    _string(segment_mapping, "last_open_time", "segment"),
                    "last_open_time",
                ),
                candle_count=_integer(
                    segment_mapping,
                    "candle_count",
                    "segment",
                ),
                preceding_closure_id=preceding_raw,
            )
        )

    manifest = CandleSegmentManifest(
        schema_version=_string(mapping, "schema_version", "manifest"),
        segments=tuple(segments),
    )
    if serialize_candle_segment_manifest(manifest) != raw:
        raise CandleValidationError("candle segment manifest encoding is not canonical")
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


def validate_and_segment_candle_sequence(
    candles: Sequence[Candle],
    request: RetrievalRequest,
    closure_manifest: ExchangeClosureManifest,
) -> CandleSegmentManifest:
    """Accept only exact declared discontinuities and derive maximal segments."""

    validate_candle_sequence_structure(candles, request)
    candle_values = tuple(candles)
    if (
        closure_manifest.instrument != request.instrument
        or closure_manifest.timeframe != request.timeframe
        or closure_manifest.start_time != request.start_time
        or closure_manifest.end_time != request.end_time
    ):
        raise CandleValidationError(
            "exchange closure manifest does not match retrieval request"
        )

    duration = request.timeframe.duration
    expected_close_delta = duration - timedelta(milliseconds=1)
    for candle in candle_values:
        if candle.close_time - candle.open_time != expected_close_delta:
            raise CandleValidationError("candle boundaries do not match timeframe")

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
        expected_open = previous.open_time + duration
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
                raise CandleValidationError(
                    "exchange closure declaration was observed more than once"
                )
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
        raise CandleValidationError(
            "exchange closure manifest contains unused declarations: "
            + ",".join(unused_ids)
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
    return CandleSegmentManifest(
        schema_version=_SCHEMA_VERSION,
        segments=tuple(segments),
    )


def segment_number_for_index(
    manifest: CandleSegmentManifest,
    index: int,
) -> int:
    """Return the one-based segment number containing a global candle index."""

    if isinstance(index, bool) or index < 0:
        raise CandleValidationError("candle index must be a non-negative integer")
    for segment in manifest.segments:
        if segment.start_index <= index < segment.end_exclusive:
            return segment.segment_number
    raise CandleValidationError("candle index is outside segment evidence")


__all__ = [
    "CandleSegment",
    "CandleSegmentManifest",
    "load_candle_segment_manifest",
    "segment_number_for_index",
    "serialize_candle_segment_manifest",
    "validate_and_segment_candle_sequence",
]
