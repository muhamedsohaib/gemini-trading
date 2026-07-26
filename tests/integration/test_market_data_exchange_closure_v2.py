import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from gemini_trading.data.exchange_closures import (
    ExchangeClosure,
    load_fixed_btcusdt_closure_manifest,
)
from gemini_trading.data.exclusions import load_candle_exclusion_manifest
from gemini_trading.data.ingestion.replay import ReplayService
from gemini_trading.data.ingestion.service import IngestionService
from gemini_trading.data.providers.base import HttpResponse, ProviderPage
from gemini_trading.data.segments import load_candle_segment_manifest
from gemini_trading.data.storage.local_immutable import LocalImmutableStore
from gemini_trading.data.verification.service import VerificationService
from gemini_trading.domain.dataset import RetrievalRequest
from gemini_trading.research.dataset_reader import load_verified_dataset

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_SERVER_TIME = datetime(2026, 7, 2, tzinfo=UTC)
_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


def _milliseconds(value: datetime) -> int:
    return (value - _EPOCH) // timedelta(milliseconds=1)


class ClosureAwareProvider:
    def __init__(self, closure: ExchangeClosure) -> None:
        self.closure = closure
        self.page_number = 0

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
        while open_time < request.end_time and len(rows) < limit:
            if open_time == self.closure.canonical_gap_start:
                rows.append(
                    [
                        1518048000000,
                        "7599.00000000",
                        "7844.00000000",
                        "7572.09000000",
                        "7784.02000000",
                        "1521.53731800",
                        1518049694788,
                        "11770168.04386595",
                        12417,
                        "844.25881300",
                        "6532638.63751892",
                        "0",
                    ]
                )
                open_time += request.timeframe.duration
                continue
            if self.closure.fully_missing_start <= open_time < self.closure.resumed_open:
                open_time = self.closure.resumed_open
                continue
            value = 10_000 + len(rows)
            rows.append(
                [
                    _milliseconds(open_time),
                    str(value),
                    str(value + 10),
                    str(value - 10),
                    str(value + 2),
                    "100.0",
                    _milliseconds(open_time + request.timeframe.duration) - 1,
                ]
            )
            open_time += request.timeframe.duration
        self.page_number += 1
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
            retrieved_at=datetime(2026, 7, 1, tzinfo=UTC) + timedelta(seconds=self.page_number),
        )


def test_sealed_ingestion_replay_and_verification_bind_exact_partial_closure(
    tmp_path: Path,
) -> None:
    closure_manifest, closure_bytes = load_fixed_btcusdt_closure_manifest(_PROJECT_ROOT)
    closure = closure_manifest.closures[0]
    request = RetrievalRequest(
        instrument=closure_manifest.instrument,
        timeframe=closure_manifest.timeframe,
        start_time=closure_manifest.start_time,
        end_time=closure_manifest.end_time,
    )
    store = LocalImmutableStore(tmp_path)
    result = IngestionService(
        provider=ClosureAwareProvider(closure),
        raw_store=store,
        canonical_store=store,
        run_id_factory=lambda: "sealed-v2-run",
        clock=lambda: _SERVER_TIME,
        closure_manifest=closure_manifest,
        closure_manifest_bytes=closure_bytes,
    ).ingest(request)

    assert set(dict(result.paths)) == {
        *(f"raw_page_{index:06d}" for index in range(1, result.raw_page_count + 1)),
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
    assert len(exclusions.exclusions) == 1
    assert (
        exclusions.exclusions[0].provider_row_sha256 == closure.partial_candle.provider_row_sha256
    )
    segments = load_candle_segment_manifest(segment_bytes)
    assert len(segments.segments) == 2
    assert segments.segments[1].preceding_closure_id == closure.closure_id

    loaded = load_verified_dataset(store, result.dataset_id, require_v3=True)
    assert loaded.manifest.schema_version == "candle-dataset-v3"
    assert loaded.closure_manifest_bytes == closure_bytes
    assert loaded.exclusion_manifest is not None
    assert loaded.segment_manifest is not None
    assert loaded.segment_manifest.boundary_indices == (228,)

    replay = ReplayService(
        raw_store=store,
        canonical_store=store,
        clock=lambda: _SERVER_TIME,
    ).replay(result.run_id)
    assert replay.dataset_id == result.dataset_id

    verified = VerificationService(raw_store=store, canonical_store=store).verify(
        result.dataset_id,
        result.run_id,
    )
    assert verified.dataset_id == result.dataset_id
    assert "declared_gap_exactness" in verified.checks
    assert "segment_continuity" in verified.checks
    assert "parsed_continuity" not in verified.checks
