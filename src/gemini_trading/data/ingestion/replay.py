"""Offline reconstruction of canonical datasets from immutable raw evidence."""

import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from gemini_trading.data.datasets.canonical_writer import (
    build_dataset_manifest,
    build_provenance,
    serialize_candles,
    serialize_dataset_manifest,
    serialize_provenance,
)
from gemini_trading.data.errors import MarketDataError
from gemini_trading.data.ingestion.service import IngestionResult
from gemini_trading.data.normalization.binance_klines import normalize_binance_klines
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
_DATASET_SCHEMA_VERSION = "candle-dataset-v1"
_PROVENANCE_SCHEMA_VERSION = "dataset-provenance-v1"
_PROVIDER = "binance_spot"


class ReplayRawStore(Protocol):
    """Readable immutable raw evidence required for offline replay."""

    def read_run(
        self,
        run_id: str,
    ) -> tuple[RetrievalManifest, tuple[RawPage, ...]]: ...

    def read_retrieval_manifest_bytes(self, run_id: str) -> bytes: ...


class ReplayCanonicalStore(Protocol):
    """Canonical publication operations required by offline replay."""

    def write_dataset(
        self,
        dataset_id: str,
        jsonl_bytes: bytes,
        manifest_bytes: bytes,
    ) -> tuple[Path, Path]: ...

    def write_provenance(
        self,
        dataset_id: str,
        run_id: str,
        receipt_bytes: bytes,
    ) -> Path: ...


def _utc_now() -> datetime:
    return datetime.now(UTC)


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
    if manifest.schema_version != _RETRIEVAL_SCHEMA_VERSION:
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


def reconstruct_completed_candles(
    manifest: RetrievalManifest,
    pages: tuple[RawPage, ...],
) -> tuple[Candle, ...]:
    if manifest.server_time_snapshot is None:
        raise MarketDataError("completed retrieval manifest lacks server time")

    candidates = tuple(
        candle
        for page in pages
        for candle in normalize_binance_klines(
            page.response_bytes,
            manifest.instrument,
            manifest.timeframe,
        )
    )
    candles = completed_candles(candidates, manifest.server_time_snapshot)
    request = RetrievalRequest(
        instrument=manifest.instrument,
        timeframe=manifest.timeframe,
        start_time=manifest.start_time,
        end_time=manifest.end_time,
    )
    validate_candle_sequence(candles, request)
    return candles


@dataclass(frozen=True, slots=True)
class ReplayService:
    """Rebuild canonical output without constructing or calling a provider."""

    raw_store: ReplayRawStore
    canonical_store: ReplayCanonicalStore
    clock: Callable[[], datetime] = _utc_now

    def replay(self, run_id: str) -> IngestionResult:
        """Verify immutable raw evidence and reproduce canonical output offline."""

        manifest, pages, manifest_bytes = load_verified_run(self.raw_store, run_id)
        candles = reconstruct_completed_candles(manifest, pages)
        canonical_bytes = serialize_candles(candles)
        dataset_manifest = build_dataset_manifest(
            schema_version=_DATASET_SCHEMA_VERSION,
            provider=manifest.provider,
            instrument=manifest.instrument,
            timeframe=manifest.timeframe,
            start_time=manifest.start_time,
            end_time=manifest.end_time,
            candles=candles,
            canonical_bytes=canonical_bytes,
        )
        dataset_manifest_bytes = serialize_dataset_manifest(dataset_manifest)
        candle_path, dataset_manifest_path = self.canonical_store.write_dataset(
            dataset_manifest.dataset_id,
            canonical_bytes,
            dataset_manifest_bytes,
        )
        provenance = build_provenance(
            schema_version=_PROVENANCE_SCHEMA_VERSION,
            dataset_id=dataset_manifest.dataset_id,
            run_id=run_id,
            page_hashes=manifest.page_hashes,
            retrieval_manifest_sha256=hashlib.sha256(manifest_bytes).hexdigest(),
            linked=True,
            created_at=self.clock(),
        )
        provenance_path = self.canonical_store.write_provenance(
            dataset_manifest.dataset_id,
            run_id,
            serialize_provenance(provenance),
        )
        return IngestionResult(
            run_id=run_id,
            dataset_id=dataset_manifest.dataset_id,
            raw_page_count=len(pages),
            candle_count=len(candles),
            paths=(
                ("canonical_jsonl", candle_path),
                ("dataset_manifest", dataset_manifest_path),
                ("provenance", provenance_path),
            ),
        )
