"""Independent verification of raw evidence, canonical data, and provenance."""

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import cast

from gemini_trading.data.datasets.canonical_writer import (
    build_dataset_manifest,
    build_provenance,
    serialize_candles,
    serialize_dataset_manifest,
    serialize_provenance,
)
from gemini_trading.data.errors import MarketDataError
from gemini_trading.data.ingestion.replay import (
    _load_verified_run,
    _reconstruct_completed_candles,
)
from gemini_trading.data.storage.base import CanonicalStore, RawStore
from gemini_trading.data.validation.candles import validate_candle_sequence
from gemini_trading.domain.candle import Candle
from gemini_trading.domain.dataset import (
    DatasetManifest,
    DatasetProvenance,
    RetrievalRequest,
)
from gemini_trading.domain.instrument import Instrument
from gemini_trading.domain.timeframe import Timeframe

_DATASET_SCHEMA_VERSION = "candle-dataset-v1"
_PROVENANCE_SCHEMA_VERSION = "dataset-provenance-v1"
_CHECKS = (
    "retrieval_manifest_bytes",
    "raw_page_hashes",
    "raw_reconstruction",
    "canonical_bytes",
    "canonical_manifest",
    "dataset_identity",
    "provenance_linkage",
    "parsed_continuity",
    "completed_state",
)


def _json_object(raw: bytes, description: str) -> dict[str, object]:
    try:
        loaded = cast(object, json.loads(raw.decode("utf-8")))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise MarketDataError(f"{description} is not valid JSON") from None
    if not isinstance(loaded, dict):
        raise MarketDataError(f"{description} must be a JSON object")
    mapping = cast(dict[object, object], loaded)
    if not all(isinstance(key, str) for key in mapping):
        raise MarketDataError(f"{description} has invalid keys")
    return cast(dict[str, object], mapping)


def _required_str(mapping: dict[str, object], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str):
        raise MarketDataError(f"verification field is invalid: {key}")
    return value


def _required_bool(mapping: dict[str, object], key: str) -> bool:
    value = mapping.get(key)
    if not isinstance(value, bool):
        raise MarketDataError(f"verification field is invalid: {key}")
    return value


def _required_int(mapping: dict[str, object], key: str) -> int:
    value = mapping.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise MarketDataError(f"verification field is invalid: {key}")
    return value


def _required_mapping(mapping: dict[str, object], key: str) -> dict[str, object]:
    value = mapping.get(key)
    if not isinstance(value, dict):
        raise MarketDataError(f"verification field is invalid: {key}")
    raw_mapping = cast(dict[object, object], value)
    if not all(isinstance(item, str) for item in raw_mapping):
        raise MarketDataError(f"verification field is invalid: {key}")
    return cast(dict[str, object], raw_mapping)


def _required_strings(mapping: dict[str, object], key: str) -> tuple[str, ...]:
    value = mapping.get(key)
    if not isinstance(value, list):
        raise MarketDataError(f"verification field is invalid: {key}")
    raw_values = cast(list[object], value)
    if not all(isinstance(item, str) for item in raw_values):
        raise MarketDataError(f"verification field is invalid: {key}")
    return tuple(cast(list[str], raw_values))


def _parse_datetime(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise MarketDataError("verification timestamp is invalid") from None


def _parse_decimal(value: object, field_name: str) -> Decimal:
    if not isinstance(value, str):
        raise MarketDataError(f"canonical field is invalid: {field_name}")
    try:
        parsed = Decimal(value)
    except InvalidOperation:
        raise MarketDataError(f"canonical field is invalid: {field_name}") from None
    if not parsed.is_finite():
        raise MarketDataError(f"canonical field is invalid: {field_name}")
    return parsed


def _parse_canonical_candles(raw: bytes) -> tuple[Candle, ...]:
    lines = raw.splitlines(keepends=True)
    if not lines or any(not line.endswith(b"\n") or line == b"\n" for line in lines):
        raise MarketDataError("canonical JSONL framing is invalid")

    candles: list[Candle] = []
    for line in lines:
        mapping = _json_object(line[:-1], "canonical candle")
        instrument = Instrument(
            _required_str(mapping, "symbol"),
            _required_str(mapping, "base_asset"),
            _required_str(mapping, "quote_asset"),
        )
        try:
            candle = Candle(
                instrument=instrument,
                timeframe=Timeframe(_required_str(mapping, "timeframe")),
                open_time=_parse_datetime(_required_str(mapping, "open_time")),
                close_time=_parse_datetime(_required_str(mapping, "close_time")),
                open=_parse_decimal(mapping.get("open"), "open"),
                high=_parse_decimal(mapping.get("high"), "high"),
                low=_parse_decimal(mapping.get("low"), "low"),
                close=_parse_decimal(mapping.get("close"), "close"),
                volume=_parse_decimal(mapping.get("volume"), "volume"),
                completed=_required_bool(mapping, "completed"),
                source_provider=_required_str(mapping, "source_provider"),
            )
        except ValueError:
            raise MarketDataError("canonical candle schema is invalid") from None
        candles.append(candle)
    return tuple(candles)


def _parse_dataset_manifest(raw: bytes) -> DatasetManifest:
    mapping = _json_object(raw, "dataset manifest")
    instrument_mapping = _required_mapping(mapping, "instrument")
    try:
        return DatasetManifest(
            schema_version=_required_str(mapping, "schema_version"),
            dataset_id=_required_str(mapping, "dataset_id"),
            provider=_required_str(mapping, "provider"),
            instrument=Instrument(
                _required_str(instrument_mapping, "symbol"),
                _required_str(instrument_mapping, "base_asset"),
                _required_str(instrument_mapping, "quote_asset"),
            ),
            timeframe=Timeframe(_required_str(mapping, "timeframe")),
            start_time=_parse_datetime(_required_str(mapping, "start_time")),
            end_time=_parse_datetime(_required_str(mapping, "end_time")),
            first_open_time=_parse_datetime(_required_str(mapping, "first_open_time")),
            last_open_time=_parse_datetime(_required_str(mapping, "last_open_time")),
            candle_count=_required_int(mapping, "candle_count"),
            canonical_sha256=_required_str(mapping, "canonical_sha256"),
        )
    except ValueError:
        raise MarketDataError("dataset manifest schema is invalid") from None


def _parse_provenance(raw: bytes) -> DatasetProvenance:
    mapping = _json_object(raw, "dataset provenance")
    try:
        return DatasetProvenance(
            schema_version=_required_str(mapping, "schema_version"),
            dataset_id=_required_str(mapping, "dataset_id"),
            run_id=_required_str(mapping, "run_id"),
            page_hashes=_required_strings(mapping, "page_hashes"),
            retrieval_manifest_sha256=_required_str(
                mapping,
                "retrieval_manifest_sha256",
            ),
            linked=_required_bool(mapping, "linked"),
            created_at=_parse_datetime(_required_str(mapping, "created_at")),
        )
    except ValueError:
        raise MarketDataError("dataset provenance schema is invalid") from None


@dataclass(frozen=True, slots=True)
class VerificationResult:
    """Safe summary of independently recomputed verification checks."""

    dataset_id: str
    run_id: str
    candle_count: int
    checks: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class VerificationService:
    """Recompute every persisted integrity claim without network access."""

    raw_store: RawStore
    canonical_store: CanonicalStore

    def verify(self, dataset_id: str, run_id: str) -> VerificationResult:
        """Verify raw evidence, deterministic canonical output, and provenance."""

        try:
            retrieval_manifest, pages, retrieval_manifest_bytes = _load_verified_run(
                self.raw_store,
                run_id,
            )
            reconstructed = _reconstruct_completed_candles(retrieval_manifest, pages)
            canonical_bytes, dataset_manifest_bytes = self.canonical_store.read_dataset(
                dataset_id
            )
            provenance_bytes = self.canonical_store.read_provenance(dataset_id, run_id)

            parsed_candles = _parse_canonical_candles(canonical_bytes)
            request = RetrievalRequest(
                instrument=retrieval_manifest.instrument,
                timeframe=retrieval_manifest.timeframe,
                start_time=retrieval_manifest.start_time,
                end_time=retrieval_manifest.end_time,
            )
            validate_candle_sequence(parsed_candles, request)
            if parsed_candles != reconstructed:
                raise MarketDataError("canonical candles do not match raw reconstruction")
            if serialize_candles(parsed_candles) != canonical_bytes:
                raise MarketDataError("canonical JSONL bytes are not deterministic")

            dataset_manifest = _parse_dataset_manifest(dataset_manifest_bytes)
            if dataset_manifest.schema_version != _DATASET_SCHEMA_VERSION:
                raise MarketDataError("unsupported canonical dataset schema")
            expected_manifest = build_dataset_manifest(
                schema_version=_DATASET_SCHEMA_VERSION,
                provider=retrieval_manifest.provider,
                instrument=retrieval_manifest.instrument,
                timeframe=retrieval_manifest.timeframe,
                start_time=retrieval_manifest.start_time,
                end_time=retrieval_manifest.end_time,
                candles=reconstructed,
                canonical_bytes=canonical_bytes,
            )
            if expected_manifest.dataset_id != dataset_id:
                raise MarketDataError("dataset identity mismatch")
            if dataset_manifest != expected_manifest:
                raise MarketDataError("dataset manifest values do not match recomputation")
            if serialize_dataset_manifest(dataset_manifest) != dataset_manifest_bytes:
                raise MarketDataError("dataset manifest bytes are not deterministic")

            provenance = _parse_provenance(provenance_bytes)
            if provenance.schema_version != _PROVENANCE_SCHEMA_VERSION:
                raise MarketDataError("unsupported provenance schema")
            retrieval_manifest_sha256 = hashlib.sha256(
                retrieval_manifest_bytes
            ).hexdigest()
            expected_provenance = build_provenance(
                schema_version=_PROVENANCE_SCHEMA_VERSION,
                dataset_id=dataset_id,
                run_id=run_id,
                page_hashes=retrieval_manifest.page_hashes,
                retrieval_manifest_sha256=retrieval_manifest_sha256,
                linked=True,
                created_at=provenance.created_at,
            )
            if provenance != expected_provenance:
                raise MarketDataError("dataset provenance linkage mismatch")
            if serialize_provenance(provenance) != provenance_bytes:
                raise MarketDataError("dataset provenance bytes are not deterministic")

            return VerificationResult(
                dataset_id=dataset_id,
                run_id=run_id,
                candle_count=len(reconstructed),
                checks=_CHECKS,
            )
        except MarketDataError:
            raise
        except Exception:
            raise MarketDataError("verification failed") from None
