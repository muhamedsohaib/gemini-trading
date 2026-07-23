"""Strict verified loading of canonical datasets for deterministic research."""

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import cast

from gemini_trading.data.datasets.canonical_writer import (
    dataset_id,
    serialize_candles,
    serialize_dataset_manifest,
)
from gemini_trading.data.storage.local_immutable import LocalImmutableStore
from gemini_trading.data.validation.candles import validate_candle_sequence
from gemini_trading.domain.candle import Candle
from gemini_trading.domain.dataset import DatasetManifest, RetrievalRequest
from gemini_trading.domain.instrument import Instrument
from gemini_trading.domain.time import require_utc
from gemini_trading.domain.timeframe import Timeframe
from gemini_trading.research.errors import DatasetVerificationError

_MANIFEST_FIELDS = {
    "schema_version",
    "dataset_id",
    "provider",
    "instrument",
    "timeframe",
    "start_time",
    "end_time",
    "first_open_time",
    "last_open_time",
    "candle_count",
    "canonical_sha256",
}
_INSTRUMENT_FIELDS = {"symbol", "base_asset", "quote_asset"}
_CANDLE_FIELDS = {
    "symbol",
    "base_asset",
    "quote_asset",
    "timeframe",
    "open_time",
    "close_time",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "completed",
    "source_provider",
}


@dataclass(frozen=True, slots=True)
class VerifiedDataset:
    """A fully verified canonical dataset ready for chronological research replay."""

    manifest: DatasetManifest
    candles: tuple[Candle, ...]
    canonical_bytes: bytes


def _mapping(value: object, description: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise DatasetVerificationError(f"{description} must be a JSON object")
    raw = cast(dict[object, object], value)
    if not all(isinstance(key, str) for key in raw):
        raise DatasetVerificationError(f"{description} keys must be strings")
    return cast(dict[str, object], raw)


def _exact_fields(mapping: dict[str, object], expected: set[str], description: str) -> None:
    if set(mapping) != expected:
        raise DatasetVerificationError(f"invalid {description} fields")


def _string(mapping: dict[str, object], key: str, description: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value:
        raise DatasetVerificationError(f"invalid {description} field: {key}")
    return value


def _integer(mapping: dict[str, object], key: str, description: str) -> int:
    value = mapping.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise DatasetVerificationError(f"invalid {description} field: {key}")
    return value


def _boolean(mapping: dict[str, object], key: str, description: str) -> bool:
    value = mapping.get(key)
    if not isinstance(value, bool):
        raise DatasetVerificationError(f"invalid {description} field: {key}")
    return value


def _utc(value: str, field_name: str) -> datetime:
    if not value.endswith("Z"):
        raise DatasetVerificationError(f"invalid UTC field: {field_name}")
    try:
        parsed = datetime.fromisoformat(f"{value[:-1]}+00:00")
        require_utc(parsed, field_name)
    except ValueError as error:
        raise DatasetVerificationError(f"invalid UTC field: {field_name}") from error
    return parsed


def _decimal(mapping: dict[str, object], key: str) -> Decimal:
    value = mapping.get(key)
    if not isinstance(value, str):
        raise DatasetVerificationError(f"invalid candle field: {key}")
    try:
        parsed = Decimal(value)
    except InvalidOperation as error:
        raise DatasetVerificationError(f"invalid candle field: {key}") from error
    if not parsed.is_finite():
        raise DatasetVerificationError(f"invalid candle field: {key}")
    return parsed


def _parse_manifest(manifest_bytes: bytes) -> DatasetManifest:
    try:
        loaded: object = json.loads(manifest_bytes.decode())
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise DatasetVerificationError("invalid dataset manifest JSON") from error
    mapping = _mapping(loaded, "dataset manifest")
    _exact_fields(mapping, _MANIFEST_FIELDS, "manifest")
    instrument_mapping = _mapping(mapping["instrument"], "manifest instrument")
    _exact_fields(instrument_mapping, _INSTRUMENT_FIELDS, "instrument")
    try:
        manifest = DatasetManifest(
            schema_version=_string(mapping, "schema_version", "manifest"),
            dataset_id=_string(mapping, "dataset_id", "manifest"),
            provider=_string(mapping, "provider", "manifest"),
            instrument=Instrument(
                _string(instrument_mapping, "symbol", "instrument"),
                _string(instrument_mapping, "base_asset", "instrument"),
                _string(instrument_mapping, "quote_asset", "instrument"),
            ),
            timeframe=Timeframe(_string(mapping, "timeframe", "manifest")),
            start_time=_utc(_string(mapping, "start_time", "manifest"), "start_time"),
            end_time=_utc(_string(mapping, "end_time", "manifest"), "end_time"),
            first_open_time=_utc(
                _string(mapping, "first_open_time", "manifest"),
                "first_open_time",
            ),
            last_open_time=_utc(
                _string(mapping, "last_open_time", "manifest"),
                "last_open_time",
            ),
            candle_count=_integer(mapping, "candle_count", "manifest"),
            canonical_sha256=_string(mapping, "canonical_sha256", "manifest"),
        )
    except ValueError as error:
        raise DatasetVerificationError("invalid dataset manifest values") from error
    if serialize_dataset_manifest(manifest) != manifest_bytes:
        raise DatasetVerificationError("dataset manifest is not canonically encoded")
    return manifest


def _parse_candle(row_bytes: bytes, manifest: DatasetManifest) -> Candle:
    try:
        loaded: object = json.loads(row_bytes.decode())
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise DatasetVerificationError("invalid canonical candle JSON") from error
    mapping = _mapping(loaded, "canonical candle")
    _exact_fields(mapping, _CANDLE_FIELDS, "candle")
    try:
        candle = Candle(
            instrument=Instrument(
                _string(mapping, "symbol", "candle"),
                _string(mapping, "base_asset", "candle"),
                _string(mapping, "quote_asset", "candle"),
            ),
            timeframe=Timeframe(_string(mapping, "timeframe", "candle")),
            open_time=_utc(_string(mapping, "open_time", "candle"), "open_time"),
            close_time=_utc(_string(mapping, "close_time", "candle"), "close_time"),
            open=_decimal(mapping, "open"),
            high=_decimal(mapping, "high"),
            low=_decimal(mapping, "low"),
            close=_decimal(mapping, "close"),
            volume=_decimal(mapping, "volume"),
            completed=_boolean(mapping, "completed", "candle"),
            source_provider=_string(mapping, "source_provider", "candle"),
        )
    except ValueError as error:
        raise DatasetVerificationError("invalid canonical candle values") from error
    if not candle.completed:
        raise DatasetVerificationError("canonical candle must be completed")
    if candle.source_provider != manifest.provider:
        raise DatasetVerificationError("canonical candle provider mismatch")
    return candle


def _parse_candles(canonical_bytes: bytes, manifest: DatasetManifest) -> tuple[Candle, ...]:
    rows = tuple(row for row in canonical_bytes.splitlines() if row)
    if not rows:
        raise DatasetVerificationError("canonical dataset contains no candles")
    return tuple(_parse_candle(row, manifest) for row in rows)


def _verify_dataset(
    dataset_id_value: str,
    manifest: DatasetManifest,
    candles: tuple[Candle, ...],
    canonical_bytes: bytes,
) -> None:
    if manifest.dataset_id != dataset_id_value:
        raise DatasetVerificationError("dataset identity mismatch")
    if hashlib.sha256(canonical_bytes).hexdigest() != manifest.canonical_sha256:
        raise DatasetVerificationError("canonical content hash mismatch")
    if dataset_id(manifest.schema_version, canonical_bytes) != dataset_id_value:
        raise DatasetVerificationError("canonical dataset identity mismatch")
    if len(candles) != manifest.candle_count:
        raise DatasetVerificationError("canonical candle count mismatch")
    if candles[0].open_time != manifest.first_open_time:
        raise DatasetVerificationError("canonical first candle mismatch")
    if candles[-1].open_time != manifest.last_open_time:
        raise DatasetVerificationError("canonical last candle mismatch")
    if serialize_candles(candles) != canonical_bytes:
        raise DatasetVerificationError("canonical candles are not canonically encoded")

    request = RetrievalRequest(
        instrument=manifest.instrument,
        timeframe=manifest.timeframe,
        start_time=manifest.start_time,
        end_time=manifest.end_time,
    )
    try:
        validate_candle_sequence(candles, request)
    except ValueError as error:
        raise DatasetVerificationError("canonical candle sequence validation failed") from error


def load_verified_dataset(
    store: LocalImmutableStore,
    dataset_id_value: str,
) -> VerifiedDataset:
    """Load and independently verify one immutable canonical dataset."""

    try:
        canonical_bytes, manifest_bytes = store.read_dataset(dataset_id_value)
        manifest = _parse_manifest(manifest_bytes)
        candles = _parse_candles(canonical_bytes, manifest)
        _verify_dataset(dataset_id_value, manifest, candles, canonical_bytes)
    except DatasetVerificationError:
        raise
    except (OSError, TypeError, ValueError) as error:
        raise DatasetVerificationError("canonical dataset could not be loaded safely") from error
    return VerifiedDataset(manifest, candles, canonical_bytes)
