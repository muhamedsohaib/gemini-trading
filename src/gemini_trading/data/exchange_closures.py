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

_SCHEMA_VERSION = "exchange-closure-manifest-v2"
_FIXED_PATH = Path("config/market-data/sealed-btcusdt-4h-exchange-closures.json")
_FIXED_SHA256 = (
    "cdd89840b30b4877d07c7be05cbc4f7615dd974f865ee0e922c933b675dfe599"  # pragma: allowlist secret
)
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
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
    """One exact provider row that closed before its declared timeframe boundary."""

    open_time: datetime
    actual_close_time: datetime
    expected_close_time: datetime
    provider_row_sha256: str
    exclusion_reason: str

    def __post_init__(self) -> None:
        _require_utc(self.open_time, "partial candle open_time")
        _require_utc(self.actual_close_time, "partial candle actual_close_time")
        _require_utc(self.expected_close_time, "partial candle expected_close_time")
        if not self.open_time < self.actual_close_time < self.expected_close_time:
            _fail("exchange closure partial candle boundaries are invalid")
        if _SHA256_PATTERN.fullmatch(self.provider_row_sha256) is None:
            _fail("exchange closure partial candle provider-row SHA-256 is invalid")
        if not self.exclusion_reason.strip():
            _fail("exchange closure partial candle exclusion reason must not be empty")


@dataclass(frozen=True, slots=True)
class ExchangeClosure:
    """One exact canonical outage containing an excluded partial slot and absent slots."""

    closure_id: str
    canonical_gap_start: datetime
    resumed_open: datetime
    unavailable_candle_count: int
    fully_missing_start: datetime
    fully_missing_candle_count: int
    reason_code: str
    governance_reference: str
    partial_candle: PartialCandleDeclaration

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
        if isinstance(self.fully_missing_candle_count, bool) or self.fully_missing_candle_count < 1:
            _fail("exchange closure fully-missing candle count must be positive")

    @property
    def missing_start(self) -> datetime:
        """Compatibility alias used by v2 segment validation until v3 migration."""

        return self.fully_missing_start

    @property
    def missing_candle_count(self) -> int:
        """Compatibility alias used by v2 evidence until v3 migration."""

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
            if closure.partial_candle.open_time != closure.canonical_gap_start:
                _fail("exchange closure partial candle does not match canonical gap start")

            expected_close = (
                closure.canonical_gap_start + self.timeframe.duration - timedelta(milliseconds=1)
            )
            if closure.partial_candle.expected_close_time != expected_close:
                _fail("exchange closure partial candle expected close mismatch")
            if closure.fully_missing_start != closure.canonical_gap_start + self.timeframe.duration:
                _fail("exchange closure fully missing start must follow the partial slot")

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
            if closure.unavailable_candle_count != closure.fully_missing_candle_count + 1:
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
        "partial_candle": _partial_payload(closure.partial_candle),
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
    """Parse canonical v2 closure bytes and reject unsupported fields or encodings."""

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

    closure_mappings = [
        _mapping(raw_closure, "entry") for raw_closure in cast(list[object], raw_closures)
    ]
    raw_ids = tuple(_string(item, "closure_id") for item in closure_mappings)
    if len(raw_ids) != len(set(raw_ids)):
        _fail("duplicate exchange closure ID")

    closures: list[ExchangeClosure] = []
    for closure_mapping in closure_mappings:
        _exact_fields(closure_mapping, _CLOSURE_FIELDS, "entry")
        partial_mapping = _mapping(closure_mapping.get("partial_candle"), "partial candle")
        _exact_fields(partial_mapping, _PARTIAL_FIELDS, "partial candle")
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
                partial_candle=PartialCandleDeclaration(
                    open_time=_utc(_string(partial_mapping, "open_time"), "partial open_time"),
                    actual_close_time=_utc(
                        _string(partial_mapping, "actual_close_time"),
                        "partial actual_close_time",
                    ),
                    expected_close_time=_utc(
                        _string(partial_mapping, "expected_close_time"),
                        "partial expected_close_time",
                    ),
                    provider_row_sha256=_string(partial_mapping, "provider_row_sha256"),
                    exclusion_reason=_string(partial_mapping, "exclusion_reason"),
                ),
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
    "PartialCandleDeclaration",
    "load_exchange_closure_manifest",
    "load_fixed_btcusdt_closure_manifest",
    "serialize_exchange_closure_manifest",
]
