"""Provider-free replay and independent verification of multi-closure dataset v4."""

import json
from pathlib import Path

from fixtures.market_data.multi_closure_ingestion import (
    MultiClosureProvider,
    SERVER_TIME,
    manifest_and_rows,
    retrieval_request,
)
from gemini_trading.data.exclusions import load_candle_exclusion_manifest
from gemini_trading.data.ingestion.replay import ReplayService
from gemini_trading.data.ingestion.service import IngestionResult, IngestionService
from gemini_trading.data.segments import load_candle_segment_manifest
from gemini_trading.data.storage.local_immutable import LocalImmutableStore
from gemini_trading.data.verification.service import VerificationService


def _ingest(tmp_path: Path, run_id: str) -> tuple[LocalImmutableStore, IngestionResult, bytes]:
    closure_manifest, closure_bytes, partial_rows = manifest_and_rows()
    store = LocalImmutableStore(tmp_path)
    result = IngestionService(
        provider=MultiClosureProvider(closure_manifest, partial_rows),
        raw_store=store,
        canonical_store=store,
        run_id_factory=lambda: run_id,
        clock=lambda: SERVER_TIME,
        page_limit=3,
        closure_manifest=closure_manifest,
        closure_manifest_bytes=closure_bytes,
    ).ingest(retrieval_request(closure_manifest))
    return store, result, closure_bytes


def _assert_ingested_evidence(
    store: LocalImmutableStore,
    result: IngestionResult,
    closure_bytes: bytes,
) -> None:
    canonical_bytes, manifest_bytes = store.read_dataset(result.dataset_id)
    manifest = json.loads(manifest_bytes)
    canonical_closure, segment_bytes = store.read_dataset_supporting_manifests(result.dataset_id)
    exclusion_bytes = store.read_dataset_exclusion_manifest_bytes(result.dataset_id)
    exclusions = load_candle_exclusion_manifest(exclusion_bytes)
    segments = load_candle_segment_manifest(segment_bytes)

    assert manifest["schema_version"] == "candle-dataset-v4"
    assert manifest["closure_count"] == 2
    assert manifest["exclusion_count"] == 2
    assert manifest["segment_count"] == 3
    assert result.raw_page_count == 4
    assert result.candle_count == canonical_bytes.count(b"\n") == 9
    assert canonical_closure == closure_bytes
    assert tuple(item.closure_id for item in exclusions.exclusions) == (
        "test-zero-missing-interruption",
        "test-one-missing-interruption",
    )
    assert tuple(item.canonical_index_before_removal for item in exclusions.exclusions) == (1, 4)
    assert segments.boundary_indices == (1, 3)


def test_provider_free_replay_reproduces_dataset_v4_exactly(tmp_path: Path) -> None:
    store, result, closure_bytes = _ingest(tmp_path, "sealed-v4-replay-run")
    _assert_ingested_evidence(store, result, closure_bytes)

    replay = ReplayService(
        raw_store=store,
        canonical_store=store,
        clock=lambda: SERVER_TIME,
    ).replay(result.run_id)

    assert replay.dataset_id == result.dataset_id
    assert replay.candle_count == result.candle_count == 9


def test_independent_verification_accepts_dataset_v4(tmp_path: Path) -> None:
    store, result, closure_bytes = _ingest(tmp_path, "sealed-v4-verification-run")
    _assert_ingested_evidence(store, result, closure_bytes)

    verified = VerificationService(raw_store=store, canonical_store=store).verify(
        result.dataset_id,
        result.run_id,
    )

    assert verified.dataset_id == result.dataset_id
    assert verified.candle_count == 9
    assert "partial_candle_exactness" in verified.checks
    assert "exclusion_evidence" in verified.checks
    assert "declared_gap_exactness" in verified.checks
    assert "segment_continuity" in verified.checks
    assert "parsed_continuity" not in verified.checks
