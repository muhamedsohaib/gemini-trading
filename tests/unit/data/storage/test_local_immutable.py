import hashlib
import os
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from gemini_trading.data.errors import RawStorageConflictError
from gemini_trading.data.storage.local_immutable import LocalImmutableStore, write_immutable
from gemini_trading.domain.dataset import RawPage, RetrievalManifest, RetrievalStatus
from gemini_trading.domain.instrument import Instrument
from gemini_trading.domain.timeframe import Timeframe

_INSTRUMENT = Instrument("ETHUSDT", "ETH", "USDT")
_START = datetime(2025, 1, 1, tzinfo=UTC)
_END = datetime(2025, 1, 2, tzinfo=UTC)
_SERVER_TIME = datetime(2025, 1, 2, 0, 0, 0, 123000, tzinfo=UTC)
_RETRIEVED_AT = datetime(2025, 1, 1, 12, 34, 56, 789000, tzinfo=UTC)
_DATASET_ID = "a" * 64


def _page(
    *,
    run_id: str = "run-001",
    sequence: int = 1,
    response_bytes: bytes = b'[[1,"100.00"]]',
) -> RawPage:
    return RawPage(
        run_id=run_id,
        sequence=sequence,
        request_parameters=(("endTime", "1735775999999"), ("startTime", "1735689600000")),
        retrieved_at=_RETRIEVED_AT,
        server_time_snapshot=_SERVER_TIME,
        http_status=200,
        response_bytes=response_bytes,
        response_sha256=hashlib.sha256(response_bytes).hexdigest(),
    )


def _manifest(*pages: RawPage, run_id: str = "run-001") -> RetrievalManifest:
    return RetrievalManifest(
        schema_version="retrieval-manifest-v1",
        run_id=run_id,
        provider="binance_spot",
        instrument=_INSTRUMENT,
        timeframe=Timeframe.H4,
        start_time=_START,
        end_time=_END,
        server_time_snapshot=_SERVER_TIME,
        page_hashes=tuple(page.response_sha256 for page in pages),
        retry_count=0,
        status=RetrievalStatus.COMPLETED,
        failure_type=None,
        failure_message=None,
    )


def test_write_immutable_preserves_exact_bytes_and_identical_write_is_idempotent(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "evidence.bin"
    content = b"\x00exact\r\nbytes\xff"

    assert write_immutable(destination, content) == destination
    assert destination.read_bytes() == content
    inode = destination.stat().st_ino

    assert write_immutable(destination, content) == destination
    assert destination.read_bytes() == content
    assert destination.stat().st_ino == inode


def test_write_immutable_rejects_conflict_and_preserves_existing_target(tmp_path: Path) -> None:
    destination = tmp_path / "evidence.bin"
    write_immutable(destination, b"original")

    with pytest.raises(RawStorageConflictError, match="immutable path conflicts"):
        write_immutable(destination, b"different")

    assert destination.read_bytes() == b"original"


def test_simulated_temporary_write_failure_leaves_no_final_or_temporary_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    destination = tmp_path / "evidence.bin"

    def fail_fsync(_file_descriptor: int) -> None:
        raise OSError("simulated fsync failure")

    monkeypatch.setattr(os, "fsync", fail_fsync)

    with pytest.raises(OSError, match="simulated fsync failure"):
        write_immutable(destination, b"partial content must never publish")

    assert not destination.exists()
    assert list(tmp_path.iterdir()) == []


def test_raw_page_uses_six_digit_name_and_preserves_exact_response_bytes(tmp_path: Path) -> None:
    store = LocalImmutableStore(tmp_path)
    page = _page(sequence=7, response_bytes=b"[\n  [1, 2, 3]\n]\n")

    path = store.write_page(page)

    assert path == tmp_path / "data" / "raw" / "binance_spot" / "run-001" / "page-000007.json"
    assert path.read_bytes() == page.response_bytes


def test_raw_page_sequence_above_six_digits_is_rejected(tmp_path: Path) -> None:
    store = LocalImmutableStore(tmp_path)

    with pytest.raises(ValueError, match="page sequence must fit six digits"):
        store.write_page(_page(sequence=1_000_000))


@pytest.mark.parametrize("bad_run_id", ["../escape", "a/b", "a\\b", "..", "a..b"])
def test_raw_run_identity_rejects_traversal_and_invalid_segments(
    tmp_path: Path,
    bad_run_id: str,
) -> None:
    store = LocalImmutableStore(tmp_path)
    page = replace(_page(), run_id=bad_run_id)

    with pytest.raises(ValueError, match="invalid storage identity"):
        store.write_page(page)


def test_empty_raw_run_identity_is_rejected_before_path_construction(tmp_path: Path) -> None:
    store = LocalImmutableStore(tmp_path)

    with pytest.raises(ValueError, match="invalid storage identity"):
        store.read_run("")


@pytest.mark.parametrize("bad_dataset_id", ["../escape", "a/b", "a\\b", "..", "a..b", ""])
def test_canonical_identity_rejects_traversal_and_invalid_segments(
    tmp_path: Path,
    bad_dataset_id: str,
) -> None:
    store = LocalImmutableStore(tmp_path)

    with pytest.raises(ValueError, match="invalid storage identity"):
        store.write_dataset(bad_dataset_id, b"{}\n", b"{}\n")


def test_retrieval_manifest_has_stable_compact_json_bytes(tmp_path: Path) -> None:
    store = LocalImmutableStore(tmp_path)
    page = _page()
    manifest = _manifest(page)

    path = store.write_retrieval_manifest(manifest)

    expected = (
        b'{"schema_version":"retrieval-manifest-v1","run_id":"run-001",'
        b'"provider":"binance_spot","instrument":{"symbol":"ETHUSDT",'
        b'"base_asset":"ETH","quote_asset":"USDT"},"timeframe":"4h",'
        b'"start_time":"2025-01-01T00:00:00.000Z",'
        b'"end_time":"2025-01-02T00:00:00.000Z",'
        b'"server_time_snapshot":"2025-01-02T00:00:00.123Z",'
        b'"page_hashes":["'
        + page.response_sha256.encode("ascii")
        + b'"],"retry_count":0,"status":"completed","failure_type":null,'
        b'"failure_message":null}\n'
    )
    assert path == (
        tmp_path / "data" / "raw" / "binance_spot" / "run-001" / "retrieval-manifest.json"
    )
    assert path.read_bytes() == expected
    assert store.write_retrieval_manifest(manifest) == path
    assert path.read_bytes() == expected


def test_read_run_reconstructs_typed_manifest_and_raw_pages(tmp_path: Path) -> None:
    store = LocalImmutableStore(tmp_path)
    pages = (
        _page(sequence=1, response_bytes=b"[[1]]"),
        _page(sequence=2, response_bytes=b"[[2]]"),
    )
    for page in pages:
        store.write_page(page)
    manifest = _manifest(*pages)
    store.write_retrieval_manifest(manifest)

    loaded_manifest, loaded_pages = store.read_run("run-001")

    assert loaded_manifest == manifest
    assert loaded_pages == pages
    assert isinstance(loaded_manifest, RetrievalManifest)
    assert all(isinstance(page, RawPage) for page in loaded_pages)


def test_read_run_fails_when_a_manifest_page_file_is_missing(tmp_path: Path) -> None:
    store = LocalImmutableStore(tmp_path)
    page = _page()
    store.write_retrieval_manifest(_manifest(page))

    with pytest.raises(FileNotFoundError, match=r"page-000001\.json"):
        store.read_run("run-001")


def test_canonical_dataset_and_provenance_use_exact_paths_and_bytes(tmp_path: Path) -> None:
    store = LocalImmutableStore(tmp_path)
    jsonl = b'{"open":"100.00"}\n'
    manifest = b'{"dataset_id":"' + _DATASET_ID.encode("ascii") + b'"}\n'
    receipt = b'{"run_id":"run-001"}\n'

    candle_path, manifest_path = store.write_dataset(_DATASET_ID, jsonl, manifest)
    provenance_path = store.write_provenance(_DATASET_ID, "run-001", receipt)

    dataset_root = tmp_path / "data" / "canonical" / _DATASET_ID
    assert candle_path == dataset_root / "candles.jsonl"
    assert manifest_path == dataset_root / "dataset-manifest.json"
    assert provenance_path == dataset_root / "provenance" / "run-001.json"
    assert candle_path.read_bytes() == jsonl
    assert manifest_path.read_bytes() == manifest
    assert provenance_path.read_bytes() == receipt
    assert store.read_dataset(_DATASET_ID) == (jsonl, manifest)
    assert store.read_provenance(_DATASET_ID, "run-001") == receipt


def test_canonical_conflict_preserves_existing_dataset_bytes(tmp_path: Path) -> None:
    store = LocalImmutableStore(tmp_path)
    original_jsonl = b'{"open":"100.00"}\n'
    manifest = b"{}\n"
    store.write_dataset(_DATASET_ID, original_jsonl, manifest)

    with pytest.raises(RawStorageConflictError, match="immutable path conflicts"):
        store.write_dataset(_DATASET_ID, b'{"open":"101.00"}\n', manifest)

    assert store.read_dataset(_DATASET_ID) == (original_jsonl, manifest)


def test_canonical_reads_require_all_expected_files(tmp_path: Path) -> None:
    store = LocalImmutableStore(tmp_path)

    with pytest.raises(FileNotFoundError, match=r"candles\.jsonl"):
        store.read_dataset(_DATASET_ID)
    with pytest.raises(FileNotFoundError, match=r"run-001\.json"):
        store.read_provenance(_DATASET_ID, "run-001")
