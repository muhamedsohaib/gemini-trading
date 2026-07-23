import hashlib
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from gemini_trading.data.errors import MarketDataError
from gemini_trading.data.ingestion.replay import ReplayService
from gemini_trading.data.storage.local_immutable import LocalImmutableStore
from gemini_trading.data.verification.service import VerificationResult, VerificationService
from gemini_trading.domain.dataset import RawPage, RetrievalManifest, RetrievalStatus
from gemini_trading.domain.instrument import Instrument
from gemini_trading.domain.timeframe import Timeframe

_INSTRUMENT = Instrument("ETHUSDT", "ETH", "USDT")
_START = datetime(2025, 1, 1, tzinfo=UTC)
_END = datetime(2025, 1, 2, tzinfo=UTC)
_SERVER_TIME = datetime(2025, 1, 1, 10, tzinfo=UTC)
_CREATED_AT = datetime(2025, 1, 1, 11, tzinfo=UTC)
_FIXTURE_ROOT = Path(__file__).parents[3] / "fixtures" / "binance_spot"
_EXPECTED_CHECKS = (
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


def _fixture(name: str) -> bytes:
    return (_FIXTURE_ROOT / name).read_bytes()


def _seed_verified_dataset(
    root: Path,
) -> tuple[LocalImmutableStore, str, str]:
    store = LocalImmutableStore(root)
    run_id = "run-001"
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
                request_parameters=(("limit", "1000"), ("symbol", "ETHUSDT")),
                retrieved_at=_SERVER_TIME + timedelta(seconds=sequence),
                server_time_snapshot=_SERVER_TIME,
                http_status=200,
                response_bytes=payload,
                response_sha256=page_hash,
            )
        )
    store.write_retrieval_manifest(
        RetrievalManifest(
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
    )
    result = ReplayService(
        raw_store=store,
        canonical_store=store,
        clock=lambda: _CREATED_AT,
    ).replay(run_id)
    return store, result.dataset_id, run_id


def test_verification_recomputes_all_integrity_and_sequence_checks(tmp_path: Path) -> None:
    store, dataset_id, run_id = _seed_verified_dataset(tmp_path)

    result = VerificationService(
        raw_store=store,
        canonical_store=store,
    ).verify(dataset_id, run_id)

    assert isinstance(result, VerificationResult)
    assert result.dataset_id == dataset_id
    assert result.run_id == run_id
    assert result.candle_count == 2
    assert result.checks == _EXPECTED_CHECKS


@pytest.mark.parametrize(
    "target",
    [
        "raw_page",
        "retrieval_manifest",
        "canonical_jsonl",
        "dataset_manifest",
        "provenance",
    ],
)
def test_verification_rejects_every_persisted_tampering_class(
    tmp_path: Path,
    target: str,
) -> None:
    store, dataset_id, run_id = _seed_verified_dataset(tmp_path)
    raw_directory = tmp_path / "data" / "raw" / "binance_spot" / run_id
    dataset_directory = tmp_path / "data" / "canonical" / dataset_id
    paths = {
        "raw_page": raw_directory / "page-000001.json",
        "retrieval_manifest": raw_directory / "retrieval-manifest.json",
        "canonical_jsonl": dataset_directory / "candles.jsonl",
        "dataset_manifest": dataset_directory / "dataset-manifest.json",
        "provenance": dataset_directory / "provenance" / f"{run_id}.json",
    }
    path = paths[target]
    original = path.read_bytes()
    if target == "canonical_jsonl":
        tampered = original.replace(b'"close":"105.00"', b'"close":"106.00"', 1)
    elif target == "provenance":
        tampered = original.replace(b'"linked":true', b'"linked":false', 1)
    else:
        tampered = original + b" "
    assert tampered != original
    path.write_bytes(tampered)

    with pytest.raises(MarketDataError):
        VerificationService(
            raw_store=store,
            canonical_store=store,
        ).verify(dataset_id, run_id)


def test_verification_rejects_partial_publication_without_receipt(tmp_path: Path) -> None:
    store, dataset_id, run_id = _seed_verified_dataset(tmp_path)
    provenance_path = (
        tmp_path
        / "data"
        / "canonical"
        / dataset_id
        / "provenance"
        / f"{run_id}.json"
    )
    provenance_path.unlink()

    with pytest.raises(MarketDataError, match="verification failed"):
        VerificationService(
            raw_store=store,
            canonical_store=store,
        ).verify(dataset_id, run_id)
