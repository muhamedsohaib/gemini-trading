"""Offline reconstruction of canonical datasets from immutable raw evidence."""

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Protocol, cast

from gemini_trading.data.datasets.canonical_writer import (
    build_dataset_manifest,
    build_provenance,
    serialize_candles,
    serialize_dataset_manifest,
    serialize_provenance,
)
from gemini_trading.data.errors import MarketDataError
from gemini_trading.data.exchange_closures import (
    ExchangeClosureManifest,
    load_exchange_closure_manifest,
)
from gemini_trading.data.exclusions import (
    CandleExclusionManifest,
    match_and_exclude_partial_candles,
    serialize_candle_exclusion_manifest,
)
from gemini_trading.data.ingestion.service import IngestionResult
from gemini_trading.data.normalization.binance_klines import normalize_binance_klines
from gemini_trading.data.segments import (
    serialize_candle_segment_manifest,
    validate_and_segment_candle_sequence,
)
from gemini_trading.data.storage.local_immutable import serialize_retrieval_manifest
from gemini_trading.data.validation.candles import completed_candles, validate_candle_sequence
from gemini_trading.domain.candle import Candle
from gemini_trading.domain.dataset import (
    RawPage,
    RetrievalManifest,
    RetrievalRequest,
    RetrievalStatus,
)

_RETRIEVAL_SCHEMA_VERSION = "retrieval-manifest-v1"
_RETRIEVAL_SCHEMA_VERSION_V2 = "retrieval-manifest-v2"
_DATASET_SCHEMA_VERSION = "candle-dataset-v1"
_DATASET_SCHEMA_VERSION_V2 = "candle-dataset-v2"
_DATASET_SCHEMA_VERSION_V4 = "candle-dataset-v4"
_PROVENANCE_SCHEMA_VERSION = "dataset-provenance-v1"
_PROVIDER = "binance_spot"
_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
_REQUEST_PARAMETER_KEYS = {"symbol", "interval", "startTime", "endTime", "limit"}


class ReplayRawStore(Protocol):
    """Readable immutable raw evidence required for offline replay."""

    def read_run(
        self,
        run_id: str,
    ) -> tuple[RetrievalManifest, tuple[RawPage, ...]]: ...

    def read_retrieval_manifest_bytes(self, run_id: str) -> bytes: ...

    def read_run_closure_manifest_bytes(self, run_id: str) -> bytes: ...


class ReplayCanonicalStore(Protocol):
    """Canonical publication operations required by offline replay."""

    def write_dataset(
        self,
        dataset_id: str,
        jsonl_bytes: bytes,
        manifest_bytes: bytes,
    ) -> tuple[Path, Path]: ...

    def write_dataset_supporting_manifests(
        self,
        dataset_id: str,
        closure_raw: bytes,
        segment_raw: bytes,
    ) -> tuple[Path, Path]: ...

    def write_dataset_exclusion_manifest(self, dataset_id: str, exclusion_raw: bytes) -> Path: ...

    def read_provenance(self, dataset_id: str, run_id: str) -> bytes: ...

    def write_provenance(
        self,
        dataset_id: str,
        run_id: str,
        receipt_bytes: bytes,
    ) -> Path: ...


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _utc_milliseconds(value: datetime) -> int:
    return (value - _EPOCH) // timedelta(milliseconds=1)


def _existing_provenance_created_at(raw: bytes) -> datetime:
    try:
        loaded: object = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise MarketDataError("existing dataset provenance is invalid") from None
    if not isinstance(loaded, dict):
        raise MarketDataError("existing dataset provenance is invalid")
    mapping = cast(dict[object, object], loaded)
    created_at = mapping.get("created_at")
    if not isinstance(created_at, str):
        raise MarketDataError("existing dataset provenance is invalid")
    try:
        return datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    except ValueError:
        raise MarketDataError("existing dataset provenance is invalid") from None


def _replay_provenance_bytes(
    canonical_store: ReplayCanonicalStore,
    *,
    dataset_id: str,
    run_id: str,
    page_hashes: tuple[str, ...],
    retrieval_manifest_sha256: str,
    clock: Callable[[], datetime],
) -> bytes:
    try:
        existing = canonical_store.read_provenance(dataset_id, run_id)
    except FileNotFoundError:
        provenance = build_provenance(
            schema_version=_PROVENANCE_SCHEMA_VERSION,
            dataset_id=dataset_id,
            run_id=run_id,
            page_hashes=page_hashes,
            retrieval_manifest_sha256=retrieval_manifest_sha256,
            linked=True,
            created_at=clock(),
        )
        return serialize_provenance(provenance)
    except OSError:
        raise MarketDataError("replay failed to read existing provenance") from None

    try:
        expected = build_provenance(
            schema_version=_PROVENANCE_SCHEMA_VERSION,
            dataset_id=dataset_id,
            run_id=run_id,
            page_hashes=page_hashes,
            retrieval_manifest_sha256=retrieval_manifest_sha256,
            linked=True,
            created_at=_existing_provenance_created_at(existing),
        )
    except ValueError:
        raise MarketDataError("existing dataset provenance is invalid") from None
    if serialize_provenance(expected) != existing:
        raise MarketDataError("existing dataset provenance does not match replay")
    return existing


def _validate_request_parameters(
    manifest: RetrievalManifest,
    page: RawPage,
    cursor: datetime,
) -> None:
    parameters = page.request_parameters
    if parameters != tuple(sorted(parameters)):
        raise MarketDataError("raw page request parameters are not sorted")
    mapping = dict(parameters)
    if len(mapping) != len(parameters) or set(mapping) != _REQUEST_PARAMETER_KEYS:
        raise MarketDataError("raw page request parameters do not match retrieval manifest")

    limit_text = mapping["limit"]
    try:
        limit = int(limit_text)
    except ValueError:
        raise MarketDataError("raw page request parameters contain an invalid limit") from None
    if not 1 <= limit <= 1000 or str(limit) != limit_text:
        raise MarketDataError("raw page request parameters contain an invalid limit")

    expected = tuple(
        sorted(
            (
                ("symbol", manifest.instrument.symbol),
                ("interval", manifest.timeframe.value),
                ("startTime", str(_utc_milliseconds(cursor))),
                ("endTime", str(_utc_milliseconds(manifest.end_time) - 1)),
                ("limit", limit_text),
            )
        )
    )
    if parameters != expected:
        raise MarketDataError("raw page request parameters do not match retrieval manifest")


def load_verified_run(
    raw_store: ReplayRawStore,
    run_id: str,
) -> tuple[RetrievalManifest, tuple[RawPage, ...], bytes]:
    try:
        manifest, pages = raw_store.read_run(run_id)
        manifest_bytes = raw_store.read_retrieval_manifest_bytes(run_id)
    except Exception:
        raise MarketDataError("replay failed to read raw evidence") from None

    if manifest.run_id != run_id:
        raise MarketDataError("retrieval manifest run identity mismatch")
    if manifest.schema_version not in {
        _RETRIEVAL_SCHEMA_VERSION,
        _RETRIEVAL_SCHEMA_VERSION_V2,
    }:
        raise MarketDataError("unsupported retrieval manifest schema")
    if manifest.provider != _PROVIDER:
        raise MarketDataError("unsupported retrieval provider")
    if manifest.status is not RetrievalStatus.COMPLETED:
        raise MarketDataError("replay requires a completed retrieval manifest")
    if manifest.server_time_snapshot is None:
        raise MarketDataError("completed retrieval manifest lacks server time")
    if manifest_bytes != serialize_retrieval_manifest(manifest):
        raise MarketDataError("retrieval manifest bytes are not canonical")
    if len(pages) != len(manifest.page_hashes):
        raise MarketDataError("raw page count does not match retrieval manifest")

    for expected_sequence, (page, expected_hash) in enumerate(
        zip(pages, manifest.page_hashes, strict=True),
        start=1,
    ):
        if page.run_id != run_id or page.sequence != expected_sequence:
            raise MarketDataError("raw page identity mismatch")
        if page.server_time_snapshot != manifest.server_time_snapshot:
            raise MarketDataError("raw page server-time snapshot mismatch")
        if not 200 <= page.http_status <= 299:
            raise MarketDataError("raw page HTTP status is not successful")
        actual_hash = hashlib.sha256(page.response_bytes).hexdigest()
        if actual_hash != expected_hash or actual_hash != page.response_sha256:
            raise MarketDataError("raw page hash mismatch")

    return manifest, pages, manifest_bytes


def reconstruct_candles_and_exclusions(
    manifest: RetrievalManifest,
    pages: tuple[RawPage, ...],
    closure_manifest: ExchangeClosureManifest | None = None,
) -> tuple[tuple[Candle, ...], CandleExclusionManifest | None]:
    """Reconstruct canonical candles and exact exclusion evidence from raw pages."""

    if manifest.server_time_snapshot is None:
        raise MarketDataError("completed retrieval manifest lacks server time")

    cursor = manifest.start_time
    terminal_guard_seen = False
    candidates: list[Candle] = []
    normalized_pages: list[tuple[Candle, ...]] = []
    previous_retrieved_at: datetime | None = None

    for index, page in enumerate(pages):
        if terminal_guard_seen:
            raise MarketDataError("raw evidence continues after a terminal guard page")
        if previous_retrieved_at is not None and page.retrieved_at < previous_retrieved_at:
            raise MarketDataError("raw page retrieval times are out of order")
        previous_retrieved_at = page.retrieved_at

        _validate_request_parameters(manifest, page, cursor)
        normalized = normalize_binance_klines(
            page.response_bytes,
            manifest.instrument,
            manifest.timeframe,
        )
        if not normalized:
            raise MarketDataError("raw evidence contains an empty non-terminal page")
        if index == 0 and normalized[0].open_time != cursor:
            raise MarketDataError("raw evidence does not begin at the requested cursor")
        if index > 0 and normalized[0].open_time < cursor:
            raise MarketDataError("raw evidence page begins before the requested cursor")

        next_cursor = normalized[-1].open_time + manifest.timeframe.duration
        if next_cursor <= cursor:
            raise MarketDataError("raw evidence cursor did not advance")
        terminal_guard_seen = any(
            candle.close_time >= manifest.server_time_snapshot for candle in normalized
        )
        if terminal_guard_seen and index != len(pages) - 1:
            raise MarketDataError("raw evidence continues after a terminal guard page")

        candidates.extend(normalized)
        normalized_pages.append(normalized)
        cursor = next_cursor

    if not terminal_guard_seen and cursor < manifest.end_time:
        raise MarketDataError("raw evidence does not cover the requested window")

    request = RetrievalRequest(
        instrument=manifest.instrument,
        timeframe=manifest.timeframe,
        start_time=manifest.start_time,
        end_time=manifest.end_time,
    )
    if closure_manifest is None:
        candles = completed_candles(candidates, manifest.server_time_snapshot)
        validate_candle_sequence(candles, request)
        return candles, None

    exclusion_result = match_and_exclude_partial_candles(
        pages,
        normalized_pages,
        closure_manifest,
        server_time=manifest.server_time_snapshot,
    )
    validate_and_segment_candle_sequence(
        exclusion_result.candles,
        request,
        closure_manifest,
    )
    return exclusion_result.candles, exclusion_result.manifest


def reconstruct_completed_candles(
    manifest: RetrievalManifest,
    pages: tuple[RawPage, ...],
    closure_manifest: ExchangeClosureManifest | None = None,
) -> tuple[Candle, ...]:
    """Compatibility wrapper returning only reconstructed canonical candles."""

    return reconstruct_candles_and_exclusions(manifest, pages, closure_manifest)[0]


@dataclass(frozen=True, slots=True)
class ReplayService:
    """Rebuild canonical output without constructing or calling a provider."""

    raw_store: ReplayRawStore
    canonical_store: ReplayCanonicalStore
    clock: Callable[[], datetime] = _utc_now

    def replay(self, run_id: str) -> IngestionResult:
        """Verify immutable raw evidence and reproduce canonical output offline."""

        manifest, pages, manifest_bytes = load_verified_run(self.raw_store, run_id)
        closure_manifest: ExchangeClosureManifest | None = None
        closure_bytes: bytes | None = None
        exclusion_bytes: bytes | None = None
        exclusion_count = 0
        segment_bytes: bytes | None = None
        segment_count = 1
        if manifest.schema_version == _RETRIEVAL_SCHEMA_VERSION_V2:
            try:
                closure_bytes = self.raw_store.read_run_closure_manifest_bytes(run_id)
                closure_manifest = load_exchange_closure_manifest(closure_bytes)
            except Exception:
                raise MarketDataError("replay failed to read closure evidence") from None
            if hashlib.sha256(closure_bytes).hexdigest() != manifest.closure_manifest_sha256:
                raise MarketDataError("run closure manifest hash mismatch")

        candles, exclusion_manifest = reconstruct_candles_and_exclusions(
            manifest,
            pages,
            closure_manifest,
        )
        if closure_manifest is not None:
            if exclusion_manifest is None:
                raise MarketDataError("replay did not reproduce exclusion evidence")
            exclusion_bytes = serialize_candle_exclusion_manifest(exclusion_manifest)
            exclusion_count = len(exclusion_manifest.exclusions)
            request = RetrievalRequest(
                instrument=manifest.instrument,
                timeframe=manifest.timeframe,
                start_time=manifest.start_time,
                end_time=manifest.end_time,
            )
            segment_manifest = validate_and_segment_candle_sequence(
                candles,
                request,
                closure_manifest,
            )
            segment_bytes = serialize_candle_segment_manifest(segment_manifest)
            segment_count = len(segment_manifest.segments)

        canonical_bytes = serialize_candles(candles)
        dataset_manifest = build_dataset_manifest(
            schema_version=(
                _DATASET_SCHEMA_VERSION_V4
                if closure_manifest is not None
                else _DATASET_SCHEMA_VERSION
            ),
            provider=manifest.provider,
            instrument=manifest.instrument,
            timeframe=manifest.timeframe,
            start_time=manifest.start_time,
            end_time=manifest.end_time,
            candles=candles,
            canonical_bytes=canonical_bytes,
            closure_manifest_bytes=closure_bytes,
            exclusion_manifest_bytes=exclusion_bytes,
            segment_manifest_bytes=segment_bytes,
            closure_count=(0 if closure_manifest is None else len(closure_manifest.closures)),
            exclusion_count=exclusion_count,
            segment_count=segment_count,
        )
        dataset_manifest_bytes = serialize_dataset_manifest(dataset_manifest)
        candle_path, dataset_manifest_path = self.canonical_store.write_dataset(
            dataset_manifest.dataset_id,
            canonical_bytes,
            dataset_manifest_bytes,
        )
        supporting_paths: tuple[tuple[str, Path], ...] = ()
        if closure_bytes is not None and exclusion_bytes is not None and segment_bytes is not None:
            closure_path, segment_path = self.canonical_store.write_dataset_supporting_manifests(
                dataset_manifest.dataset_id,
                closure_bytes,
                segment_bytes,
            )
            exclusion_path = self.canonical_store.write_dataset_exclusion_manifest(
                dataset_manifest.dataset_id,
                exclusion_bytes,
            )
            supporting_paths = (
                ("canonical_closure_manifest", closure_path),
                ("exclusion_manifest", exclusion_path),
                ("segment_manifest", segment_path),
            )
        provenance_bytes = _replay_provenance_bytes(
            self.canonical_store,
            dataset_id=dataset_manifest.dataset_id,
            run_id=run_id,
            page_hashes=manifest.page_hashes,
            retrieval_manifest_sha256=hashlib.sha256(manifest_bytes).hexdigest(),
            clock=self.clock,
        )
        provenance_path = self.canonical_store.write_provenance(
            dataset_manifest.dataset_id,
            run_id,
            provenance_bytes,
        )
        return IngestionResult(
            run_id=run_id,
            dataset_id=dataset_manifest.dataset_id,
            raw_page_count=len(pages),
            candle_count=len(candles),
            paths=(
                ("canonical_jsonl", candle_path),
                ("dataset_manifest", dataset_manifest_path),
                *supporting_paths,
                ("provenance", provenance_path),
            ),
        )
