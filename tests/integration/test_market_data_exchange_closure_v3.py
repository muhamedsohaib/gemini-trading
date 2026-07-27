import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from gemini_trading.data.exchange_closures import (
    ExchangeClosure,
    ExchangeClosureManifest,
    PartialCandleDeclaration,
    serialize_exchange_closure_manifest,
)
from gemini_trading.data.exclusions import (
    canonical_binance_row_bytes,
    load_candle_exclusion_manifest,
)
from gemini_trading.data.ingestion.replay import ReplayService
from gemini_trading.data.ingestion.service import IngestionService
from gemini_trading.data.providers.base import HttpResponse, ProviderPage
from gemini_trading.data.segments import load_candle_segment_manifest
from gemini_trading.data.storage.local_immutable import LocalImmutableStore
from gemini_trading.data.verification.service import VerificationService
from gemini_trading.domain.dataset import RetrievalRequest
from gemini_trading.domain.instrument import Instrument
from gemini_trading.domain.timeframe import Timeframe
from gemini_trading.research.dataset_reader import load_verified_dataset

_INSTRUMENT = Instrument(symbol="BTCUSDT", base_asset="BTC", quote_asset="USDT")
_TIMEFRAME = Timeframe.H4
_START = datetime(2020, 1, 1, tzinfo=UTC)
_END = _START + timedelta(hours=48)
_SERVER_TIME = datetime(2026, 7, 2, tzinfo=UTC)
_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


def _milliseconds(value: datetime) -> int:
    return (value - _EPOCH) // timedelta(milliseconds=1)


def _full_row(open_time: datetime, seed: int) -> list[object]:
    value = 10_000 + seed
    return [
        _milliseconds(open_time),
        str(value),
        str(value + 10),
        str(value - 10),
        str(value + 2),
        "100.0",
        _milliseconds(open_time + _TIMEFRAME.duration) - 1,
        "1000.0",
        10,
        "50.0",
        "500.0",
        "0",
    ]


def _partial_row(open_time: datetime, actual_close: datetime, seed: int) -> list[object]:
    row = _full_row(open_time, seed)
    row[6] = _milliseconds(actual_close)
    return row


def _row_sha256(row: list[object]) -> str:
    return hashlib.sha256(canonical_binance_row_bytes(row)).hexdigest()


def _closure(
    *,
    closure_id: str,
    row: list[object],
    actual_close: datetime,
    resumed_open: datetime,
    fully_missing_count: int,
) -> ExchangeClosure:
    open_time = datetime.fromtimestamp(row[0] / 1000, tz=UTC)  # type: ignore[operator]
    return ExchangeClosure(
        closure_id=closure_id,
        canonical_gap_start=open_time,
        resumed_open=resumed_open,
        unavailable_candle_count=fully_missing_count + 1,
        fully_missing_start=open_time + _TIMEFRAME.duration,
        fully_missing_candle_count=fully_missing_count,
        reason_code="test_exchange_interruption",
        governance_reference="test-governance",
        partial_candle=PartialCandleDeclaration(
            open_time=open_time,
            actual_close_time=actual_close,
            expected_close_time=open_time + _TIMEFRAME.duration - timedelta(milliseconds=1),
            provider_row_sha256=_row_sha256(row),
            exclusion_reason="exchange_closed_mid_candle",
        ),
    )


def _manifest_and_rows() -> tuple[
    ExchangeClosureManifest,
    bytes,
    dict[datetime, list[object]],
]:
    first_open = _START + timedelta(hours=4)
    first_close = first_open + timedelta(hours=3, minutes=1)
    second_open = _START + timedelta(hours=16)
    second_close = second_open + timedelta(hours=2, minutes=5)
    first_row = _partial_row(first_open, first_close, 1)
    second_row = _partial_row(second_open, second_close, 2)
    manifest = ExchangeClosureManifest(
        schema_version="exchange-closure-manifest-v3",
        provider="binance_spot",
        instrument=_INSTRUMENT,
        timeframe=_TIMEFRAME,
        start_time=_START,
        end_time=_END,
        closures=(
            _closure(
                closure_id="test-zero-missing-interruption",
                row=first_row,
                actual_close=first_close,
                resumed_open=_START + timedelta(hours=8),
                fully_missing_count=0,
            ),
            _closure(
                closure_id="test-one-missing-interruption",
                row=second_row,
                actual_close=second_close,
                resumed_open=_START + timedelta(hours=24),
                fully_missing_count=1,
            ),
        ),
    )
    return (
        manifest,
        serialize_exchange_closure_manifest(manifest),
        {first_open: first_row, second_open: second_row},
    )


class MultiClosureProvider:
    def __init__(
        self,
        manifest: ExchangeClosureManifest,
        partial_rows: dict[datetime, list[object]],
    ) -> None:
        self._manifest = manifest
        self._partial_rows = partial_rows
        self._page_number = 0

    def fetch_server_time(self) -> datetime:
        return _SERVER_TIME

    def fetch_klines(
        self,
        request: RetrievalRequest,
        cursor: datetime,
        limit: int = 1000,
    ) -> ProviderPage:
        rows: list[list[object]] = []
        open_time = cursor
        page_limit = min(limit, 3)
        while open_time < request.end_time and len(rows) < page_limit:
            partial = self._partial_rows.get(open_time)
            if partial is not None:
                rows.append(partial)
                open_time += request.timeframe.duration
                continue

            skipped = False
            for closure in self._manifest.closures:
                if closure.fully_missing_start <= open_time < closure.resumed_open:
                    open_time = closure.resumed_open
                    skipped = True
                    break
            if skipped:
                continue

            rows.append(_full_row(open_time, len(rows) + self._page_number * page_limit))
            open_time += request.timeframe.duration

        self._page_number += 1
        parameters = tuple(
            sorted(
                (
                    ("symbol", request.instrument.symbol),
                    ("interval", request.timeframe.value),
                    ("startTime", str(_milliseconds(cursor))),
                    ("endTime", str(_milliseconds(request.end_time) - 1)),
                    ("limit", str(limit)),
                )
            )
        )
        return ProviderPage(
            request_parameters=parameters,
            response=HttpResponse(
                status_code=200,
                headers=(),
                body=(json.dumps(rows, separators=(",", ":")) + "\n").encode(),
            ),
            retrieved_at=datetime(2026, 7, 1, tzinfo=UTC) + timedelta(seconds=self._page_number),
        )


def test_v3_ingestion_replay_and_verification_bind_multiple_partial_closures(
    tmp_path: Path,
) -> None:
    closure_manifest, closure_bytes, partial_rows = _manifest_and_rows()
    request = RetrievalRequest(
        instrument=closure_manifest.instrument,
        timeframe=closure_manifest.timeframe,
        start_time=closure_manifest.start_time,
        end_time=closure_manifest.end_time,
    )
    store = LocalImmutableStore(tmp_path)
    result = IngestionService(
        provider=MultiClosureProvider(closure_manifest, partial_rows),
        raw_store=store,
        canonical_store=store,
        run_id_factory=lambda: "sealed-v3-multi-closure-run",
        clock=lambda: _SERVER_TIME,
        page_limit=3,
        closure_manifest=closure_manifest,
        closure_manifest_bytes=closure_bytes,
    ).ingest(request)

    assert result.raw_page_count == 4
    assert result.candle_count == 9
    assert set(dict(result.paths)) == {
        *(f"raw_page_{index:06d}" for index in range(1, 5)),
        "run_closure_manifest",
        "retrieval_manifest",
        "canonical_jsonl",
        "dataset_manifest",
        "canonical_closure_manifest",
        "exclusion_manifest",
        "segment_manifest",
        "provenance",
    }

    canonical_closure, segment_bytes = store.read_dataset_supporting_manifests(result.dataset_id)
    exclusion_bytes = store.read_dataset_exclusion_manifest_bytes(result.dataset_id)
    assert canonical_closure == closure_bytes

    exclusions = load_candle_exclusion_manifest(exclusion_bytes)
    assert tuple(item.closure_id for item in exclusions.exclusions) == tuple(
        item.closure_id for item in closure_manifest.closures
    )
    assert tuple(item.provider_row_sha256 for item in exclusions.exclusions) == tuple(
        item.partial_candle.provider_row_sha256 for item in closure_manifest.closures
    )
    assert tuple(item.canonical_index_before_removal for item in exclusions.exclusions) == (
        1,
        4,
    )

    segments = load_candle_segment_manifest(segment_bytes)
    assert len(segments.segments) == 3
    assert segments.boundary_indices == (1, 3)
    assert tuple(item.preceding_closure_id for item in segments.segments[1:]) == tuple(
        item.closure_id for item in closure_manifest.closures
    )

    loaded = load_verified_dataset(store, result.dataset_id, require_v3=True)
    assert loaded.manifest.schema_version == "candle-dataset-v3"
    assert loaded.manifest.closure_count == 2
    assert loaded.manifest.exclusion_count == 2
    assert loaded.manifest.segment_count == 3
    assert loaded.closure_manifest_bytes == closure_bytes
    assert loaded.exclusion_manifest == exclusions
    assert loaded.segment_manifest == segments

    replay = ReplayService(
        raw_store=store,
        canonical_store=store,
        clock=lambda: _SERVER_TIME,
    ).replay(result.run_id)
    assert replay.dataset_id == result.dataset_id
    assert replay.candle_count == 9

    verified = VerificationService(raw_store=store, canonical_store=store).verify(
        result.dataset_id,
        result.run_id,
    )
    assert verified.dataset_id == result.dataset_id
    assert verified.candle_count == 9
    assert "declared_gap_exactness" in verified.checks
    assert "segment_continuity" in verified.checks
    assert "parsed_continuity" not in verified.checks
