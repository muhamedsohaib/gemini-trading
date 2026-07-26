"""Canonical contracts for approved exchange-closure evidence."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast

from gemini_trading.data.errors import CandleValidationError
from gemini_trading.domain.instrument import Instrument
from gemini_trading.domain.time import require_utc
from gemini_trading.domain.timeframe import Timeframe
from gemini_trading.research.serialization import canonical_json_bytes

_SCHEMA_VERSION = "exchange-closure-manifest-v1"
_PROVIDER = "binance_spot"
_INSTRUMENT = Instrument("BTCUSDT", "BTC", "USDT")
_TIMEFRAME = Timeframe.H4
_START_TIME = datetime(2018, 1, 1, tzinfo=UTC)
_END_TIME = datetime(2026, 7, 1, tzinfo=UTC)
_FIXED_PATH = Path("config/market-data/sealed-btcusdt-4h-exchange-closures.json")
_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
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


def _exact_fields(mapping: dict[str, object], expected: set[str], description: str) -> None:
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
        raise CandleValidationError(f"exchange closure {field_name} must be UTC")
    try:
        parsed = datetime.fromisoformat(f"{value[:-1]}+00:00")
        require_utc(parsed, field_name)
    except ValueError:
        raise CandleValidationError(f"exchange closure {field_name} must be valid UTC") from None
    return parsed.astimezone(UTC)


@dataclass(frozen=True, slots=True)
class ExchangeClosure:
    """One approved interval with no authentic provider candles."""

    closure_id: str
    missing_start: datetime
    resumed_open: datetime
    missing_candle_count: int
    reason_code: str
    governance_reference: str

    def __post_init__(self) -> None:
        for value, field_name in (
            (self.closure_id, "closure_id"),
            (self.reason_code, "reason_code"),
            (self.governance_reference, "governance_reference"),
        ):
            if _ID_PATTERN.fullmatch(value) is None:
                raise CandleValidationError(f"invalid exchange closure {field_name}")
        require_utc(self.missing_start, "missing_start")
        require_utc(self.resumed_open, "resumed_open")
        if self.resumed_open <= self.missing_start:
            raise CandleValidationError("exchange closure resumed_open must follow missing_start")
        if isinstance(self.missing_candle_count, bool) or self.missing_candle_count < 1:
            raise CandleValidationError("exchange closure missing-candle count must be positive")


@dataclass(frozen=True, slots=True)
class ExchangeClosureManifest:
    """Exact source-controlled closure declaration for the sealed BTCUSDT window."""

    schema_version: str
    provider: str
    instrument: Instrument
    timeframe: Timeframe
    start_time: datetime
    end_time: datetime
    closures: tuple[ExchangeClosure, ...]

    def __post_init__(self) -> None:
        if self.schema_version != _SCHEMA_VERSION:
            raise CandleValidationError("unsupported exchange closure manifest schema")
        if self.provider != _PROVIDER or self.instrument != _INSTRUMENT:
            raise CandleValidationError("exchange closure manifest market identity mismatch")
        if self.timeframe is not _TIMEFRAME:
            raise CandleValidationError("exchange closure manifest timeframe mismatch")
        if self.start_time != _START_TIME or self.end_time != _END_TIME:
            raise CandleValidationError("exchange closure manifest request window mismatch")
        if not self.closures:
            raise CandleValidationError("exchange closure manifest must declare a closure")

        closure_ids = tuple(closure.closure_id for closure in self.closures)
        if len(closure_ids) != len(set(closure_ids)):
            raise CandleValidationError("duplicate exchange closure ID")

        starts = tuple(closure.missing_start for closure in self.closures)
        if starts != tuple(sorted(starts)):
            raise CandleValidationError("exchange closures must be ordered")

        previous: ExchangeClosure | None = None
        for closure in self.closures:
            if not self.start_time < closure.missing_start < closure.resumed_open <= self.end_time:
                raise CandleValidationError("exchange closure is outside the request window")
            for boundary in (closure.missing_start, closure.resumed_open):
                if (boundary - self.start_time) % self.timeframe.duration != timedelta(0):
                    raise CandleValidationError("exchange closure boundary is not timeframe aligned")
            duration = closure.resumed_open - closure.missing_start
            if duration % self.timeframe.duration != timedelta(0):
                raise CandleValidationError("exchange closure duration is not timeframe aligned")
            expected_count = duration // self.timeframe.duration
            if expected_count != closure.missing_candle_count:
                raise CandleValidationError("exchange closure missing-candle count mismatch")
            if previous is not None:
                if closure.missing_start < previous.resumed_open:
                    raise CandleValidationError("exchange closure intervals overlap")
                if closure.missing_start == previous.resumed_open:
                    raise CandleValidationError("exchange closure intervals touch")
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
        "missing_start": _format_utc(closure.missing_start),
        "resumed_open": _format_utc(closure.resumed_open),
        "missing_candle_count": closure.missing_candle_count,
        "reason_code": closure.reason_code,
        "governance_reference": closure.governance_reference,
    }


def serialize_exchange_closure_manifest(manifest: ExchangeClosureManifest) -> bytes:
    """Serialize the exact closure contract using canonical project JSON."""

    return canonical_json_bytes(
        {
            "schema_version": manifest.schema_version,
            "provider": manifest.provider,
            "instrument": _instrument_payload(manifest.instrument),
            "timeframe": manifest.timeframe.value,
            "start_time": _format_utc(manifest.start_time),
            "end_time": _format_utc(manifest.end_time),
            "closures": [_closure_payload(closure) for closure in manifest.closures],
        }
    )


def load_exchange_closure_manifest(raw: bytes) -> ExchangeClosureManifest:
    """Parse exact canonical closure bytes and reject alternate representations."""

    try:
        loaded: object = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise CandleValidationError("invalid exchange closure manifest JSON") from None
    mapping = _mapping(loaded, "exchange closure manifest")
    _exact_fields(mapping, _MANIFEST_FIELDS, "exchange closure manifest")

    instrument_mapping = _mapping(mapping.get("instrument"), "exchange closure instrument")
    _exact_fields(instrument_mapping, _INSTRUMENT_FIELDS, "exchange closure instrument")
    try:
        instrument = Instrument(
            _string(instrument_mapping, "symbol", "instrument"),
            _string(instrument_mapping, "base_asset", "instrument"),
            _string(instrument_mapping, "quote_asset", "instrument"),
        )
        timeframe = Timeframe(_string(mapping, "timeframe", "manifest"))
    except ValueError:
        raise CandleValidationError("exchange closure manifest market identity is invalid") from None

    raw_closures = mapping.get("closures")
    if not isinstance(raw_closures, list):
        raise CandleValidationError("invalid exchange closure manifest field: closures")
    closures: list[ExchangeClosure] = []
    for raw_closure in cast(list[object], raw_closures):
        closure_mapping = _mapping(raw_closure, "exchange closure")
        _exact_fields(closure_mapping, _CLOSURE_FIELDS, "exchange closure")
        closures.append(
            ExchangeClosure(
                closure_id=_string(closure_mapping, "closure_id", "closure"),
                missing_start=_utc(
                    _string(closure_mapping, "missing_start", "closure"),
                    "missing_start",
                ),
                resumed_open=_utc(
                    _string(closure_mapping, "resumed_open", "closure"),
                    "resumed_open",
                ),
                missing_candle_count=_integer(
                    closure_mapping,
                    "missing_candle_count",
                    "closure",
                ),
                reason_code=_string(closure_mapping, "reason_code", "closure"),
                governance_reference=_string(
                    closure_mapping,
                    "governance_reference",
                    "closure",
                ),
            )
        )

    manifest = ExchangeClosureManifest(
        schema_version=_string(mapping, "schema_version", "manifest"),
        provider=_string(mapping, "provider", "manifest"),
        instrument=instrument,
        timeframe=timeframe,
        start_time=_utc(_string(mapping, "start_time", "manifest"), "start_time"),
        end_time=_utc(_string(mapping, "end_time", "manifest"), "end_time"),
        closures=tuple(closures),
    )
    if serialize_exchange_closure_manifest(manifest) != raw:
        raise CandleValidationError("exchange closure manifest encoding is not canonical")
    return manifest


def load_fixed_btcusdt_closure_manifest(
    project_root: Path,
) -> tuple[ExchangeClosureManifest, bytes]:
    """Load the only approved closure manifest from its fixed repository path."""

    path = project_root.resolve(strict=False) / _FIXED_PATH
    try:
        raw = path.read_bytes()
    except OSError:
        raise CandleValidationError("fixed exchange closure manifest is unavailable") from None
    return load_exchange_closure_manifest(raw), raw


__all__ = [
    "ExchangeClosure",
    "ExchangeClosureManifest",
    "load_exchange_closure_manifest",
    "load_fixed_btcusdt_closure_manifest",
    "serialize_exchange_closure_manifest",
]
