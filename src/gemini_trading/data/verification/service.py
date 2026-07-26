"""Independent verification of raw evidence, canonical data, and provenance."""

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Protocol, cast

from gemini_trading.data.datasets.canonical_writer import (
    build_dataset_manifest,
    build_provenance,
    serialize_candles,
    serialize_dataset_manifest,
    serialize_provenance,
)
from gemini_trading.data.errors import MarketDataError
from gemini_trading.data.exchange_closures import load_exchange_closure_manifest
from gemini_trading.data.exclusions import (
    load_candle_exclusion_manifest,
    serialize_candle_exclusion_manifest,
)
from gemini_trading.data.ingestion.replay import (
    ReplayRawStore,
    load_verified_run,
    reconstruct_candles_and_exclusions,
)
from gemini_trading.data.segments import (
    load_candle_segment_manifest,
    serialize_candle_segment_manifest,
    validate_and_segment_candle_sequence,
)
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
_DATASET_SCHEMA_VERSION_V2 = "candle-dataset-v2"
_DATASET_SCHEMA_VERSION_V3 = "candle-dataset-v3"
_RETRIEVAL_SCHEMA_VERSION_V2 = "retrieval-manifest-v2"
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

_V3_CHECKS = (
    "retrieval_manifest_bytes",
    "raw_page_hashes",
    "raw_reconstruction",
    "canonical_bytes",
    "canonical_manifest",
    "dataset_identity",
    "provenance_linkage",
    "partial_candle_exactness",
    "exclusion_evidence",
    "declared_gap_exactness",
    "segment_continuity",
    "completed_state",
)


class VerificationCanonicalStore(Protocol):
    """Readable canonical artifacts required for independent verification."""

    def read_dataset(self, dataset_id: str) -> tuple[bytes, bytes]: ...

    def read_dataset_supporting_manifests(self, dataset_id: str) -> tuple[bytes, bytes]: ...

    def read_dataset_exclusion_manifest_bytes(self, dataset_id: str) -> bytes: ...

    def read_provenance(self, dataset_id: str, run_id: str) -> bytes: ...


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
            closure_manifest_sha256=(
                _required_str(mapping, "closure_manifest_sha256")
                if mapping.get("schema_version")
                in {
                    _DATASET_SCHEMA_VERSION_V2,
                    _DATASET_SCHEMA_VERSION_V3,
                }
                else None
            ),
            exclusion_manifest_sha256=(
                _required_str(mapping, "exclusion_manifest_sha256")
                if mapping.get("schema_version") == _DATASET_SCHEMA_VERSION_V3
                else None
            ),
            segment_manifest_sha256=(
                _required_str(mapping, "segment_manifest_sha256")
                if mapping.get("schema_version")
                in {
                    _DATASET_SCHEMA_VERSION_V2,
                    _DATASET_SCHEMA_VERSION_V3,
                }
                else None
            ),
            closure_count=(
                _required_int(mapping, "closure_count")
                if mapping.get("schema_version")
                in {
                    _DATASET_SCHEMA_VERSION_V2,
                    _DATASET_SCHEMA_VERSION_V3,
                }
                else 0
            ),
            exclusion_count=(
                _required_int(mapping, "exclusion_count")
                if mapping.get("schema_version") == _DATASET_SCHEMA_VERSION_V3
                else 0
            ),
            segment_count=(
                _required_int(mapping, "segment_count")
                if mapping.get("schema_version")
                in {
                    _DATASET_SCHEMA_VERSION_V2,
                    _DATASET_SCHEMA_VERSION_V3,
                }
                else 1
            ),
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

    raw_store: ReplayRawStore
    canonical_store: VerificationCanonicalStore

    def verify(self, dataset_id: str, run_id: str) -> VerificationResult:
        """Verify raw evidence, deterministic canonical output, and provenance."""

        try:
            retrieval_manifest, pages, retrieval_manifest_bytes = load_verified_run(
                self.raw_store,
                run_id,
            )
            closure_manifest = None
            closure_bytes: bytes | None = None
            exclusion_bytes: bytes | None = None
            segment_bytes: bytes | None = None
            stored_exclusions = None
            stored_segments = None
            if retrieval_manifest.schema_version == _RETRIEVAL_SCHEMA_VERSION_V2:
                try:
                    run_closure_bytes = self.raw_store.read_run_closure_manifest_bytes(run_id)
                    closure_manifest = load_exchange_closure_manifest(run_closure_bytes)
                    closure_bytes, segment_bytes = (
                        self.canonical_store.read_dataset_supporting_manifests(dataset_id)
                    )
                    exclusion_bytes = self.canonical_store.read_dataset_exclusion_manifest_bytes(
                        dataset_id
                    )
                    stored_exclusions = load_candle_exclusion_manifest(exclusion_bytes)
                    stored_segments = load_candle_segment_manifest(segment_bytes)
                except Exception:
                    raise MarketDataError(
                        "verification failed to read supporting evidence"
                    ) from None
                if run_closure_bytes != closure_bytes:
                    raise MarketDataError("run and canonical closure evidence differ")
                if (
                    hashlib.sha256(run_closure_bytes).hexdigest()
                    != retrieval_manifest.closure_manifest_sha256
                ):
                    raise MarketDataError("run closure manifest hash mismatch")

            reconstructed, derived_exclusions = reconstruct_candles_and_exclusions(
                retrieval_manifest,
                pages,
                closure_manifest,
            )
            if closure_manifest is not None:
                if stored_exclusions != derived_exclusions:
                    raise MarketDataError("stored candle exclusion evidence mismatch")
                assert exclusion_bytes is not None
                assert derived_exclusions is not None
                if serialize_candle_exclusion_manifest(derived_exclusions) != exclusion_bytes:
                    raise MarketDataError("candle exclusion bytes are not deterministic")
            canonical_bytes, dataset_manifest_bytes = self.canonical_store.read_dataset(dataset_id)
            provenance_bytes = self.canonical_store.read_provenance(dataset_id, run_id)

            parsed_candles = _parse_canonical_candles(canonical_bytes)
            request = RetrievalRequest(
                instrument=retrieval_manifest.instrument,
                timeframe=retrieval_manifest.timeframe,
                start_time=retrieval_manifest.start_time,
                end_time=retrieval_manifest.end_time,
            )
            derived_segments = None
            if closure_manifest is None:
                validate_candle_sequence(parsed_candles, request)
            else:
                derived_segments = validate_and_segment_candle_sequence(
                    parsed_candles,
                    request,
                    closure_manifest,
                )
                if stored_segments != derived_segments:
                    raise MarketDataError("stored candle segment evidence mismatch")
                assert segment_bytes is not None
                if serialize_candle_segment_manifest(derived_segments) != segment_bytes:
                    raise MarketDataError("candle segment bytes are not deterministic")
            if parsed_candles != reconstructed:
                raise MarketDataError("canonical candles do not match raw reconstruction")
            if serialize_candles(parsed_candles) != canonical_bytes:
                raise MarketDataError("canonical JSONL bytes are not deterministic")

            dataset_manifest = _parse_dataset_manifest(dataset_manifest_bytes)
            expected_schema = (
                _DATASET_SCHEMA_VERSION_V3
                if closure_manifest is not None
                else _DATASET_SCHEMA_VERSION
            )
            if dataset_manifest.schema_version != expected_schema:
                raise MarketDataError("unsupported canonical dataset schema")
            expected_manifest = build_dataset_manifest(
                schema_version=expected_schema,
                provider=retrieval_manifest.provider,
                instrument=retrieval_manifest.instrument,
                timeframe=retrieval_manifest.timeframe,
                start_time=retrieval_manifest.start_time,
                end_time=retrieval_manifest.end_time,
                candles=reconstructed,
                canonical_bytes=canonical_bytes,
                closure_manifest_bytes=closure_bytes,
                exclusion_manifest_bytes=exclusion_bytes,
                segment_manifest_bytes=segment_bytes,
                closure_count=(0 if closure_manifest is None else len(closure_manifest.closures)),
                exclusion_count=(
                    0 if derived_exclusions is None else len(derived_exclusions.exclusions)
                ),
                segment_count=(1 if derived_segments is None else len(derived_segments.segments)),
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
            retrieval_manifest_sha256 = hashlib.sha256(retrieval_manifest_bytes).hexdigest()
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
                checks=(_V3_CHECKS if closure_manifest is not None else _CHECKS),
            )
        except MarketDataError:
            raise
        except Exception:
            raise MarketDataError("verification failed") from None
