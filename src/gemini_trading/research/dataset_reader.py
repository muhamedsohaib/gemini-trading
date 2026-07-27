"""Strict verified loading of canonical datasets for deterministic research."""

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import cast

from gemini_trading.data.datasets.canonical_writer import (
    dataset_id,
    dataset_id_v2,
    dataset_id_v3,
    dataset_id_v4,
    serialize_candles,
    serialize_dataset_manifest,
)
from gemini_trading.data.errors import CandleValidationError
from gemini_trading.data.exchange_closures import (
    ExchangeClosureManifest,
    load_exchange_closure_manifest,
)
from gemini_trading.data.exclusions import (
    CandleExclusionManifest,
    load_candle_exclusion_manifest,
)
from gemini_trading.data.segments import (
    CandleSegmentManifest,
    load_candle_segment_manifest,
    serialize_candle_segment_manifest,
    validate_and_segment_candle_sequence,
)
from gemini_trading.data.storage.local_immutable import LocalImmutableStore
from gemini_trading.data.validation.candles import validate_candle_sequence
from gemini_trading.domain.candle import Candle
from gemini_trading.domain.dataset import DatasetManifest, RetrievalRequest
from gemini_trading.domain.instrument import Instrument
from gemini_trading.domain.time import require_utc
from gemini_trading.domain.timeframe import Timeframe
from gemini_trading.research.errors import DatasetVerificationError

_MANIFEST_FIELDS_V1 = {
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
_MANIFEST_FIELDS_V2 = _MANIFEST_FIELDS_V1 | {
    "closure_manifest_sha256",
    "segment_manifest_sha256",
    "closure_count",
    "segment_count",
}
_MANIFEST_FIELDS_V3 = _MANIFEST_FIELDS_V2 | {
    "exclusion_manifest_sha256",
    "exclusion_count",
}
_MANIFEST_FIELDS_V4 = _MANIFEST_FIELDS_V3
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
    closure_manifest: ExchangeClosureManifest | None = None
    exclusion_manifest: CandleExclusionManifest | None = None
    segment_manifest: CandleSegmentManifest | None = None
    closure_manifest_bytes: bytes | None = None
    exclusion_manifest_bytes: bytes | None = None
    segment_manifest_bytes: bytes | None = None


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
    schema_version = _string(mapping, "schema_version", "manifest")
    expected_fields = (
        _MANIFEST_FIELDS_V4
        if schema_version == "candle-dataset-v4"
        else _MANIFEST_FIELDS_V3
        if schema_version == "candle-dataset-v3"
        else _MANIFEST_FIELDS_V2
        if schema_version == "candle-dataset-v2"
        else _MANIFEST_FIELDS_V1
    )
    _exact_fields(mapping, expected_fields, "manifest")
    instrument_mapping = _mapping(mapping["instrument"], "manifest instrument")
    _exact_fields(instrument_mapping, _INSTRUMENT_FIELDS, "instrument")
    try:
        manifest = DatasetManifest(
            schema_version=schema_version,
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
            closure_manifest_sha256=(
                _string(mapping, "closure_manifest_sha256", "manifest")
                if schema_version
                in {"candle-dataset-v2", "candle-dataset-v3", "candle-dataset-v4"}
                else None
            ),
            exclusion_manifest_sha256=(
                _string(mapping, "exclusion_manifest_sha256", "manifest")
                if schema_version in {"candle-dataset-v3", "candle-dataset-v4"}
                else None
            ),
            segment_manifest_sha256=(
                _string(mapping, "segment_manifest_sha256", "manifest")
                if schema_version
                in {"candle-dataset-v2", "candle-dataset-v3", "candle-dataset-v4"}
                else None
            ),
            closure_count=(
                _integer(mapping, "closure_count", "manifest")
                if schema_version
                in {"candle-dataset-v2", "candle-dataset-v3", "candle-dataset-v4"}
                else 0
            ),
            exclusion_count=(
                _integer(mapping, "exclusion_count", "manifest")
                if schema_version in {"candle-dataset-v3", "candle-dataset-v4"}
                else 0
            ),
            segment_count=(
                _integer(mapping, "segment_count", "manifest")
                if schema_version
                in {"candle-dataset-v2", "candle-dataset-v3", "candle-dataset-v4"}
                else 1
            ),
        )
    except ValueError as error:
        raise DatasetVerificationError("invalid dataset manifest values") from error
    if serialize_dataset_manifest(manifest) != manifest_bytes:
        raise DatasetVerificationError("dataset manifest is not canonically encoded")
    return manifest


def _verify_content_identity(
    dataset_id_value: str,
    manifest: DatasetManifest,
    canonical_bytes: bytes,
    closure_manifest_bytes: bytes | None = None,
    exclusion_manifest_bytes: bytes | None = None,
    segment_manifest_bytes: bytes | None = None,
) -> None:
    if manifest.dataset_id != dataset_id_value:
        raise DatasetVerificationError("dataset identity mismatch")
    if hashlib.sha256(canonical_bytes).hexdigest() != manifest.canonical_sha256:
        raise DatasetVerificationError("canonical content hash mismatch")
    if manifest.schema_version == "candle-dataset-v4":
        if (
            closure_manifest_bytes is None
            or exclusion_manifest_bytes is None
            or segment_manifest_bytes is None
        ):
            raise DatasetVerificationError("v4 supporting evidence is missing")
        expected_id = dataset_id_v4(
            provider=manifest.provider,
            instrument=manifest.instrument,
            timeframe=manifest.timeframe,
            start_time=manifest.start_time,
            end_time=manifest.end_time,
            canonical_bytes=canonical_bytes,
            closure_manifest_bytes=closure_manifest_bytes,
            exclusion_manifest_bytes=exclusion_manifest_bytes,
            segment_manifest_bytes=segment_manifest_bytes,
        )
    elif manifest.schema_version == "candle-dataset-v3":
        if (
            closure_manifest_bytes is None
            or exclusion_manifest_bytes is None
            or segment_manifest_bytes is None
        ):
            raise DatasetVerificationError("v3 supporting evidence is missing")
        expected_id = dataset_id_v3(
            provider=manifest.provider,
            instrument=manifest.instrument,
            timeframe=manifest.timeframe,
            start_time=manifest.start_time,
            end_time=manifest.end_time,
            canonical_bytes=canonical_bytes,
            closure_manifest_bytes=closure_manifest_bytes,
            exclusion_manifest_bytes=exclusion_manifest_bytes,
            segment_manifest_bytes=segment_manifest_bytes,
        )
    elif manifest.schema_version == "candle-dataset-v2":
        if closure_manifest_bytes is None or segment_manifest_bytes is None:
            raise DatasetVerificationError("v2 supporting evidence is missing")
        expected_id = dataset_id_v2(
            provider=manifest.provider,
            instrument=manifest.instrument,
            timeframe=manifest.timeframe,
            start_time=manifest.start_time,
            end_time=manifest.end_time,
            canonical_bytes=canonical_bytes,
            closure_manifest_bytes=closure_manifest_bytes,
            segment_manifest_bytes=segment_manifest_bytes,
        )
    else:
        expected_id = dataset_id(manifest.schema_version, canonical_bytes)
    if expected_id != dataset_id_value:
        raise DatasetVerificationError("canonical dataset identity mismatch")


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


def _verify_candle_evidence(
    manifest: DatasetManifest,
    candles: tuple[Candle, ...],
    canonical_bytes: bytes,
    closure_manifest: ExchangeClosureManifest | None = None,
    segment_manifest: CandleSegmentManifest | None = None,
    segment_manifest_bytes: bytes | None = None,
) -> None:
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
        if closure_manifest is None:
            validate_candle_sequence(candles, request)
        else:
            expected_segments = validate_and_segment_candle_sequence(
                candles,
                request,
                closure_manifest,
            )
            if segment_manifest != expected_segments:
                raise DatasetVerificationError("canonical segment manifest mismatch")
            if (
                segment_manifest_bytes is None
                or serialize_candle_segment_manifest(expected_segments) != segment_manifest_bytes
            ):
                raise DatasetVerificationError("canonical segment bytes mismatch")
    except CandleValidationError as error:
        raise DatasetVerificationError("canonical candle sequence validation failed") from error


def load_verified_dataset(
    store: LocalImmutableStore,
    dataset_id_value: str,
    *,
    require_v2: bool = False,
    require_v3: bool = False,
    require_v4: bool = False,
) -> VerifiedDataset:
    """Load and independently verify one immutable canonical dataset."""

    try:
        canonical_bytes, manifest_bytes = store.read_dataset(dataset_id_value)
        manifest = _parse_manifest(manifest_bytes)
        if require_v2 and manifest.schema_version != "candle-dataset-v2":
            raise DatasetVerificationError("sealed dataset loading requires candle-dataset-v2")
        if require_v3 and manifest.schema_version != "candle-dataset-v3":
            raise DatasetVerificationError("sealed dataset loading requires candle-dataset-v3")
        if require_v4 and manifest.schema_version != "candle-dataset-v4":
            raise DatasetVerificationError("sealed dataset loading requires candle-dataset-v4")
        closure_manifest = None
        exclusion_manifest = None
        segment_manifest = None
        closure_manifest_bytes = None
        exclusion_manifest_bytes = None
        segment_manifest_bytes = None
        if manifest.schema_version in {
            "candle-dataset-v2",
            "candle-dataset-v3",
            "candle-dataset-v4",
        }:
            closure_manifest_bytes, segment_manifest_bytes = (
                store.read_dataset_supporting_manifests(dataset_id_value)
            )
            closure_manifest = load_exchange_closure_manifest(closure_manifest_bytes)
            segment_manifest = load_candle_segment_manifest(segment_manifest_bytes)
            if manifest.schema_version in {"candle-dataset-v3", "candle-dataset-v4"}:
                exclusion_manifest_bytes = store.read_dataset_exclusion_manifest_bytes(
                    dataset_id_value
                )
                exclusion_manifest = load_candle_exclusion_manifest(exclusion_manifest_bytes)
            if (
                hashlib.sha256(closure_manifest_bytes).hexdigest()
                != manifest.closure_manifest_sha256
            ):
                raise DatasetVerificationError("closure manifest hash mismatch")
            if (
                exclusion_manifest_bytes is not None
                and hashlib.sha256(exclusion_manifest_bytes).hexdigest()
                != manifest.exclusion_manifest_sha256
            ):
                raise DatasetVerificationError("exclusion manifest hash mismatch")
            if (
                hashlib.sha256(segment_manifest_bytes).hexdigest()
                != manifest.segment_manifest_sha256
            ):
                raise DatasetVerificationError("segment manifest hash mismatch")
            if len(closure_manifest.closures) != manifest.closure_count:
                raise DatasetVerificationError("closure count mismatch")
            if exclusion_manifest is not None:
                if len(exclusion_manifest.exclusions) != manifest.exclusion_count:
                    raise DatasetVerificationError("exclusion count mismatch")
                if manifest.schema_version == "candle-dataset-v4":
                    closure_ids = tuple(item.closure_id for item in closure_manifest.closures)
                    exclusion_ids = tuple(item.closure_id for item in exclusion_manifest.exclusions)
                    if exclusion_ids != closure_ids:
                        raise DatasetVerificationError("exclusion declaration order mismatch")
                declarations = {item.closure_id: item for item in closure_manifest.closures}
                for exclusion in exclusion_manifest.exclusions:
                    declaration = declarations.get(exclusion.closure_id)
                    if declaration is None:
                        raise DatasetVerificationError("exclusion closure identity mismatch")
                    partial = declaration.partial_candle
                    if (
                        exclusion.provider_row_sha256 != partial.provider_row_sha256
                        or exclusion.open_time != partial.open_time
                        or exclusion.actual_close_time != partial.actual_close_time
                        or exclusion.expected_close_time != partial.expected_close_time
                    ):
                        raise DatasetVerificationError("exclusion declaration mismatch")
            if len(segment_manifest.segments) != manifest.segment_count:
                raise DatasetVerificationError("segment count mismatch")
        _verify_content_identity(
            dataset_id_value,
            manifest,
            canonical_bytes,
            closure_manifest_bytes,
            exclusion_manifest_bytes,
            segment_manifest_bytes,
        )
        candles = _parse_candles(canonical_bytes, manifest)
        _verify_candle_evidence(
            manifest,
            candles,
            canonical_bytes,
            closure_manifest,
            segment_manifest,
            segment_manifest_bytes,
        )
    except DatasetVerificationError:
        raise
    except (OSError, TypeError, ValueError) as error:
        raise DatasetVerificationError("canonical dataset could not be loaded safely") from error
    return VerifiedDataset(
        manifest=manifest,
        candles=candles,
        canonical_bytes=canonical_bytes,
        closure_manifest=closure_manifest,
        exclusion_manifest=exclusion_manifest,
        segment_manifest=segment_manifest,
        closure_manifest_bytes=closure_manifest_bytes,
        exclusion_manifest_bytes=exclusion_manifest_bytes,
        segment_manifest_bytes=segment_manifest_bytes,
    )
