import hashlib
import inspect
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from gemini_trading.data.datasets.canonical_writer import (
    build_dataset_manifest,
    serialize_candles,
    serialize_dataset_manifest,
)
from gemini_trading.data.errors import MarketDataError
from gemini_trading.data.ingestion.replay import ReplayService
from gemini_trading.data.normalization.binance_klines import normalize_binance_klines
from gemini_trading.data.storage.local_immutable import LocalImmutableStore
from gemini_trading.data.validation.candles import completed_candles, validate_candle_sequence
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
_CREATED_AT = datetime(2025, 1, 1, 11, tzinfo=UTC)
_FIXTURE_ROOT = Path(__file__).parents[3] / "fixtures" / "binance_spot"


def _fixture(name: str) -> bytes:
    return (_FIXTURE_ROOT / name).read_bytes()


def _seed_run(store: LocalImmutableStore, run_id: str) -> RetrievalManifest:
    payloads = (
        _fixture("klines_valid_two_pages_page_1.json"),
        _fixture("klines_valid_two_pages_page_2.json"),
    )
    page_hashes: list[str] = []
    for sequence, payload in enumerate(payloads, start=1):
        page_hash = hashlib.sha256(payload).hexdigest()
        page_hashes.append(page_hash)
        store.write_page(
            RawPage(
                run_id=run_id,
                sequence=sequence,
                request_parameters=tuple(
                    sorted(
                        (
                            ("symbol", "ETHUSDT"),
                            ("interval", "4h"),
                            (
                                "startTime",
                                str(1_735_689_600_000 + (sequence - 1) * 14_400_000),
                            ),
                            ("endTime", "1735775999999"),
                            ("limit", "1000"),
                        )
                    )
                ),
                retrieved_at=_SERVER_TIME + timedelta(seconds=sequence),
                server_time_snapshot=_SERVER_TIME,
                http_status=200,
                response_bytes=payload,
                response_sha256=page_hash,
            )
        )
    manifest = RetrievalManifest(
        schema_version="retrieval-manifest-v1",
        run_id=run_id,
        provider="binance_spot",
        instrument=_INSTRUMENT,
        timeframe=Timeframe.H4,
        start_time=_START,
        end_time=_END,
        server_time_snapshot=_SERVER_TIME,
        page_hashes=tuple(page_hashes),
        retry_count=0,
        status=RetrievalStatus.COMPLETED,
        failure_type=None,
        failure_message=None,
    )
    store.write_retrieval_manifest(manifest)
    return manifest


def _expected_dataset(manifest: RetrievalManifest) -> tuple[bytes, bytes, str]:
    request = RetrievalRequest(
        manifest.instrument,
        manifest.timeframe,
        manifest.start_time,
        manifest.end_time,
    )
    candidates = tuple(
        candle
        for payload in (
            _fixture("klines_valid_two_pages_page_1.json"),
            _fixture("klines_valid_two_pages_page_2.json"),
        )
        for candle in normalize_binance_klines(payload, manifest.instrument, manifest.timeframe)
    )
    assert manifest.server_time_snapshot is not None
    candles = completed_candles(candidates, manifest.server_time_snapshot)
    validate_candle_sequence(candles, request)
    canonical_bytes = serialize_candles(candles)
    dataset_manifest = build_dataset_manifest(
        schema_version="candle-dataset-v1",
        provider=manifest.provider,
        instrument=manifest.instrument,
        timeframe=manifest.timeframe,
        start_time=manifest.start_time,
        end_time=manifest.end_time,
        candles=candles,
        canonical_bytes=canonical_bytes,
    )
    return (
        canonical_bytes,
        serialize_dataset_manifest(dataset_manifest),
        dataset_manifest.dataset_id,
    )


def test_replay_has_no_provider_parameter_and_reproduces_exact_dataset(tmp_path: Path) -> None:
    store = LocalImmutableStore(tmp_path)
    retrieval_manifest = _seed_run(store, "run-001")
    service = ReplayService(
        raw_store=store,
        canonical_store=store,
        clock=lambda: _CREATED_AT,
    )

    assert "provider" not in inspect.signature(ReplayService).parameters
    assert not hasattr(service, "_provider")

    result = service.replay("run-001")

    expected_canonical, expected_manifest, expected_id = _expected_dataset(retrieval_manifest)
    actual_canonical, actual_manifest = store.read_dataset(result.dataset_id)
    assert result.dataset_id == expected_id
    assert result.raw_page_count == 2
    assert result.candle_count == 2
    assert actual_canonical == expected_canonical
    assert actual_manifest == expected_manifest

    provenance = json.loads(store.read_provenance(result.dataset_id, "run-001"))
    retrieval_bytes = store.read_retrieval_manifest_bytes("run-001")
    assert provenance["retrieval_manifest_sha256"] == hashlib.sha256(retrieval_bytes).hexdigest()


def test_equivalent_runs_share_identity_but_keep_separate_receipts(tmp_path: Path) -> None:
    store = LocalImmutableStore(tmp_path)
    _seed_run(store, "run-001")
    _seed_run(store, "run-002")
    service = ReplayService(
        raw_store=store,
        canonical_store=store,
        clock=lambda: _CREATED_AT,
    )

    first = service.replay("run-001")
    second = service.replay("run-002")

    assert first.dataset_id == second.dataset_id
    first_receipt = store.read_provenance(first.dataset_id, "run-001")
    second_receipt = store.read_provenance(second.dataset_id, "run-002")
    assert first_receipt != second_receipt
    assert b'"run_id":"run-001"' in first_receipt
    assert b'"run_id":"run-002"' in second_receipt


def test_replay_recomputes_raw_hashes_and_writes_no_canonical_data_on_tamper(
    tmp_path: Path,
) -> None:
    store = LocalImmutableStore(tmp_path)
    _seed_run(store, "run-001")
    raw_path = tmp_path / "data" / "raw" / "binance_spot" / "run-001" / "page-000001.json"
    raw_path.write_bytes(raw_path.read_bytes() + b" ")
    service = ReplayService(
        raw_store=store,
        canonical_store=store,
        clock=lambda: _CREATED_AT,
    )

    with pytest.raises(MarketDataError, match="raw page hash mismatch"):
        service.replay("run-001")

    assert not (tmp_path / "data" / "canonical").exists()


def test_replay_rejects_failed_retrieval_manifest(tmp_path: Path) -> None:
    store = LocalImmutableStore(tmp_path)
    manifest = _seed_run(store, "run-001")
    manifest_path = (
        tmp_path / "data" / "raw" / "binance_spot" / "run-001" / "retrieval-manifest.json"
    )
    content = manifest_path.read_text()
    manifest_path.write_text(content.replace('"status":"completed"', '"status":"failed"'))
    assert manifest.status is RetrievalStatus.COMPLETED

    with pytest.raises(MarketDataError, match="completed retrieval manifest"):
        ReplayService(
            raw_store=store,
            canonical_store=store,
            clock=lambda: _CREATED_AT,
        ).replay("run-001")
