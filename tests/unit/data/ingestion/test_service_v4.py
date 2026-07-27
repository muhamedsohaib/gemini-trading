"""Sealed ingestion publication contract for candle-dataset-v4."""

import json
from pathlib import Path

from tests.integration.test_market_data_exchange_closure_v3 import (
    MultiClosureProvider,
    _manifest_and_rows,
)

from gemini_trading.data.ingestion.service import IngestionService
from gemini_trading.data.storage.local_immutable import LocalImmutableStore
from gemini_trading.domain.dataset import RetrievalRequest


def test_sealed_ingestion_publishes_v4_with_supporting_evidence(tmp_path: Path) -> None:
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
        run_id_factory=lambda: "sealed-v4-ingestion-run",
        page_limit=3,
        closure_manifest=closure_manifest,
        closure_manifest_bytes=closure_bytes,
    ).ingest(request)

    canonical_bytes, manifest_bytes = store.read_dataset(result.dataset_id)
    payload = json.loads(manifest_bytes)
    retrieval, raw_pages = store.read_run(result.run_id)

    assert payload["schema_version"] == "candle-dataset-v4"
    assert payload["closure_count"] == 2
    assert payload["exclusion_count"] == 2
    assert payload["segment_count"] == 3
    assert result.candle_count == canonical_bytes.count(b"\n") == 9
    assert tuple(page.response_sha256 for page in raw_pages) == retrieval.page_hashes
    assert all(page.response_bytes for page in raw_pages)
    assert set(dict(result.paths)) >= {
        "canonical_closure_manifest",
        "exclusion_manifest",
        "segment_manifest",
    }
