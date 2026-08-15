"""Version-isolated hourly Stage 1 contracts for Candidate v0.4."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Never, cast

from gemini_trading.data.exchange_closures import (
    ExchangeClosure,
    load_fixed_btcusdt_closure_manifest,
)
from gemini_trading.domain.instrument import Instrument
from gemini_trading.domain.timeframe import Timeframe
from gemini_trading.strategy.errors import DatasetHandoffError

V04_STAGE1_START = datetime(2018, 1, 1, tzinfo=UTC)
V04_STAGE1_END_EXCLUSIVE = datetime(2026, 8, 1, tzinfo=UTC)

_V04_CLOSURE_SCHEMA = "exchange-closure-manifest-v4"
_ONE_HOUR = timedelta(hours=1)
_ONE_MILLISECOND = timedelta(milliseconds=1)
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_MANIFEST_FIELDS = {
    "schema_version",
    "provider",
    "instrument",
    "timeframe",
    "start_time",
    "end_time",
    "source_manifest_sha256",
    "closures",
}
_INSTRUMENT_FIELDS = {"symbol", "base_asset", "quote_asset"}
_CLOSURE_FIELDS = {
    "closure_id",
    "canonical_gap_start",
    "resumed_open",
    "unavailable_candle_count",
    "fully_missing_start",
    "fully_missing_candle_count",
    "reason_code",
    "governance_reference",
    "partial_candle",
}
_PARTIAL_FIELDS = {
    "open_time",
    "actual_close_time",
    "expected_close_time",
    "provider_row_sha256",
    "exclusion_reason",
}


def _fail(message: str) -> Never:
    raise DatasetHandoffError(message)


def _require_utc(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        _fail(f"v0.4 hourly closure {field_name} must be UTC")


def _require_sha256(value: str, field_name: str) -> None:
    if _SHA256_PATTERN.fullmatch(value) is None:
        _fail(f"v0.4 hourly closure {field_name} must be a lowercase SHA-256 digest")


def _format_datetime(value: datetime) -> str:
    timespec = "milliseconds" if value.microsecond else "seconds"
    return value.astimezone(UTC).isoformat(timespec=timespec).replace("+00:00", "Z")


def _parse_utc(value: str, field_name: str) -> datetime:
    if not value.endswith("Z"):
        _fail(f"v0.4 hourly closure {field_name} must be UTC")
    try:
        parsed = datetime.fromisoformat(f"{value[:-1]}+00:00")
    except ValueError:
        _fail(f"v0.4 hourly closure {field_name} must be valid UTC")
    return parsed.astimezone(UTC)


def _mapping(value: object, description: str) -> dict[str, object]:
    if not isinstance(value, dict):
        _fail(f"v0.4 hourly closure {description} must be an object")
    raw = cast(dict[object, object], value)
    if not all(isinstance(key, str) for key in raw):
        _fail(f"v0.4 hourly closure {description} fields are invalid")
    return cast(dict[str, object], raw)


def _exact_fields(mapping: dict[str, object], expected: set[str], description: str) -> None:
    if set(mapping) != expected:
        _fail(f"v0.4 hourly closure {description} fields are invalid")


def _string(mapping: dict[str, object], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value:
        _fail(f"v0.4 hourly closure field is invalid: {key}")
    return value


def _integer(mapping: dict[str, object], key: str) -> int:
    value = mapping.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        _fail(f"v0.4 hourly closure field is invalid: {key}")
    return value


def _hour_open(value: datetime) -> datetime:
    _require_utc(value, "actual_close_time")
    return value.replace(minute=0, second=0, microsecond=0)


@dataclass(frozen=True, slots=True)
class V04PartialCandleDeclaration:
    """One preregistered hourly partial slot; row identity is bound after retrieval."""

    open_time: datetime
    actual_close_time: datetime
    expected_close_time: datetime
    provider_row_sha256: str | None
    exclusion_reason: str

    def __post_init__(self) -> None:
        _require_utc(self.open_time, "partial open_time")
        _require_utc(self.actual_close_time, "partial actual_close_time")
        _require_utc(self.expected_close_time, "partial expected_close_time")
        if not self.open_time < self.actual_close_time < self.expected_close_time:
            _fail("v0.4 hourly partial candle boundaries are invalid")
        if self.provider_row_sha256 is not None:
            _require_sha256(self.provider_row_sha256, "partial provider-row SHA-256")
        if not self.exclusion_reason.strip():
            _fail("v0.4 hourly partial exclusion reason must not be empty")


@dataclass(frozen=True, slots=True)
class V04ExchangeClosure:
    """One hourly outage derived only from frozen source interruption timestamps."""

    closure_id: str
    canonical_gap_start: datetime
    resumed_open: datetime
    unavailable_candle_count: int
    fully_missing_start: datetime
    fully_missing_candle_count: int
    reason_code: str
    governance_reference: str
    partial_candle: V04PartialCandleDeclaration | None

    def __post_init__(self) -> None:
        if not self.closure_id.strip():
            _fail("v0.4 hourly closure ID must not be empty")
        if not self.reason_code.strip() or not self.governance_reference.strip():
            _fail("v0.4 hourly closure governance fields must not be empty")
        for field_name, value in (
            ("canonical_gap_start", self.canonical_gap_start),
            ("fully_missing_start", self.fully_missing_start),
            ("resumed_open", self.resumed_open),
        ):
            _require_utc(value, field_name)
            if value != _hour_open(value):
                _fail(f"v0.4 hourly closure {field_name} must be hour aligned")
        if self.resumed_open <= self.canonical_gap_start:
            _fail("v0.4 hourly closure interval must be positive")
        if isinstance(self.unavailable_candle_count, bool) or self.unavailable_candle_count < 1:
            _fail("v0.4 hourly unavailable-candle count must be positive")
        if isinstance(self.fully_missing_candle_count, bool) or self.fully_missing_candle_count < 0:
            _fail("v0.4 hourly fully-missing count must be non-negative")

        expected_unavailable = (self.resumed_open - self.canonical_gap_start) // _ONE_HOUR
        expected_missing = (self.resumed_open - self.fully_missing_start) // _ONE_HOUR
        if expected_unavailable != self.unavailable_candle_count:
            _fail("v0.4 hourly unavailable-candle count mismatch")
        if expected_missing != self.fully_missing_candle_count:
            _fail("v0.4 hourly fully-missing candle count mismatch")

        if self.partial_candle is None:
            if self.fully_missing_start != self.canonical_gap_start:
                _fail("v0.4 full-missing-only closure must begin at its gap start")
            if self.unavailable_candle_count != self.fully_missing_candle_count:
                _fail("v0.4 full-missing-only closure counts are inconsistent")
        else:
            if self.partial_candle.open_time != self.canonical_gap_start:
                _fail("v0.4 partial hourly candle does not match its gap start")
            expected_close = self.canonical_gap_start + _ONE_HOUR - _ONE_MILLISECOND
            if self.partial_candle.expected_close_time != expected_close:
                _fail("v0.4 partial hourly expected close mismatch")
            if self.fully_missing_start != self.canonical_gap_start + _ONE_HOUR:
                _fail("v0.4 fully-missing start must follow its partial hourly slot")
            if self.unavailable_candle_count != self.fully_missing_candle_count + 1:
                _fail("v0.4 partial hourly closure counts are inconsistent")


@dataclass(frozen=True, slots=True)
class V04ExchangeClosureManifest:
    """Version-isolated hourly closure evidence for the v0.4 development window."""

    schema_version: str
    provider: str
    instrument: Instrument
    timeframe: Timeframe
    start_time: datetime
    end_time: datetime
    source_manifest_sha256: str
    closures: tuple[V04ExchangeClosure, ...]

    def __post_init__(self) -> None:
        if self.schema_version != _V04_CLOSURE_SCHEMA:
            _fail("unsupported v0.4 hourly closure schema")
        if self.provider != "binance_spot":
            _fail("v0.4 hourly closure provider changed")
        if self.instrument.symbol != "BTCUSDT":
            _fail("v0.4 hourly closure instrument changed")
        if self.timeframe is not Timeframe.H1:
            _fail("v0.4 hourly closure timeframe must be 1h")
        if (self.start_time, self.end_time) != (V04_STAGE1_START, V04_STAGE1_END_EXCLUSIVE):
            _fail("v0.4 hourly closure development window changed")
        _require_sha256(self.source_manifest_sha256, "source-manifest SHA-256")
        if not self.closures:
            _fail("v0.4 hourly closure manifest must contain closures")
        closure_ids = tuple(item.closure_id for item in self.closures)
        if len(closure_ids) != len(set(closure_ids)):
            _fail("duplicate v0.4 hourly closure ID")
        starts = tuple(item.canonical_gap_start for item in self.closures)
        if starts != tuple(sorted(starts)):
            _fail("v0.4 hourly closure entries must be ordered")
        previous: V04ExchangeClosure | None = None
        for closure in self.closures:
            if (
                not self.start_time
                <= closure.canonical_gap_start
                < closure.resumed_open
                <= self.end_time
            ):
                _fail("v0.4 hourly closure lies outside the development window")
            if previous is not None and closure.canonical_gap_start <= previous.resumed_open:
                _fail("v0.4 hourly closure entries overlap or touch")
            previous = closure


def _partial_payload(partial: V04PartialCandleDeclaration) -> dict[str, object]:
    return {
        "open_time": _format_datetime(partial.open_time),
        "actual_close_time": _format_datetime(partial.actual_close_time),
        "expected_close_time": _format_datetime(partial.expected_close_time),
        "provider_row_sha256": partial.provider_row_sha256,
        "exclusion_reason": partial.exclusion_reason,
    }


def _closure_payload(closure: V04ExchangeClosure) -> dict[str, object]:
    return {
        "closure_id": closure.closure_id,
        "canonical_gap_start": _format_datetime(closure.canonical_gap_start),
        "resumed_open": _format_datetime(closure.resumed_open),
        "unavailable_candle_count": closure.unavailable_candle_count,
        "fully_missing_start": _format_datetime(closure.fully_missing_start),
        "fully_missing_candle_count": closure.fully_missing_candle_count,
        "reason_code": closure.reason_code,
        "governance_reference": closure.governance_reference,
        "partial_candle": (
            None if closure.partial_candle is None else _partial_payload(closure.partial_candle)
        ),
    }


def serialize_v0_4_closure_manifest(manifest: V04ExchangeClosureManifest) -> bytes:
    """Serialize the exact v0.4 hourly closure declaration canonically."""

    payload: dict[str, object] = {
        "schema_version": manifest.schema_version,
        "provider": manifest.provider,
        "instrument": {
            "symbol": manifest.instrument.symbol,
            "base_asset": manifest.instrument.base_asset,
            "quote_asset": manifest.instrument.quote_asset,
        },
        "timeframe": manifest.timeframe.value,
        "start_time": _format_datetime(manifest.start_time),
        "end_time": _format_datetime(manifest.end_time),
        "source_manifest_sha256": manifest.source_manifest_sha256,
        "closures": [_closure_payload(item) for item in manifest.closures],
    }
    return (json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n").encode()


def _load_partial(value: object) -> V04PartialCandleDeclaration | None:
    if value is None:
        return None
    mapping = _mapping(value, "partial candle")
    _exact_fields(mapping, _PARTIAL_FIELDS, "partial candle")
    raw_digest = mapping.get("provider_row_sha256")
    if raw_digest is not None and not isinstance(raw_digest, str):
        _fail("v0.4 hourly partial provider-row SHA-256 is invalid")
    return V04PartialCandleDeclaration(
        open_time=_parse_utc(_string(mapping, "open_time"), "partial open_time"),
        actual_close_time=_parse_utc(
            _string(mapping, "actual_close_time"), "partial actual_close_time"
        ),
        expected_close_time=_parse_utc(
            _string(mapping, "expected_close_time"), "partial expected_close_time"
        ),
        provider_row_sha256=cast(str | None, raw_digest),
        exclusion_reason=_string(mapping, "exclusion_reason"),
    )


def load_v0_4_closure_manifest(raw: bytes) -> V04ExchangeClosureManifest:
    """Load only canonical Candidate v0.4 hourly closure bytes."""

    try:
        loaded: object = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        _fail("v0.4 hourly closure manifest is not valid JSON")
    mapping = _mapping(loaded, "manifest")
    _exact_fields(mapping, _MANIFEST_FIELDS, "manifest")
    instrument_mapping = _mapping(mapping.get("instrument"), "instrument")
    _exact_fields(instrument_mapping, _INSTRUMENT_FIELDS, "instrument")
    raw_closures = mapping.get("closures")
    if not isinstance(raw_closures, list):
        _fail("v0.4 hourly closure list is invalid")

    closures: list[V04ExchangeClosure] = []
    for raw_closure in cast(list[object], raw_closures):
        item = _mapping(raw_closure, "entry")
        _exact_fields(item, _CLOSURE_FIELDS, "entry")
        closures.append(
            V04ExchangeClosure(
                closure_id=_string(item, "closure_id"),
                canonical_gap_start=_parse_utc(
                    _string(item, "canonical_gap_start"), "canonical_gap_start"
                ),
                resumed_open=_parse_utc(_string(item, "resumed_open"), "resumed_open"),
                unavailable_candle_count=_integer(item, "unavailable_candle_count"),
                fully_missing_start=_parse_utc(
                    _string(item, "fully_missing_start"), "fully_missing_start"
                ),
                fully_missing_candle_count=_integer(item, "fully_missing_candle_count"),
                reason_code=_string(item, "reason_code"),
                governance_reference=_string(item, "governance_reference"),
                partial_candle=_load_partial(item.get("partial_candle")),
            )
        )

    try:
        manifest = V04ExchangeClosureManifest(
            schema_version=_string(mapping, "schema_version"),
            provider=_string(mapping, "provider"),
            instrument=Instrument(
                _string(instrument_mapping, "symbol"),
                _string(instrument_mapping, "base_asset"),
                _string(instrument_mapping, "quote_asset"),
            ),
            timeframe=Timeframe(_string(mapping, "timeframe")),
            start_time=_parse_utc(_string(mapping, "start_time"), "start_time"),
            end_time=_parse_utc(_string(mapping, "end_time"), "end_time"),
            source_manifest_sha256=_string(mapping, "source_manifest_sha256"),
            closures=tuple(closures),
        )
    except ValueError as error:
        raise DatasetHandoffError("v0.4 hourly closure values are invalid") from error
    if serialize_v0_4_closure_manifest(manifest) != raw:
        _fail("v0.4 hourly closure encoding is not canonical")
    return manifest


def _derive_hourly_closure(source: ExchangeClosure) -> V04ExchangeClosure:
    partial = source.partial_candle
    containing_open = _hour_open(partial.actual_close_time)
    expected_close = containing_open + _ONE_HOUR - _ONE_MILLISECOND
    if partial.actual_close_time > expected_close:
        _fail("v0.4 source interruption cannot map to an hourly slot")

    if partial.actual_close_time < expected_close:
        gap_start = containing_open
        derived_partial = V04PartialCandleDeclaration(
            open_time=containing_open,
            actual_close_time=partial.actual_close_time,
            expected_close_time=expected_close,
            provider_row_sha256=None,
            exclusion_reason=partial.exclusion_reason,
        )
        fully_missing_start = gap_start + _ONE_HOUR
    else:
        gap_start = containing_open + _ONE_HOUR
        derived_partial = None
        fully_missing_start = gap_start

    if source.resumed_open <= gap_start:
        _fail("v0.4 derived hourly closure interval is not positive")
    if source.resumed_open != _hour_open(source.resumed_open):
        _fail("v0.4 source resumption is not hourly aligned")

    unavailable = (source.resumed_open - gap_start) // _ONE_HOUR
    fully_missing = (source.resumed_open - fully_missing_start) // _ONE_HOUR
    return V04ExchangeClosure(
        closure_id=source.closure_id,
        canonical_gap_start=gap_start,
        resumed_open=source.resumed_open,
        unavailable_candle_count=unavailable,
        fully_missing_start=fully_missing_start,
        fully_missing_candle_count=fully_missing,
        reason_code=source.reason_code,
        governance_reference=source.governance_reference,
        partial_candle=derived_partial,
    )


def build_v0_4_closure_manifest(
    project_root: Path,
) -> tuple[V04ExchangeClosureManifest, bytes]:
    """Derive the exact hourly outage contract from frozen 4h source evidence."""

    source, source_raw = load_fixed_btcusdt_closure_manifest(project_root)
    if source.schema_version != "exchange-closure-manifest-v3":
        _fail("v0.4 requires the exact frozen v3 closure source")
    if source.timeframe is not Timeframe.H4:
        _fail("v0.4 closure source must remain the frozen 4h evidence")
    if source.start_time != V04_STAGE1_START:
        _fail("v0.4 Stage 1 start boundary changed")
    if source.end_time > V04_STAGE1_END_EXCLUSIVE:
        _fail("v0.4 source closure window exceeds the locked cutoff")

    manifest = V04ExchangeClosureManifest(
        schema_version=_V04_CLOSURE_SCHEMA,
        provider=source.provider,
        instrument=source.instrument,
        timeframe=Timeframe.H1,
        start_time=V04_STAGE1_START,
        end_time=V04_STAGE1_END_EXCLUSIVE,
        source_manifest_sha256=hashlib.sha256(source_raw).hexdigest(),
        closures=tuple(_derive_hourly_closure(item) for item in source.closures),
    )
    raw = serialize_v0_4_closure_manifest(manifest)
    return manifest, raw


__all__ = [
    "V04ExchangeClosure",
    "V04ExchangeClosureManifest",
    "V04PartialCandleDeclaration",
    "V04_STAGE1_END_EXCLUSIVE",
    "V04_STAGE1_START",
    "build_v0_4_closure_manifest",
    "load_v0_4_closure_manifest",
    "serialize_v0_4_closure_manifest",
]
