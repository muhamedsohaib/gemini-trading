import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import pytest

from gemini_trading.data.errors import (
    CandleGapError,
    IncompleteWindowError,
    ProviderConnectionError,
    ProviderRateLimitError,
    ProviderResponseError,
    ProviderSchemaError,
)
from gemini_trading.data.ingestion.retry import RetryPolicy
from gemini_trading.data.ingestion.service import IngestionResult, IngestionService
from gemini_trading.data.normalization.binance_klines import normalize_binance_klines
from gemini_trading.data.providers.base import HttpResponse, ProviderPage
from gemini_trading.data.storage.local_immutable import LocalImmutableStore
from gemini_trading.domain.candle import Candle
from gemini_trading.domain.dataset import (
    RawPage,
    RetrievalManifest,
    RetrievalRequest,
    RetrievalStatus,
)
from gemini_trading.domain.instrument import Instrument
from gemini_trading.domain.timeframe import Timeframe

_INSTRUMENT = Instrument("ETHUSDT", "ETH", "USDT")
_START = datetime(2025, 1, 1, tzinfo=UTC)
_END = datetime(2025, 1, 2, tzinfo=UTC)
_SERVER_TIME = datetime(2025, 1, 1, 10, tzinfo=UTC)
_RETRIEVED_AT = datetime(2025, 1, 1, 10, 0, 1, tzinfo=UTC)
_CREATED_AT = datetime(2025, 1, 1, 10, 0, 2, tzinfo=UTC)
_REQUEST = RetrievalRequest(_INSTRUMENT, Timeframe.H4, _START, _END)
_FIXTURE_ROOT = Path(__file__).parents[3] / "fixtures" / "binance_spot"


class FakeProvider:
    def __init__(
        self,
        *,
        server_results: list[datetime | Exception],
        page_results: list[ProviderPage | Exception],
        events: list[str],
    ) -> None:
        self._server_results = server_results
        self._page_results = page_results
        self.events = events
        self.server_time_calls = 0
        self.cursors: list[datetime] = []
        self.limits: list[int] = []

    def fetch_server_time(self) -> datetime:
        self.events.append("fetch_server_time")
        self.server_time_calls += 1
        result = self._server_results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    def fetch_klines(
        self,
        request: RetrievalRequest,
        cursor: datetime,
        limit: int = 1000,
    ) -> ProviderPage:
        del request
        self.events.append("fetch_klines")
        self.cursors.append(cursor)
        self.limits.append(limit)
        result = self._page_results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


class RecordingStore:
    def __init__(self, root: Path, events: list[str]) -> None:
        self.local = LocalImmutableStore(root)
        self.events = events
        self.dataset_write_count = 0
        self.provenance_write_count = 0

    def write_page(self, page: RawPage) -> Path:
        self.events.append(f"write_page:{page.sequence}")
        return self.local.write_page(page)

    def write_retrieval_manifest(self, manifest: RetrievalManifest) -> Path:
        self.events.append(f"write_manifest:{manifest.status.value}")
        return self.local.write_retrieval_manifest(manifest)

    def read_run(self, run_id: str) -> tuple[RetrievalManifest, tuple[RawPage, ...]]:
        return self.local.read_run(run_id)

    def write_dataset(
        self,
        dataset_id: str,
        jsonl_bytes: bytes,
        manifest_bytes: bytes,
    ) -> tuple[Path, Path]:
        self.events.append("write_dataset")
        self.dataset_write_count += 1
        return self.local.write_dataset(dataset_id, jsonl_bytes, manifest_bytes)

    def write_provenance(
        self,
        dataset_id: str,
        run_id: str,
        receipt_bytes: bytes,
    ) -> Path:
        self.events.append("write_provenance")
        self.provenance_write_count += 1
        return self.local.write_provenance(dataset_id, run_id, receipt_bytes)


def _fixture(name: str) -> bytes:
    return (_FIXTURE_ROOT / name).read_bytes()


def _provider_page(payload: bytes) -> ProviderPage:
    return ProviderPage(
        request_parameters=(("limit", "1000"), ("symbol", "ETHUSDT")),
        response=HttpResponse(status_code=200, headers=(), body=payload),
        retrieved_at=_RETRIEVED_AT,
    )


def _payload(*rows: list[object]) -> bytes:
    return f"{json.dumps(list(rows), separators=(',', ':'))}\n".encode()


def _row(open_ms: int, close_ms: int) -> list[object]:
    return [
        open_ms,
        "100.00",
        "110.00",
        "90.00",
        "105.00",
        "12.3400",
        close_ms,
    ]


def _recording_normalizer(
    events: list[str],
) -> Callable[[bytes, Instrument, Timeframe], tuple[Candle, ...]]:
    def normalize(
        payload: bytes,
        instrument: Instrument,
        timeframe: Timeframe,
    ) -> tuple[Candle, ...]:
        events.append("normalize")
        return normalize_binance_klines(payload, instrument, timeframe)

    return normalize


def _service(
    tmp_path: Path,
    *,
    server_results: list[datetime | Exception] | None = None,
    page_results: list[ProviderPage | Exception],
    retry_policy: RetryPolicy | None = None,
    request_page_limit: int = 1000,
) -> tuple[IngestionService, FakeProvider, RecordingStore, list[float], list[str]]:
    events: list[str] = []
    sleeps: list[float] = []
    provider = FakeProvider(
        server_results=server_results or [_SERVER_TIME],
        page_results=page_results,
        events=events,
    )
    store = RecordingStore(tmp_path, events)
    service = IngestionService(
        provider=provider,
        raw_store=store,
        canonical_store=store,
        retry_policy=retry_policy or RetryPolicy(),
        clock=lambda: _CREATED_AT,
        sleeper=sleeps.append,
        run_id_factory=lambda: "run-001",
        normalizer=_recording_normalizer(events),
        page_limit=request_page_limit,
    )
    return service, provider, store, sleeps, events


def test_success_persists_before_parse_continues_short_page_and_stops_on_guard(
    tmp_path: Path,
) -> None:
    service, provider, store, sleeps, events = _service(
        tmp_path,
        page_results=[
            _provider_page(_fixture("klines_valid_two_pages_page_1.json")),
            _provider_page(_fixture("klines_valid_two_pages_page_2.json")),
        ],
    )

    result = service.ingest(_REQUEST)

    assert isinstance(result, IngestionResult)
    assert result.run_id == "run-001"
    assert result.raw_page_count == 2
    assert result.candle_count == 2
    assert provider.server_time_calls == 1
    assert provider.cursors == [
        _START,
        datetime(2025, 1, 1, 4, tzinfo=UTC),
    ]
    assert provider.limits == [1000, 1000]
    assert sleeps == []
    assert events == [
        "fetch_server_time",
        "fetch_klines",
        "write_page:1",
        "normalize",
        "fetch_klines",
        "write_page:2",
        "normalize",
        "write_manifest:completed",
        "write_dataset",
        "write_provenance",
    ]

    manifest, raw_pages = store.read_run("run-001")
    canonical_bytes, _manifest_bytes = store.local.read_dataset(result.dataset_id)
    assert manifest.status is RetrievalStatus.COMPLETED
    assert manifest.retry_count == 0
    assert len(raw_pages) == 2
    assert canonical_bytes.count(b"\n") == 2
    assert b'"open_time":"2025-01-01T08:00:00.000Z"' not in canonical_bytes
    assert set(dict(result.paths)) == {
        "raw_page_000001",
        "raw_page_000002",
        "retrieval_manifest",
        "canonical_jsonl",
        "dataset_manifest",
        "provenance",
    }


def test_cursor_reaching_request_end_terminates_without_guard_page(tmp_path: Path) -> None:
    request = RetrievalRequest(
        _INSTRUMENT,
        Timeframe.H4,
        _START,
        datetime(2025, 1, 1, 4, tzinfo=UTC),
    )
    service, provider, store, _sleeps, _events = _service(
        tmp_path,
        page_results=[_provider_page(_fixture("klines_valid_two_pages_page_1.json"))],
    )

    result = service.ingest(request)

    assert result.raw_page_count == 1
    assert result.candle_count == 1
    assert provider.cursors == [_START]
    assert store.dataset_write_count == 1


def test_repeated_cursor_is_rejected_and_failed_manifest_is_written(tmp_path: Path) -> None:
    request = RetrievalRequest(
        _INSTRUMENT,
        Timeframe.H4,
        datetime(2025, 1, 1, 4, tzinfo=UTC),
        datetime(2025, 1, 1, 12, tzinfo=UTC),
    )
    service, _provider, store, _sleeps, _events = _service(
        tmp_path,
        page_results=[_provider_page(_fixture("klines_valid_two_pages_page_1.json"))],
    )

    with pytest.raises(IncompleteWindowError, match="cursor did not advance"):
        service.ingest(request)

    manifest, pages = store.read_run("run-001")
    assert manifest.status is RetrievalStatus.FAILED
    assert manifest.failure_type == "IncompleteWindowError"
    assert len(pages) == 1
    assert store.dataset_write_count == 0
    assert store.provenance_write_count == 0


def test_empty_non_terminal_page_fails_closed(tmp_path: Path) -> None:
    service, _provider, store, _sleeps, _events = _service(
        tmp_path,
        page_results=[_provider_page(b"[]")],
    )

    with pytest.raises(IncompleteWindowError, match="empty non-terminal page"):
        service.ingest(_REQUEST)

    manifest, pages = store.read_run("run-001")
    assert manifest.status is RetrievalStatus.FAILED
    assert len(pages) == 1
    assert store.dataset_write_count == 0


@pytest.mark.parametrize(
    ("transient_error", "expected_delay"),
    [
        (ProviderConnectionError("temporary connection failure"), 0.5),
        (ProviderRateLimitError(retry_after_seconds=3.0), 3.0),
        (ProviderResponseError(status_code=503, retryable=True), 0.5),
    ],
)
def test_transient_page_failures_retry_with_bounded_delay(
    tmp_path: Path,
    transient_error: Exception,
    expected_delay: float,
) -> None:
    service, provider, store, sleeps, _events = _service(
        tmp_path,
        page_results=[
            transient_error,
            _provider_page(_fixture("klines_valid_two_pages_page_2.json")),
        ],
    )
    request = RetrievalRequest(
        _INSTRUMENT,
        Timeframe.H4,
        datetime(2025, 1, 1, 4, tzinfo=UTC),
        _END,
    )

    result = service.ingest(request)

    manifest, _pages = store.read_run("run-001")
    assert result.candle_count == 1
    assert provider.cursors == [request.start_time, request.start_time]
    assert sleeps == [expected_delay]
    assert manifest.retry_count == 1


def test_retry_exhaustion_writes_one_failed_manifest_and_no_canonical_output(
    tmp_path: Path,
) -> None:
    service, provider, store, sleeps, events = _service(
        tmp_path,
        page_results=[
            ProviderConnectionError("temporary connection failure"),
            ProviderConnectionError("temporary connection failure"),
            ProviderConnectionError("temporary connection failure"),
        ],
    )

    with pytest.raises(ProviderConnectionError, match="temporary connection failure"):
        service.ingest(_REQUEST)

    manifest, pages = store.read_run("run-001")
    assert provider.cursors == [_START, _START, _START]
    assert sleeps == [0.5, 1.0]
    assert manifest.status is RetrievalStatus.FAILED
    assert manifest.retry_count == 2
    assert manifest.failure_type == "ProviderConnectionError"
    assert pages == ()
    assert events.count("write_manifest:failed") == 1
    assert store.dataset_write_count == 0
    assert store.provenance_write_count == 0


def test_non_retryable_provider_response_is_not_retried(tmp_path: Path) -> None:
    service, provider, store, sleeps, _events = _service(
        tmp_path,
        page_results=[
            ProviderResponseError(status_code=400, retryable=False),
            _provider_page(_fixture("klines_valid_two_pages_page_2.json")),
        ],
    )

    with pytest.raises(ProviderResponseError):
        service.ingest(_REQUEST)

    manifest, _pages = store.read_run("run-001")
    assert provider.cursors == [_START]
    assert sleeps == []
    assert manifest.retry_count == 0
    assert store.dataset_write_count == 0


def test_malformed_page_is_preserved_before_schema_failure(tmp_path: Path) -> None:
    malformed = b'{"private":"raw evidence must remain exact"'
    service, _provider, store, _sleeps, events = _service(
        tmp_path,
        page_results=[_provider_page(malformed)],
    )

    with pytest.raises(ProviderSchemaError):
        service.ingest(_REQUEST)

    manifest, pages = store.read_run("run-001")
    assert manifest.status is RetrievalStatus.FAILED
    assert manifest.page_hashes == (hashlib.sha256(malformed).hexdigest(),)
    assert pages[0].response_bytes == malformed
    assert events.index("write_page:1") < events.index("normalize")
    assert store.dataset_write_count == 0


def test_internal_gap_fails_before_any_canonical_write(tmp_path: Path) -> None:
    service, _provider, store, _sleeps, _events = _service(
        tmp_path,
        server_results=[datetime(2025, 1, 1, 14, tzinfo=UTC)],
        page_results=[_provider_page(_fixture("klines_internal_gap.json"))],
    )

    with pytest.raises(CandleGapError):
        service.ingest(_REQUEST)

    manifest, pages = store.read_run("run-001")
    assert manifest.status is RetrievalStatus.FAILED
    assert len(pages) == 1
    assert store.dataset_write_count == 0
    assert store.provenance_write_count == 0


def test_terminal_page_with_zero_completed_candles_fails_closed(tmp_path: Path) -> None:
    incomplete_only = _payload(_row(1735718400000, 1735732799999))
    service, _provider, store, _sleeps, _events = _service(
        tmp_path,
        page_results=[_provider_page(incomplete_only)],
    )

    with pytest.raises(IncompleteWindowError, match="zero completed candles"):
        service.ingest(_REQUEST)

    manifest, pages = store.read_run("run-001")
    assert manifest.status is RetrievalStatus.FAILED
    assert len(pages) == 1
    assert store.dataset_write_count == 0
