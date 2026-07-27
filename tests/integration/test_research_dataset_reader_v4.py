"""Strict verified loading contracts for candle-dataset-v4."""

import hashlib
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Protocol, cast

import pytest

from fixtures.market_data.multi_closure_ingestion import (
    SERVER_TIME,
    MultiClosureProvider,
    manifest_and_rows,
    retrieval_request,
)
from gemini_trading.data.datasets.canonical_writer import (
    build_dataset_manifest,
    dataset_id_v4,
    serialize_candles,
    serialize_dataset_manifest,
)
from gemini_trading.data.ingestion.service import IngestionService
from gemini_trading.data.storage.local_immutable import LocalImmutableStore
from gemini_trading.domain.candle import Candle
from gemini_trading.domain.instrument import Instrument
from gemini_trading.domain.timeframe import Timeframe
from gemini_trading.research import dataset_reader
from gemini_trading.research.dataset_reader import VerifiedDataset
from gemini_trading.research.errors import DatasetVerificationError


class _V4Loader(Protocol):
    def __call__(
        self,
        store: LocalImmutableStore,
        dataset_id_value: str,
        *,
        require_v4: bool = False,
    ) -> VerifiedDataset: ...


def _load_v4(store: LocalImmutableStore, dataset_id_value: str) -> VerifiedDataset:
    loader = cast(_V4Loader, dataset_reader.__dict__["load_verified_dataset"])
    return loader(store, dataset_id_value, require_v4=True)


def _candle() -> Candle:
    instrument = Instrument("ETHUSDT", "ETH", "USDT")
    start = datetime(2025, 1, 1, tzinfo=UTC)
    return Candle(
        instrument=instrument,
        timeframe=Timeframe.H4,
        open_time=start,
        close_time=start + timedelta(hours=4) - timedelta(milliseconds=1),
        open=Decimal("100"),
        high=Decimal("110"),
        low=Decimal("90"),
        close=Decimal("105"),
        volume=Decimal("10"),
        completed=True,
        source_provider="binance_spot",
    )


def _write_legacy_dataset(root: Path, schema_version: str) -> str:
    candle = _candle()
    canonical_bytes = serialize_candles((candle,))
    if schema_version == "candle-dataset-v1":
        manifest = build_dataset_manifest(
            schema_version=schema_version,
            provider="binance_spot",
            instrument=candle.instrument,
            timeframe=candle.timeframe,
            start_time=candle.open_time,
            end_time=candle.open_time + candle.timeframe.duration,
            candles=(candle,),
            canonical_bytes=canonical_bytes,
        )
    elif schema_version == "candle-dataset-v2":
        manifest = build_dataset_manifest(
            schema_version=schema_version,
            provider="binance_spot",
            instrument=candle.instrument,
            timeframe=candle.timeframe,
            start_time=candle.open_time,
            end_time=candle.open_time + candle.timeframe.duration,
            candles=(candle,),
            canonical_bytes=canonical_bytes,
            closure_manifest_bytes=b"{}\n",
            segment_manifest_bytes=b"{}\n",
            closure_count=1,
            segment_count=2,
        )
    elif schema_version == "candle-dataset-v3":
        manifest = build_dataset_manifest(
            schema_version=schema_version,
            provider="binance_spot",
            instrument=candle.instrument,
            timeframe=candle.timeframe,
            start_time=candle.open_time,
            end_time=candle.open_time + candle.timeframe.duration,
            candles=(candle,),
            canonical_bytes=canonical_bytes,
            closure_manifest_bytes=b"{}\n",
            exclusion_manifest_bytes=b"{}\n",
            segment_manifest_bytes=b"{}\n",
            closure_count=1,
            exclusion_count=1,
            segment_count=2,
        )
    else:
        raise AssertionError("unsupported legacy fixture schema")
    LocalImmutableStore(root).write_dataset(
        manifest.dataset_id,
        canonical_bytes,
        serialize_dataset_manifest(manifest),
    )
    return manifest.dataset_id


def _ingest_v4(root: Path, run_id: str) -> tuple[LocalImmutableStore, str]:
    closure_manifest, closure_bytes, partial_rows = manifest_and_rows()
    store = LocalImmutableStore(root)
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
    return store, result.dataset_id


def test_require_v4_loads_exact_multi_closure_evidence(tmp_path: Path) -> None:
    store, dataset_id_value = _ingest_v4(tmp_path, "reader-v4-success")

    loaded = _load_v4(store, dataset_id_value)

    assert loaded.manifest.schema_version == "candle-dataset-v4"
    assert (
        loaded.manifest.closure_count,
        loaded.manifest.exclusion_count,
        loaded.manifest.segment_count,
    ) == (2, 2, 3)
    assert loaded.exclusion_manifest is not None
    assert loaded.closure_manifest is not None
    assert tuple(item.closure_id for item in loaded.exclusion_manifest.exclusions) == tuple(
        item.closure_id for item in loaded.closure_manifest.closures
    )


@pytest.mark.parametrize(
    "schema_version",
    ["candle-dataset-v1", "candle-dataset-v2", "candle-dataset-v3"],
)
def test_require_v4_rejects_every_legacy_dataset_schema(
    tmp_path: Path,
    schema_version: str,
) -> None:
    dataset_id_value = _write_legacy_dataset(tmp_path, schema_version)

    with pytest.raises(DatasetVerificationError, match="candle-dataset-v4"):
        _load_v4(LocalImmutableStore(tmp_path), dataset_id_value)


def test_require_v4_rejects_reordered_exclusion_identity(tmp_path: Path) -> None:
    store, dataset_id_value = _ingest_v4(tmp_path, "reader-v4-reordered")
    canonical_bytes, manifest_bytes = store.read_dataset(dataset_id_value)
    closure_bytes, segment_bytes = store.read_dataset_supporting_manifests(dataset_id_value)
    exclusion_bytes = store.read_dataset_exclusion_manifest_bytes(dataset_id_value)

    manifest_payload = cast(dict[str, object], json.loads(manifest_bytes))
    exclusion_payload = cast(dict[str, object], json.loads(exclusion_bytes))
    exclusions = cast(list[object], exclusion_payload["exclusions"])
    exclusion_payload["exclusions"] = list(reversed(exclusions))
    reordered_exclusion_bytes = (
        json.dumps(exclusion_payload, ensure_ascii=False, separators=(",", ":")) + "\n"
    ).encode()
    instrument_payload = cast(dict[str, object], manifest_payload["instrument"])
    instrument = Instrument(
        cast(str, instrument_payload["symbol"]),
        cast(str, instrument_payload["base_asset"]),
        cast(str, instrument_payload["quote_asset"]),
    )
    start_time = datetime.fromisoformat(
        cast(str, manifest_payload["start_time"]).replace("Z", "+00:00")
    )
    end_time = datetime.fromisoformat(
        cast(str, manifest_payload["end_time"]).replace("Z", "+00:00")
    )
    reordered_id = dataset_id_v4(
        provider=cast(str, manifest_payload["provider"]),
        instrument=instrument,
        timeframe=Timeframe(cast(str, manifest_payload["timeframe"])),
        start_time=start_time,
        end_time=end_time,
        canonical_bytes=canonical_bytes,
        closure_manifest_bytes=closure_bytes,
        exclusion_manifest_bytes=reordered_exclusion_bytes,
        segment_manifest_bytes=segment_bytes,
    )
    manifest_payload["dataset_id"] = reordered_id
    manifest_payload["exclusion_manifest_sha256"] = hashlib.sha256(
        reordered_exclusion_bytes
    ).hexdigest()
    reordered_manifest_bytes = (
        json.dumps(manifest_payload, ensure_ascii=False, separators=(",", ":")) + "\n"
    ).encode()
    store.write_dataset(reordered_id, canonical_bytes, reordered_manifest_bytes)
    store.write_dataset_supporting_manifests(reordered_id, closure_bytes, segment_bytes)
    store.write_dataset_exclusion_manifest(reordered_id, reordered_exclusion_bytes)

    with pytest.raises(DatasetVerificationError, match="order|identity"):
        _load_v4(store, reordered_id)
