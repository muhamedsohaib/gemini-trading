"""Exact Binance partial-row matching and deterministic exclusion evidence."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from typing import Never, NoReturn, cast

from gemini_trading.data.errors import CandleValidationError
from gemini_trading.data.exchange_closures import ExchangeClosureManifest, PartialCandleDeclaration
from gemini_trading.data.normalization.binance_klines import normalize_binance_klines
from gemini_trading.domain.candle import Candle
from gemini_trading.domain.dataset import RawPage

_SCHEMA_VERSION = "candle-exclusion-manifest-v1"
_PROVIDER = "binance_spot"
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
_MANIFEST_FIELDS = {"schema_version", "exclusions"}
_EXCLUSION_FIELDS = {
    "closure_id",
    "raw_page_sequence",
    "raw_page_sha256",
    "row_index",
    "provider_row_sha256",
    "open_time",
    "actual_close_time",
    "expected_close_time",
    "exclusion_reason",
    "canonical_index_before_removal",
}


def _fail(message: str) -> Never:
    raise CandleValidationError(message)


def _reject_json_constant(_value: str) -> NoReturn:
    raise ValueError("non-standard JSON constant")


def _mapping(value: object, description: str) -> dict[str, object]:
    if not isinstance(value, dict):
        _fail(f"candle exclusion {description} must be an object")
    raw = cast(dict[object, object], value)
    if not all(isinstance(key, str) for key in raw):
        _fail(f"candle exclusion {description} fields are invalid")
    return cast(dict[str, object], raw)


def _exact_fields(mapping: dict[str, object], expected: set[str], description: str) -> None:
    if set(mapping) != expected:
        _fail(f"candle exclusion {description} fields are invalid")


def _string(mapping: dict[str, object], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value:
        _fail(f"candle exclusion field is invalid: {key}")
    return value


def _integer(mapping: dict[str, object], key: str) -> int:
    value = mapping.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        _fail(f"candle exclusion field is invalid: {key}")
    return value


def _utc(value: str, field_name: str) -> datetime:
    if not value.endswith("Z"):
        _fail(f"candle exclusion {field_name} must be UTC")
    try:
        parsed = datetime.fromisoformat(f"{value[:-1]}+00:00")
    except ValueError:
        _fail(f"candle exclusion {field_name} must be valid UTC")
    if parsed.utcoffset() != timedelta(0):
        _fail(f"candle exclusion {field_name} must be UTC")
    return parsed.astimezone(UTC)


def _format_datetime(value: datetime) -> str:
    timespec = "milliseconds" if value.microsecond else "seconds"
    return value.astimezone(UTC).isoformat(timespec=timespec).replace("+00:00", "Z")


def _require_utc(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        _fail(f"candle exclusion {field_name} must be UTC")


def _require_sha256(value: str, field_name: str) -> None:
    if _SHA256_PATTERN.fullmatch(value) is None:
        _fail(f"candle exclusion {field_name} must be a lowercase SHA-256 digest")


@dataclass(frozen=True, slots=True)
class CandleExclusion:
    """One exact raw provider row excluded from the canonical candle sequence."""

    closure_id: str
    raw_page_sequence: int
    raw_page_sha256: str
    row_index: int
    provider_row_sha256: str
    open_time: datetime
    actual_close_time: datetime
    expected_close_time: datetime
    exclusion_reason: str
    canonical_index_before_removal: int

    def __post_init__(self) -> None:
        if _ID_PATTERN.fullmatch(self.closure_id) is None:
            _fail("candle exclusion closure ID is invalid")
        if isinstance(self.raw_page_sequence, bool) or self.raw_page_sequence < 1:
            _fail("candle exclusion raw page sequence must be positive")
        if isinstance(self.row_index, bool) or self.row_index < 0:
            _fail("candle exclusion row index must be non-negative")
        if (
            isinstance(self.canonical_index_before_removal, bool)
            or self.canonical_index_before_removal < 0
        ):
            _fail("candle exclusion canonical index must be non-negative")
        _require_sha256(self.raw_page_sha256, "raw page SHA-256")
        _require_sha256(self.provider_row_sha256, "provider-row SHA-256")
        _require_utc(self.open_time, "open_time")
        _require_utc(self.actual_close_time, "actual_close_time")
        _require_utc(self.expected_close_time, "expected_close_time")
        if not self.open_time < self.actual_close_time < self.expected_close_time:
            _fail("candle exclusion partial boundaries are invalid")
        if not self.exclusion_reason.strip():
            _fail("candle exclusion reason must not be empty")


@dataclass(frozen=True, slots=True)
class CandleExclusionManifest:
    """Canonical derived evidence for every exactly matched partial row."""

    schema_version: str
    exclusions: tuple[CandleExclusion, ...]

    def __post_init__(self) -> None:
        if self.schema_version != _SCHEMA_VERSION:
            _fail("unsupported candle exclusion manifest schema")
        if not self.exclusions:
            _fail("candle exclusion manifest must not be empty")
        closure_ids = tuple(item.closure_id for item in self.exclusions)
        if len(closure_ids) != len(set(closure_ids)):
            _fail("duplicate candle exclusion closure ID")
        row_locations = tuple((item.raw_page_sequence, item.row_index) for item in self.exclusions)
        if len(row_locations) != len(set(row_locations)):
            _fail("duplicate candle exclusion raw row location")
        provider_hashes = tuple(item.provider_row_sha256 for item in self.exclusions)
        if len(provider_hashes) != len(set(provider_hashes)):
            _fail("duplicate candle exclusion provider-row SHA-256")
        indices = tuple(item.canonical_index_before_removal for item in self.exclusions)
        if indices != tuple(sorted(indices)) or len(indices) != len(set(indices)):
            _fail("candle exclusions must be ordered by unique canonical index")


@dataclass(frozen=True, slots=True)
class CandleExclusionResult:
    """Completed canonical candles and the derived exclusion manifest."""

    candles: tuple[Candle, ...]
    manifest: CandleExclusionManifest


def canonical_binance_row_bytes(row: object) -> bytes:
    """Return compact canonical JSON bytes for one exact Binance kline row."""

    if not isinstance(row, list):
        _fail("Binance kline row must contain at least 7 fields")
    values = cast(list[object], row)
    if len(values) < 7:
        _fail("Binance kline row must contain at least 7 fields")
    if any(isinstance(value, bool) or not isinstance(value, (str, int)) for value in values):
        _fail("Binance kline row contains a non-canonical value")
    return json.dumps(values, ensure_ascii=False, separators=(",", ":")).encode()


def _exclusion_payload(exclusion: CandleExclusion) -> dict[str, object]:
    return {
        "closure_id": exclusion.closure_id,
        "raw_page_sequence": exclusion.raw_page_sequence,
        "raw_page_sha256": exclusion.raw_page_sha256,
        "row_index": exclusion.row_index,
        "provider_row_sha256": exclusion.provider_row_sha256,
        "open_time": _format_datetime(exclusion.open_time),
        "actual_close_time": _format_datetime(exclusion.actual_close_time),
        "expected_close_time": _format_datetime(exclusion.expected_close_time),
        "exclusion_reason": exclusion.exclusion_reason,
        "canonical_index_before_removal": exclusion.canonical_index_before_removal,
    }


def serialize_candle_exclusion_manifest(manifest: CandleExclusionManifest) -> bytes:
    """Serialize deterministic candle-exclusion evidence."""

    payload: dict[str, object] = {
        "schema_version": manifest.schema_version,
        "exclusions": [_exclusion_payload(item) for item in manifest.exclusions],
    }
    serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return f"{serialized}\n".encode()


def load_candle_exclusion_manifest(raw: bytes) -> CandleExclusionManifest:
    """Parse canonical exclusion bytes and reject alternate encodings."""

    try:
        loaded: object = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        _fail("candle exclusion manifest is not valid JSON")
    mapping = _mapping(loaded, "manifest")
    _exact_fields(mapping, _MANIFEST_FIELDS, "manifest")
    raw_exclusions = mapping.get("exclusions")
    if not isinstance(raw_exclusions, list):
        _fail("candle exclusion manifest exclusions field is invalid")

    exclusions: list[CandleExclusion] = []
    for raw_exclusion in cast(list[object], raw_exclusions):
        item = _mapping(raw_exclusion, "entry")
        _exact_fields(item, _EXCLUSION_FIELDS, "entry")
        exclusions.append(
            CandleExclusion(
                closure_id=_string(item, "closure_id"),
                raw_page_sequence=_integer(item, "raw_page_sequence"),
                raw_page_sha256=_string(item, "raw_page_sha256"),
                row_index=_integer(item, "row_index"),
                provider_row_sha256=_string(item, "provider_row_sha256"),
                open_time=_utc(_string(item, "open_time"), "open_time"),
                actual_close_time=_utc(_string(item, "actual_close_time"), "actual_close_time"),
                expected_close_time=_utc(
                    _string(item, "expected_close_time"), "expected_close_time"
                ),
                exclusion_reason=_string(item, "exclusion_reason"),
                canonical_index_before_removal=_integer(item, "canonical_index_before_removal"),
            )
        )
    manifest = CandleExclusionManifest(
        schema_version=_string(mapping, "schema_version"),
        exclusions=tuple(exclusions),
    )
    if serialize_candle_exclusion_manifest(manifest) != raw:
        _fail("candle exclusion manifest encoding is not canonical")
    return manifest


def _decode_page_rows(page: RawPage) -> tuple[list[object], ...]:
    actual_page_hash = hashlib.sha256(page.response_bytes).hexdigest()
    if actual_page_hash != page.response_sha256:
        _fail("raw page SHA-256 mismatch during candle exclusion")
    if not 200 <= page.http_status <= 299:
        _fail("raw page HTTP status is not successful")
    try:
        decoded: object = json.loads(
            page.response_bytes.decode("utf-8"),
            parse_float=str,
            parse_constant=_reject_json_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        _fail("raw Binance page is not valid canonical JSON evidence")
    if not isinstance(decoded, list):
        _fail("raw Binance page root must be a list")
    rows: list[list[object]] = []
    for raw_row in cast(list[object], decoded):
        if not isinstance(raw_row, list):
            _fail("raw Binance page contains an invalid kline row")
        row = cast(list[object], raw_row)
        if len(row) < 7:
            _fail("raw Binance page contains an invalid kline row")
        canonical_binance_row_bytes(row)
        rows.append(row)
    return tuple(rows)


def _validate_page_identity(
    pages: Sequence[RawPage],
    normalized_pages: Sequence[Sequence[Candle]],
    manifest: ExchangeClosureManifest,
    server_time: datetime,
) -> None:
    _require_utc(server_time, "server_time")
    if manifest.provider != _PROVIDER:
        _fail("candle exclusion requires Binance Spot provider identity")
    if len(pages) != len(normalized_pages) or not pages:
        _fail("raw and normalized page evidence does not align")
    run_ids = {page.run_id for page in pages}
    if len(run_ids) != 1:
        _fail("raw pages do not share one retrieval run")
    sequences = tuple(page.sequence for page in pages)
    if sequences != tuple(range(1, len(pages) + 1)):
        _fail("raw page sequence is not consecutive")
    if any(page.server_time_snapshot != server_time for page in pages):
        _fail("raw page server-time snapshot mismatch")

    expected_symbol = manifest.instrument.symbol
    expected_interval = manifest.timeframe.value
    for page in pages:
        parameters = dict(page.request_parameters)
        if parameters.get("symbol") != expected_symbol:
            _fail("raw page symbol does not match exclusion manifest")
        if parameters.get("interval") != expected_interval:
            _fail("raw page interval does not match exclusion manifest")


def _partial_declarations(
    manifest: ExchangeClosureManifest,
) -> dict[datetime, tuple[str, PartialCandleDeclaration]]:
    return {
        partial.open_time: (closure.closure_id, partial)
        for closure in manifest.closures
        if (partial := closure.partial_candle) is not None
    }


def match_and_exclude_partial_candles(
    pages: Sequence[RawPage],
    normalized_pages: Sequence[Sequence[Candle]],
    closure_manifest: ExchangeClosureManifest,
    *,
    server_time: datetime,
) -> CandleExclusionResult:
    """Match every declared partial row exactly and exclude it once from canonical data."""

    _validate_page_identity(pages, normalized_pages, closure_manifest, server_time)
    declarations = _partial_declarations(closure_manifest)
    matches: dict[str, CandleExclusion] = {}
    canonical: list[Candle] = []
    seen_open_times: set[datetime] = set()
    previous_open_time: datetime | None = None
    global_index = 0

    for page, supplied_page in zip(pages, normalized_pages, strict=True):
        rows = _decode_page_rows(page)
        normalized_page = tuple(supplied_page)
        reproduced_page = normalize_binance_klines(
            page.response_bytes,
            closure_manifest.instrument,
            closure_manifest.timeframe,
        )
        if normalized_page != reproduced_page or len(rows) != len(normalized_page):
            _fail("normalized candles do not match immutable raw rows")

        for row_index, (row, candle) in enumerate(zip(rows, normalized_page, strict=True)):
            if candle.instrument != closure_manifest.instrument:
                _fail("normalized candle instrument does not match exclusion manifest")
            if candle.timeframe != closure_manifest.timeframe:
                _fail("normalized candle timeframe does not match exclusion manifest")
            if not closure_manifest.start_time <= candle.open_time < closure_manifest.end_time:
                _fail("normalized candle is outside the exclusion request window")
            if candle.open_time in seen_open_times:
                _fail("duplicate normalized candle open time in raw evidence")
            if previous_open_time is not None and candle.open_time <= previous_open_time:
                _fail("normalized candle open times are out of order")
            seen_open_times.add(candle.open_time)
            previous_open_time = candle.open_time

            declaration = declarations.get(candle.open_time)
            expected_close = (
                candle.open_time + closure_manifest.timeframe.duration - timedelta(milliseconds=1)
            )
            row_hash = hashlib.sha256(canonical_binance_row_bytes(row)).hexdigest()
            if declaration is not None:
                closure_id, partial = declaration
                if candle.close_time != partial.actual_close_time:
                    _fail("declared partial candle actual close mismatch")
                if expected_close != partial.expected_close_time:
                    _fail("declared partial candle expected close mismatch")
                if (
                    partial.provider_row_sha256 is not None
                    and row_hash != partial.provider_row_sha256
                ):
                    _fail("declared partial candle provider-row SHA-256 mismatch")
                if candle.close_time >= server_time:
                    _fail("declared partial candle is not closed at the server snapshot")
                if closure_id in matches:
                    _fail("declared partial candle appears more than once")
                matches[closure_id] = CandleExclusion(
                    closure_id=closure_id,
                    raw_page_sequence=page.sequence,
                    raw_page_sha256=page.response_sha256,
                    row_index=row_index,
                    provider_row_sha256=row_hash,
                    open_time=candle.open_time,
                    actual_close_time=candle.close_time,
                    expected_close_time=expected_close,
                    exclusion_reason=partial.exclusion_reason,
                    canonical_index_before_removal=global_index,
                )
                global_index += 1
                continue

            if candle.close_time != expected_close:
                _fail("raw evidence contains an undeclared partial or malformed candle")
            if candle.close_time < server_time:
                canonical.append(replace(candle, completed=True))
            global_index += 1

    if not seen_open_times or min(seen_open_times) != closure_manifest.start_time:
        _fail("raw evidence does not begin at the exclusion request window")
    missing_ids = tuple(
        closure_id
        for closure_id, _partial in declarations.values()
        if closure_id not in matches
    )
    if missing_ids:
        _fail("declared partial candle is missing from raw evidence: " + ",".join(missing_ids))

    for closure in closure_manifest.closures:
        absent_opens = {
            closure.fully_missing_start + offset * closure_manifest.timeframe.duration
            for offset in range(closure.fully_missing_candle_count)
        }
        if absent_opens & seen_open_times:
            _fail("raw evidence contains a candle inside the fully missing closure interval")
        if closure.resumed_open not in seen_open_times:
            _fail("raw evidence lacks the declared resumed candle")

    ordered_exclusions = tuple(
        sorted(matches.values(), key=lambda item: item.canonical_index_before_removal)
    )
    return CandleExclusionResult(
        candles=tuple(canonical),
        manifest=CandleExclusionManifest(
            schema_version=_SCHEMA_VERSION,
            exclusions=ordered_exclusions,
        ),
    )


__all__ = [
    "CandleExclusion",
    "CandleExclusionManifest",
    "CandleExclusionResult",
    "canonical_binance_row_bytes",
    "load_candle_exclusion_manifest",
    "match_and_exclude_partial_candles",
    "serialize_candle_exclusion_manifest",
]
