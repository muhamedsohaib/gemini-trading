"""Canonical contracts for source-controlled exchange-closure declarations."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Never, cast

from gemini_trading.data.errors import CandleValidationError
from gemini_trading.domain.instrument import Instrument
from gemini_trading.domain.timeframe import Timeframe

_SCHEMA_VERSION_V3 = "exchange-closure-manifest-v3"
_SCHEMA_VERSION_V4 = "exchange-closure-manifest-v4"
_FIXED_PATH = Path("config/market-data/sealed-btcusdt-4h-exchange-closures.json")
_FIXED_SHA256 = (
    "a028bd367ac51b85cca3fab24a28b794fc35ea2d9f73b6f39d681eafa66a31f5"  # pragma: allowlist secret
)
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_MANIFEST_FIELDS_V3 = {
    "schema_version",
    "provider",
    "instrument",
    "timeframe",
    "start_time",
    "end_time",
    "closures",
}
_MANIFEST_FIELDS_V4 = {*_MANIFEST_FIELDS_V3, "source_manifest_sha256"}
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
    raise CandleValidationError(message)


def _mapping(value: object, description: str) -> dict[str, object]:
    if not isinstance(value, dict):
        _fail(f"exchange closure {description} must be an object")
    raw = cast(dict[object, object], value)
    if not all(isinstance(key, str) for key in raw):
        _fail(f"exchange closure {description} fields are invalid")
    return cast(dict[str, object], raw)


def _exact_fields(mapping: dict[str, object], expected: set[str], description: str) -> None:
    if set(mapping) != expected:
        _fail(f"exchange closure {description} fields are invalid")


def _string(mapping: dict[str, object], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value:
        _fail(f"exchange closure field is invalid: {key}")
    return value


def _nullable_sha256(mapping: dict[str, object], key: str) -> str | None:
    value = mapping.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or _SHA256_PATTERN.fullmatch(value) is None:
        _fail(f"exchange closure field is invalid: {key}")
    return value


def _integer(mapping: dict[str, object], key: str) -> int:
    value = mapping.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        _fail(f"exchange closure field is invalid: {key}")
    return value


def _utc(value: str, field_name: str) -> datetime:
    if not value.endswith("Z"):
        _fail(f"exchange closure {field_name} must be UTC")
    try:
        parsed = datetime.fromisoformat(f"{value[:-1]}+00:00")
    except ValueError:
        _fail(f"exchange closure {field_name} must be valid UTC")
    if parsed.utcoffset() != UTC.utcoffset(parsed):
        _fail(f"exchange closure {field_name} must be UTC")
    return parsed.astimezone(UTC)


def _format_datetime(value: datetime) -> str:
    timespec = "milliseconds" if value.microsecond else "seconds"
    return value.astimezone(UTC).isoformat(timespec=timespec).replace("+00:00", "Z")


def _aligned(value: datetime, timeframe: Timeframe) -> bool:
    epoch = datetime(1970, 1, 1, tzinfo=UTC)
    return (value - epoch) % timeframe.duration == timedelta(0)


def _require_utc(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        _fail(f"exchange closure manifest {field_name} must be UTC")


@dataclass(frozen=True, slots=True)
class PartialCandleDeclaration:
    """One provider row that closed before its declared timeframe boundary."""

    open_time: datetime
    actual_close_time: datetime
    expected_close_time: datetime
    provider_row_sha256: str | None
    exclusion_reason: str

    def __post_init__(self) -> None:
        _require_utc(self.open_time, "partial candle open_time")
        _require_utc(self.actual_close_time, "partial candle actual_close_time")
        _require_utc(self.expected_close_time, "partial candle expected_close_time")
        if not self.open_time < self.actual_close_time < self.expected_close_time:
            _fail("exchange closure partial candle boundaries are invalid")
        if (
            self.provider_row_sha256 is not None
            and _SHA256_PATTERN.fullmatch(self.provider_row_sha256) is None
        ):
            _fail("exchange closure partial candle provider-row SHA-256 is invalid")
        if not self.exclusion_reason.strip():
            _fail("exchange closure partial candle exclusion reason must not be empty")


@dataclass(frozen=True, slots=True)
class ExchangeClosure:
    """One exact canonical outage containing unavailable candle slots."""

    closure_id: str
    canonical_gap_start: datetime
    resumed_open: datetime
    unavailable_candle_count: int
    fully_missing_start: datetime
    fully_missing_candle_count: int
    reason_code: str
    governance_reference: str
    partial_candle: PartialCandleDeclaration | None

    def __post_init__(self) -> None:
        if not self.closure_id.strip():
            _fail("exchange closure ID must not be empty")
        if not self.reason_code.strip() or not self.governance_reference.strip():
            _fail("exchange closure governance fields must not be empty")
        _require_utc(self.canonical_gap_start, "canonical_gap_start")
        _require_utc(self.fully_missing_start, "fully_missing_start")
        _require_utc(self.resumed_open, "resumed_open")
        if self.resumed_open <= self.canonical_gap_start:
            _fail("exchange closure interval must be positive")
        if isinstance(self.unavailable_candle_count, bool) or self.unavailable_candle_count < 1:
            _fail("exchange closure unavailable-candle count must be positive")
        if isinstance(self.fully_missing_candle_count, bool) or self.fully_missing_candle_count < 0:
            _fail("exchange closure fully-missing candle count must be nonnegative")

    @property
    def missing_start(self) -> datetime:
        """Compatibility alias used by segment validation."""

        return self.fully_missing_start

    @property
    def missing_candle_count(self) -> int:
        """Compatibility alias used by existing evidence consumers."""

        return self.fully_missing_candle_count


@dataclass(frozen=True, slots=True)
class ExchangeClosureManifest:
    """Ordered exchange-closure declarations for one exact retrieval window."""

    schema_version: str
    provider: str
    instrument: Instrument
    timeframe: Timeframe
    start_time: datetime
    end_time: datetime
    closures: tuple[ExchangeClosure, ...]
    source_manifest_sha256: str | None = None

    def __post_init__(self) -> None:
        if self.schema_version not in {_SCHEMA_VERSION_V3, _SCHEMA_VERSION_V4}:
            _fail("unsupported exchange closure manifest schema")
        if not self.provider.strip():
            _fail("exchange closure provider must not be empty")
        _require_utc(self.start_time, "start_time")
        _require_utc(self.end_time, "end_time")
        if self.end_time <= self.start_time:
            _fail("exchange closure request window must be positive")
        if not self.closures:
            _fail("exchange closure manifest must contain a closure")

        if self.schema_version == _SCHEMA_VERSION_V3:
            if self.source_manifest_sha256 is not None:
                _fail("v3 exchange closure manifest cannot reference a source manifest")
            if any(item.partial_candle is None for item in self.closures):
                _fail("v3 exchange closure manifest requires one partial candle per closure")
            if any(
                item.partial_candle is not None and item.partial_candle.provider_row_sha256 is None
                for item in self.closures
            ):
                _fail("v3 exchange closure partial rows require provider-row SHA-256")
        else:
            if self.timeframe is not Timeframe.H1:
                _fail("v4 exchange closure manifest requires 1h timeframe")
            if (
                self.source_manifest_sha256 is None
                or _SHA256_PATTERN.fullmatch(self.source_manifest_sha256) is None
            ):
                _fail("v4 exchange closure source-manifest SHA-256 is invalid")

        closure_ids = tuple(item.closure_id for item in self.closures)
        if len(closure_ids) != len(set(closure_ids)):
            _fail("duplicate exchange closure ID")

        partials = tuple(
            item.partial_candle for item in self.closures if item.partial_candle is not None
        )
        partial_opens = tuple(item.open_time for item in partials)
        if len(partial_opens) != len(set(partial_opens)):
            _fail("duplicate exchange closure partial candle open")

        provider_row_digests = tuple(
            item.provider_row_sha256 for item in partials if item.provider_row_sha256 is not None
        )
        if len(provider_row_digests) != len(set(provider_row_digests)):
            _fail("duplicate exchange closure provider-row SHA-256")

        starts = tuple(item.canonical_gap_start for item in self.closures)
        if starts != tuple(sorted(starts)):
            _fail("exchange closure entries must be ordered")

        previous: ExchangeClosure | None = None
        for closure in self.closures:
            if (
                not _aligned(closure.canonical_gap_start, self.timeframe)
                or not _aligned(closure.fully_missing_start, self.timeframe)
                or not _aligned(closure.resumed_open, self.timeframe)
            ):
                _fail("exchange closure boundaries must be timeframe aligned")
            if not (
                self.start_time
                <= closure.canonical_gap_start
                < closure.resumed_open
                <= self.end_time
            ):
                _fail("exchange closure is outside the request window")

            expected_unavailable = (
                closure.resumed_open - closure.canonical_gap_start
            ) // self.timeframe.duration
            if expected_unavailable != closure.unavailable_candle_count:
                _fail("exchange closure unavailable-candle count mismatch")
            expected_fully_missing = (
                closure.resumed_open - closure.fully_missing_start
            ) // self.timeframe.duration
            if expected_fully_missing != closure.fully_missing_candle_count:
                _fail("exchange closure fully-missing candle count mismatch")

            partial = closure.partial_candle
            if partial is not None:
                if partial.open_time != closure.canonical_gap_start:
                    _fail("exchange closure partial candle does not match canonical gap start")
                expected_close = (
                    closure.canonical_gap_start
                    + self.timeframe.duration
                    - timedelta(milliseconds=1)
                )
                if partial.expected_close_time != expected_close:
                    _fail("exchange closure partial candle expected close mismatch")
                if closure.fully_missing_start != (
                    closure.canonical_gap_start + self.timeframe.duration
                ):
                    _fail("exchange closure fully missing start must follow the partial slot")
                if closure.unavailable_candle_count != closure.fully_missing_candle_count + 1:
                    _fail("exchange closure candle counts are inconsistent")
            else:
                if self.schema_version != _SCHEMA_VERSION_V4:
                    _fail("exchange closure partial candle is required")
                if closure.fully_missing_start != closure.canonical_gap_start:
                    _fail("full-missing-only closure must start at canonical gap start")
                if closure.fully_missing_candle_count < 1:
                    _fail("full-missing-only closure must contain a missing candle")
                if closure.unavailable_candle_count != closure.fully_missing_candle_count:
                    _fail("exchange closure candle counts are inconsistent")

            if previous is not None and closure.canonical_gap_start <= previous.resumed_open:
                _fail("exchange closure entries overlap or touch")
            previous = closure


def _instrument_payload(instrument: Instrument) -> dict[str, object]:
    return {
        "symbol": instrument.symbol,
        "base_asset": instrument.base_asset,
        "quote_asset": instrument.quote_asset,
    }


def _partial_payload(partial: PartialCandleDeclaration) -> dict[str, object]:
    return {
        "open_time": _format_datetime(partial.open_time),
        "actual_close_time": _format_datetime(partial.actual_close_time),
        "expected_close_time": _format_datetime(partial.expected_close_time),
        "provider_row_sha256": partial.provider_row_sha256,
        "exclusion_reason": partial.exclusion_reason,
    }


def _closure_payload(closure: ExchangeClosure) -> dict[str, object]:
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


def serialize_exchange_closure_manifest(manifest: ExchangeClosureManifest) -> bytes:
    """Serialize one exact closure manifest as canonical compact JSON."""

    payload: dict[str, object] = {
        "schema_version": manifest.schema_version,
        "provider": manifest.provider,
        "instrument": _instrument_payload(manifest.instrument),
        "timeframe": manifest.timeframe.value,
        "start_time": _format_datetime(manifest.start_time),
        "end_time": _format_datetime(manifest.end_time),
    }
    if manifest.schema_version == _SCHEMA_VERSION_V4:
        payload["source_manifest_sha256"] = manifest.source_manifest_sha256
    payload["closures"] = [_closure_payload(item) for item in manifest.closures]
    serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return f"{serialized}\n".encode()


def _load_partial(
    mapping: dict[str, object], schema_version: str
) -> PartialCandleDeclaration | None:
    raw_partial = mapping.get("partial_candle")
    if raw_partial is None:
        if schema_version != _SCHEMA_VERSION_V4:
            _fail("exchange closure partial candle must be an object")
        return None
    partial_mapping = _mapping(raw_partial, "partial candle")
    _exact_fields(partial_mapping, _PARTIAL_FIELDS, "partial candle")
    provider_row_sha256 = _nullable_sha256(partial_mapping, "provider_row_sha256")
    if schema_version == _SCHEMA_VERSION_V3 and provider_row_sha256 is None:
        _fail("exchange closure partial candle provider-row SHA-256 is invalid")
    return PartialCandleDeclaration(
        open_time=_utc(_string(partial_mapping, "open_time"), "partial open_time"),
        actual_close_time=_utc(
            _string(partial_mapping, "actual_close_time"),
            "partial actual_close_time",
        ),
        expected_close_time=_utc(
            _string(partial_mapping, "expected_close_time"),
            "partial expected_close_time",
        ),
        provider_row_sha256=provider_row_sha256,
        exclusion_reason=_string(partial_mapping, "exclusion_reason"),
    )


def load_exchange_closure_manifest(raw: bytes) -> ExchangeClosureManifest:
    """Parse canonical v3/v4 closure bytes and reject alternate encodings."""

    try:
        loaded: object = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        _fail("exchange closure manifest is not valid JSON")
    mapping = _mapping(loaded, "manifest")
    schema_version = _string(mapping, "schema_version")
    if schema_version == _SCHEMA_VERSION_V3:
        _exact_fields(mapping, _MANIFEST_FIELDS_V3, "manifest")
        source_manifest_sha256 = None
    elif schema_version == _SCHEMA_VERSION_V4:
        _exact_fields(mapping, _MANIFEST_FIELDS_V4, "manifest")
        source_manifest_sha256 = _string(mapping, "source_manifest_sha256")
    else:
        _fail("unsupported exchange closure manifest schema")

    instrument_mapping = _mapping(mapping.get("instrument"), "instrument")
    _exact_fields(instrument_mapping, _INSTRUMENT_FIELDS, "instrument")
    raw_closures = mapping.get("closures")
    if not isinstance(raw_closures, list):
        _fail("exchange closure manifest closures field is invalid")

    closure_mappings = [
        _mapping(raw_closure, "entry") for raw_closure in cast(list[object], raw_closures)
    ]
    raw_ids = tuple(_string(item, "closure_id") for item in closure_mappings)
    if len(raw_ids) != len(set(raw_ids)):
        _fail("duplicate exchange closure ID")

    closures: list[ExchangeClosure] = []
    for closure_mapping in closure_mappings:
        _exact_fields(closure_mapping, _CLOSURE_FIELDS, "entry")
        closures.append(
            ExchangeClosure(
                closure_id=_string(closure_mapping, "closure_id"),
                canonical_gap_start=_utc(
                    _string(closure_mapping, "canonical_gap_start"), "canonical_gap_start"
                ),
                resumed_open=_utc(_string(closure_mapping, "resumed_open"), "resumed_open"),
                unavailable_candle_count=_integer(closure_mapping, "unavailable_candle_count"),
                fully_missing_start=_utc(
                    _string(closure_mapping, "fully_missing_start"), "fully_missing_start"
                ),
                fully_missing_candle_count=_integer(closure_mapping, "fully_missing_candle_count"),
                reason_code=_string(closure_mapping, "reason_code"),
                governance_reference=_string(closure_mapping, "governance_reference"),
                partial_candle=_load_partial(closure_mapping, schema_version),
            )
        )

    try:
        manifest = ExchangeClosureManifest(
            schema_version=schema_version,
            provider=_string(mapping, "provider"),
            instrument=Instrument(
                _string(instrument_mapping, "symbol"),
                _string(instrument_mapping, "base_asset"),
                _string(instrument_mapping, "quote_asset"),
            ),
            timeframe=Timeframe(_string(mapping, "timeframe")),
            start_time=_utc(_string(mapping, "start_time"), "start_time"),
            end_time=_utc(_string(mapping, "end_time"), "end_time"),
            closures=tuple(closures),
            source_manifest_sha256=source_manifest_sha256,
        )
    except ValueError as error:
        raise CandleValidationError("exchange closure manifest values are invalid") from error

    if serialize_exchange_closure_manifest(manifest) != raw:
        _fail("exchange closure manifest encoding is not canonical")
    return manifest


def load_fixed_btcusdt_closure_manifest(
    project_root: Path,
) -> tuple[ExchangeClosureManifest, bytes]:
    """Load the approved source-controlled closure declarations."""

    path = Path(project_root).resolve(strict=False) / _FIXED_PATH
    try:
        raw = path.read_bytes()
    except OSError:
        _fail("fixed exchange closure manifest is unavailable")
    if hashlib.sha256(raw).hexdigest() != _FIXED_SHA256:
        _fail("fixed exchange closure manifest identity mismatch")
    return load_exchange_closure_manifest(raw), raw


__all__ = [
    "ExchangeClosure",
    "ExchangeClosureManifest",
    "PartialCandleDeclaration",
    "load_exchange_closure_manifest",
    "load_fixed_btcusdt_closure_manifest",
    "serialize_exchange_closure_manifest",
]
