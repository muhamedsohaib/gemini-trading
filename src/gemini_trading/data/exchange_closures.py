"""Canonical contracts for source-controlled exchange-closure declarations."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Never, cast

from gemini_trading.data.errors import CandleValidationError
from gemini_trading.domain.instrument import Instrument
from gemini_trading.domain.timeframe import Timeframe

_SCHEMA_VERSION = "exchange-closure-manifest-v1"
_FIXED_PATH = Path("config/market-data/sealed-btcusdt-4h-exchange-closures.json")
_FIXED_SHA256 = "ea1dcb5ec5c8bb6cdb16baa51a6a4f38af2bc9d5d5a9657f746d6411eb3975c1"
_MANIFEST_FIELDS = {
    "schema_version",
    "provider",
    "instrument",
    "timeframe",
    "start_time",
    "end_time",
    "closures",
}
_INSTRUMENT_FIELDS = {"symbol", "base_asset", "quote_asset"}
_CLOSURE_FIELDS = {
    "closure_id",
    "missing_start",
    "resumed_open",
    "missing_candle_count",
    "reason_code",
    "governance_reference",
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
    return value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _aligned(value: datetime, timeframe: Timeframe) -> bool:
    epoch = datetime(1970, 1, 1, tzinfo=UTC)
    return (value - epoch) % timeframe.duration == timedelta(0)


def _require_utc(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        _fail(f"exchange closure manifest {field_name} must be UTC")


@dataclass(frozen=True, slots=True)
class ExchangeClosure:
    """One exact interval where provider candles are absent because trading was closed."""

    closure_id: str
    missing_start: datetime
    resumed_open: datetime
    missing_candle_count: int
    reason_code: str
    governance_reference: str

    def __post_init__(self) -> None:
        if not self.closure_id.strip():
            _fail("exchange closure ID must not be empty")
        if not self.reason_code.strip() or not self.governance_reference.strip():
            _fail("exchange closure governance fields must not be empty")
        _require_utc(self.missing_start, "missing_start")
        _require_utc(self.resumed_open, "resumed_open")
        if self.resumed_open <= self.missing_start:
            _fail("exchange closure interval must be positive")
        if isinstance(self.missing_candle_count, bool) or self.missing_candle_count < 1:
            _fail("exchange closure missing-candle count must be positive")


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

    def __post_init__(self) -> None:
        if self.schema_version != _SCHEMA_VERSION:
            _fail("unsupported exchange closure manifest schema")
        if not self.provider.strip():
            _fail("exchange closure provider must not be empty")
        _require_utc(self.start_time, "start_time")
        _require_utc(self.end_time, "end_time")
        if self.end_time <= self.start_time:
            _fail("exchange closure request window must be positive")
        if not self.closures:
            _fail("exchange closure manifest must contain a closure")

        closure_ids = tuple(item.closure_id for item in self.closures)
        if len(closure_ids) != len(set(closure_ids)):
            _fail("duplicate exchange closure ID")

        starts = tuple(item.missing_start for item in self.closures)
        if starts != tuple(sorted(starts)):
            _fail("exchange closure entries must be ordered")

        previous: ExchangeClosure | None = None
        for closure in self.closures:
            if not _aligned(closure.missing_start, self.timeframe) or not _aligned(
                closure.resumed_open, self.timeframe
            ):
                _fail("exchange closure boundaries must be timeframe aligned")
            if not (
                self.start_time <= closure.missing_start < closure.resumed_open <= self.end_time
            ):
                _fail("exchange closure is outside the request window")
            expected_count = (
                closure.resumed_open - closure.missing_start
            ) // self.timeframe.duration
            if expected_count != closure.missing_candle_count:
                _fail("exchange closure missing-candle count mismatch")
            if previous is not None and closure.missing_start <= previous.resumed_open:
                _fail("exchange closure entries overlap or touch")
            previous = closure


def _instrument_payload(instrument: Instrument) -> dict[str, object]:
    return {
        "symbol": instrument.symbol,
        "base_asset": instrument.base_asset,
        "quote_asset": instrument.quote_asset,
    }


def _closure_payload(closure: ExchangeClosure) -> dict[str, object]:
    return {
        "closure_id": closure.closure_id,
        "missing_start": _format_datetime(closure.missing_start),
        "resumed_open": _format_datetime(closure.resumed_open),
        "missing_candle_count": closure.missing_candle_count,
        "reason_code": closure.reason_code,
        "governance_reference": closure.governance_reference,
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
        "closures": [_closure_payload(item) for item in manifest.closures],
    }
    serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return f"{serialized}\n".encode()


def load_exchange_closure_manifest(raw: bytes) -> ExchangeClosureManifest:
    """Parse canonical closure bytes and reject unsupported fields or encodings."""

    try:
        loaded: object = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        _fail("exchange closure manifest is not valid JSON")
    mapping = _mapping(loaded, "manifest")
    _exact_fields(mapping, _MANIFEST_FIELDS, "manifest")

    instrument_mapping = _mapping(mapping.get("instrument"), "instrument")
    _exact_fields(instrument_mapping, _INSTRUMENT_FIELDS, "instrument")
    raw_closures = mapping.get("closures")
    if not isinstance(raw_closures, list):
        _fail("exchange closure manifest closures field is invalid")

    closures: list[ExchangeClosure] = []
    for raw_closure in cast(list[object], raw_closures):
        closure_mapping = _mapping(raw_closure, "entry")
        _exact_fields(closure_mapping, _CLOSURE_FIELDS, "entry")
        closures.append(
            ExchangeClosure(
                closure_id=_string(closure_mapping, "closure_id"),
                missing_start=_utc(_string(closure_mapping, "missing_start"), "missing_start"),
                resumed_open=_utc(_string(closure_mapping, "resumed_open"), "resumed_open"),
                missing_candle_count=_integer(closure_mapping, "missing_candle_count"),
                reason_code=_string(closure_mapping, "reason_code"),
                governance_reference=_string(closure_mapping, "governance_reference"),
            )
        )

    try:
        manifest = ExchangeClosureManifest(
            schema_version=_string(mapping, "schema_version"),
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
        )
    except ValueError as error:
        raise CandleValidationError("exchange closure manifest values are invalid") from error

    if serialize_exchange_closure_manifest(manifest) != raw:
        _fail("exchange closure manifest encoding is not canonical")
    return manifest


def load_fixed_btcusdt_closure_manifest(
    project_root: Path,
) -> tuple[ExchangeClosureManifest, bytes]:
    """Load the single approved source-controlled closure declaration."""

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
    "load_exchange_closure_manifest",
    "load_fixed_btcusdt_closure_manifest",
    "serialize_exchange_closure_manifest",
]
