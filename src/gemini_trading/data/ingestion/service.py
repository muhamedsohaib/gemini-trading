"""Fail-closed orchestration for bounded market-data ingestion."""

import hashlib
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TypeVar
from uuid import uuid4

from gemini_trading.data.datasets.canonical_writer import (
    build_dataset_manifest,
    build_provenance,
    serialize_candles,
    serialize_dataset_manifest,
    serialize_provenance,
)
from gemini_trading.data.errors import (
    IncompleteWindowError,
    MarketDataError,
    ProviderConnectionError,
    ProviderRateLimitError,
    ProviderResponseError,
)
from gemini_trading.data.ingestion.retry import RetryPolicy
from gemini_trading.data.normalization.binance_klines import normalize_binance_klines
from gemini_trading.data.providers.base import MarketDataProvider
from gemini_trading.data.storage.base import CanonicalStore, RawStore
from gemini_trading.data.validation.candles import completed_candles, validate_candle_sequence
from gemini_trading.domain.candle import Candle
from gemini_trading.domain.dataset import (
    RawPage,
    RetrievalManifest,
    RetrievalRequest,
    RetrievalStatus,
)
from gemini_trading.domain.instrument import Instrument
from gemini_trading.domain.timeframe import Timeframe

_RETRIEVAL_SCHEMA_VERSION = "retrieval-manifest-v1"
_DATASET_SCHEMA_VERSION = "candle-dataset-v1"
_PROVENANCE_SCHEMA_VERSION = "dataset-provenance-v1"
_PROVIDER = "binance_spot"

_T = TypeVar("_T")
_Normalizer = Callable[[bytes, Instrument, Timeframe], tuple[Candle, ...]]


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _new_run_id() -> str:
    return uuid4().hex


def _is_retryable(error: Exception) -> bool:
    if isinstance(error, (ProviderConnectionError, ProviderRateLimitError)):
        return True
    return isinstance(error, ProviderResponseError) and error.retryable


def _safe_failure_message(error: Exception) -> str:
    if isinstance(error, MarketDataError):
        return str(error)
    return "market data ingestion failed"


@dataclass(frozen=True, slots=True)
class IngestionResult:
    """Successful ingestion summary containing only safe identifiers and paths."""

    run_id: str
    dataset_id: str
    raw_page_count: int
    candle_count: int
    paths: tuple[tuple[str, Path], ...]


class IngestionService:
    """Persist raw evidence, validate completely, then publish canonical content."""

    def __init__(
        self,
        *,
        provider: MarketDataProvider,
        raw_store: RawStore,
        canonical_store: CanonicalStore,
        retry_policy: RetryPolicy | None = None,
        clock: Callable[[], datetime] = _utc_now,
        sleeper: Callable[[float], None] = time.sleep,
        run_id_factory: Callable[[], str] = _new_run_id,
        normalizer: _Normalizer = normalize_binance_klines,
        page_limit: int = 1000,
    ) -> None:
        if page_limit < 1:
            raise ValueError("page_limit must be positive")
        self._provider = provider
        self._raw_store = raw_store
        self._canonical_store = canonical_store
        self._retry_policy = retry_policy if retry_policy is not None else RetryPolicy()
        self._clock = clock
        self._sleeper = sleeper
        self._run_id_factory = run_id_factory
        self._normalizer = normalizer
        self._page_limit = page_limit

    def _call_with_retry(
        self,
        operation: Callable[[], _T],
        retry_count: list[int],
    ) -> _T:
        for attempt in range(1, self._retry_policy.max_attempts + 1):
            try:
                return operation()
            except (
                ProviderConnectionError,
                ProviderRateLimitError,
                ProviderResponseError,
            ) as error:
                if not _is_retryable(error) or attempt >= self._retry_policy.max_attempts:
                    raise
                retry_count[0] += 1
                rate_limit = error if isinstance(error, ProviderRateLimitError) else None
                self._sleeper(self._retry_policy.delay_for(attempt, rate_limit))
        raise AssertionError("retry loop exhausted without returning or raising")

    def _terminal_manifest(
        self,
        *,
        run_id: str,
        request: RetrievalRequest,
        server_time_snapshot: datetime | None,
        pages: list[RawPage],
        retry_count: int,
        status: RetrievalStatus,
        failure: Exception | None,
    ) -> RetrievalManifest:
        return RetrievalManifest(
            schema_version=_RETRIEVAL_SCHEMA_VERSION,
            run_id=run_id,
            provider=_PROVIDER,
            instrument=request.instrument,
            timeframe=request.timeframe,
            start_time=request.start_time,
            end_time=request.end_time,
            server_time_snapshot=server_time_snapshot,
            page_hashes=tuple(page.response_sha256 for page in pages),
            retry_count=retry_count,
            status=status,
            failure_type=None if failure is None else type(failure).__name__,
            failure_message=None if failure is None else _safe_failure_message(failure),
        )

    def ingest(self, request: RetrievalRequest) -> IngestionResult:
        """Execute one bounded retrieval run and fail closed on every invalid state."""

        run_id = self._run_id_factory()
        retry_count = [0]
        server_time_snapshot: datetime | None = None
        pages: list[RawPage] = []
        candidates: list[Candle] = []
        paths: list[tuple[str, Path]] = []
        completed_manifest_written = False

        try:
            server_time = self._call_with_retry(
                self._provider.fetch_server_time,
                retry_count,
            )
            server_time_snapshot = server_time
            cursor = request.start_time
            sequence = 1

            while cursor < request.end_time:
                provider_page = self._call_with_retry(
                    lambda: self._provider.fetch_klines(
                        request,
                        cursor,
                        self._page_limit,
                    ),
                    retry_count,
                )
                response_bytes = provider_page.response.body
                raw_page = RawPage(
                    run_id=run_id,
                    sequence=sequence,
                    request_parameters=provider_page.request_parameters,
                    retrieved_at=provider_page.retrieved_at,
                    server_time_snapshot=server_time,
                    http_status=provider_page.response.status_code,
                    response_bytes=response_bytes,
                    response_sha256=hashlib.sha256(response_bytes).hexdigest(),
                )
                page_path = self._raw_store.write_page(raw_page)
                pages.append(raw_page)
                paths.append((f"raw_page_{sequence:06d}", page_path))

                normalized = self._normalizer(
                    response_bytes,
                    request.instrument,
                    request.timeframe,
                )
                if not normalized:
                    raise IncompleteWindowError("provider returned empty non-terminal page")

                terminal_guard = any(candle.close_time >= server_time for candle in normalized)
                next_cursor = normalized[-1].open_time + request.timeframe.duration
                if next_cursor <= cursor:
                    raise IncompleteWindowError("provider cursor did not advance")

                candidates.extend(normalized)
                cursor = next_cursor
                sequence += 1
                if terminal_guard:
                    break

            canonical_candles = completed_candles(candidates, server_time)
            if not canonical_candles:
                raise IncompleteWindowError("retrieval produced zero completed candles")
            validate_candle_sequence(canonical_candles, request)

            canonical_bytes = serialize_candles(canonical_candles)
            dataset_manifest = build_dataset_manifest(
                schema_version=_DATASET_SCHEMA_VERSION,
                provider=_PROVIDER,
                instrument=request.instrument,
                timeframe=request.timeframe,
                start_time=request.start_time,
                end_time=request.end_time,
                candles=canonical_candles,
                canonical_bytes=canonical_bytes,
            )
            dataset_manifest_bytes = serialize_dataset_manifest(dataset_manifest)

            retrieval_manifest = self._terminal_manifest(
                run_id=run_id,
                request=request,
                server_time_snapshot=server_time_snapshot,
                pages=pages,
                retry_count=retry_count[0],
                status=RetrievalStatus.COMPLETED,
                failure=None,
            )
            retrieval_manifest_path = self._raw_store.write_retrieval_manifest(
                retrieval_manifest
            )
            completed_manifest_written = True
            paths.append(("retrieval_manifest", retrieval_manifest_path))
            retrieval_manifest_sha256 = hashlib.sha256(
                retrieval_manifest_path.read_bytes()
            ).hexdigest()

            candle_path, dataset_manifest_path = self._canonical_store.write_dataset(
                dataset_manifest.dataset_id,
                canonical_bytes,
                dataset_manifest_bytes,
            )
            paths.extend(
                (
                    ("canonical_jsonl", candle_path),
                    ("dataset_manifest", dataset_manifest_path),
                )
            )

            provenance = build_provenance(
                schema_version=_PROVENANCE_SCHEMA_VERSION,
                dataset_id=dataset_manifest.dataset_id,
                run_id=run_id,
                page_hashes=tuple(page.response_sha256 for page in pages),
                retrieval_manifest_sha256=retrieval_manifest_sha256,
                linked=True,
                created_at=self._clock(),
            )
            provenance_path = self._canonical_store.write_provenance(
                dataset_manifest.dataset_id,
                run_id,
                serialize_provenance(provenance),
            )
            paths.append(("provenance", provenance_path))

            return IngestionResult(
                run_id=run_id,
                dataset_id=dataset_manifest.dataset_id,
                raw_page_count=len(pages),
                candle_count=len(canonical_candles),
                paths=tuple(paths),
            )
        except Exception as error:
            if not completed_manifest_written:
                failed_manifest = self._terminal_manifest(
                    run_id=run_id,
                    request=request,
                    server_time_snapshot=server_time_snapshot,
                    pages=pages,
                    retry_count=retry_count[0],
                    status=RetrievalStatus.FAILED,
                    failure=error,
                )
                self._raw_store.write_retrieval_manifest(failed_manifest)
            raise
